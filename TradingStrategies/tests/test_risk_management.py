"""Tests for the Risk Management and Interceptor Middleware.

Verifies pre-flight validation checks, dynamic lot calculations, TP splitter
volume allocations, and channel win/loss streaks calculation using mock MT5 data.
"""

import os
import sys
import sqlite3
import asyncio
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Provide access to the telegram_to_mt5_bot modules
current_dir = Path(__file__).resolve().parent
bot_dir = current_dir.parent / 'telegram_to_mt5_bot'
if str(bot_dir) not in sys.path:
    sys.path.insert(0, str(bot_dir))

# Mock MetaTrader5 before importing risk_manager
mock_mt5 = MagicMock()
sys.modules['MetaTrader5'] = mock_mt5

import risk_manager
from config import config

TEST_DB_PATH = "test_risk_management.db"


@pytest.fixture(autouse=True)
def setup_test_db():
    """Setup a separate database path for tests and tear it down after."""
    original_db_path = risk_manager.DB_PATH
    risk_manager.DB_PATH = TEST_DB_PATH
    
    # Initialize the test DB tables
    risk_manager.init_db()
    
    yield
    
    # Teardown: delete test DB
    risk_manager.DB_PATH = original_db_path
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass


def test_db_initialization():
    """Verify that tables are created correctly on database init."""
    assert os.path.exists(TEST_DB_PATH)
    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='channels'")
    assert cursor.fetchone() is not None
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracked_orders'")
    assert cursor.fetchone() is not None
    conn.close()


@pytest.mark.asyncio
async def test_get_or_create_magic_number():
    """Verify channel Magic Number generation and persistence."""
    # First channel should get 1000001
    m1 = await risk_manager.get_or_create_magic_number("channel_A")
    assert m1 == 1000001
    
    # Same channel name should yield the same magic number
    m1_retry = await risk_manager.get_or_create_magic_number("channel_A")
    assert m1_retry == 1000001
    
    # Second channel should get 1000002
    m2 = await risk_manager.get_or_create_magic_number("channel_B")
    assert m2 == 1000002


@pytest.mark.asyncio
async def test_set_channel_paused_and_stats():
    """Verify setting channel pause status and fetching statistics."""
    channel = "test_channel_streak"
    magic = await risk_manager.get_or_create_magic_number(channel)
    
    # Defaults
    status = await risk_manager.get_channel_status(channel)
    assert status["paused"] is False
    assert status["consecutive_losses"] == 0
    
    # Set paused
    success = await risk_manager.set_channel_paused(magic, True)
    assert success is True
    
    status = await risk_manager.get_channel_status(channel)
    assert status["paused"] is True
    
    # Unpause
    success = await risk_manager.set_channel_paused(magic, False)
    assert success is True
    
    status = await risk_manager.get_channel_status(channel)
    assert status["paused"] is False


def test_calculate_lot_size_fixed():
    """Verify lot size calculation in 'fixed_lot' sizing mode."""
    config.risk_sizing_mode = "fixed_lot"
    config.fixed_lot_size = 0.05
    config.max_allowed_lot_size = 1.0
    
    mock_mt5.initialize.return_value = True
    
    # Mock symbol info
    sym_info = MagicMock()
    sym_info.point = 0.01
    sym_info.trade_tick_value = 1.2
    sym_info.trade_tick_size = 0.01
    sym_info.volume_min = 0.01
    sym_info.volume_step = 0.01
    sym_info.volume_max = 50.0
    mock_mt5.symbol_info.return_value = sym_info
    
    lot, sl_points = risk_manager.calculate_lot_size("XAUUSD", 2400.0, 2410.0)
    assert lot == 0.05
    assert sl_points == 1000.0


def test_calculate_lot_size_percentage():
    """Verify dynamic sizing under 'percentage_risk' sizing mode."""
    config.risk_sizing_mode = "percentage_risk"
    config.risk_percentage = 2.0  # 2% risk
    config.max_allowed_lot_size = 2.0
    
    mock_mt5.initialize.return_value = True
    
    # Mock Account: Balance = $10,000. Risk Amount = $200.
    acc_info = MagicMock()
    acc_info.balance = 10000.0
    acc_info.equity = 10000.0
    mock_mt5.account_info.return_value = acc_info
    
    # Mock Symbol Info: XAUUSD. Point = 0.01, Tick Value = 1.2, Tick Size = 0.01.
    sym_info = MagicMock()
    sym_info.point = 0.01
    sym_info.trade_tick_value = 1.2
    sym_info.trade_tick_size = 0.01
    sym_info.volume_min = 0.01
    sym_info.volume_step = 0.01
    sym_info.volume_max = 50.0
    mock_mt5.symbol_info.return_value = sym_info
    
    # SL distance = $10 (1000 points)
    # SL Points = 10.00 / 0.01 = 1000
    # Formula: Risk_Amt / ((SL_points * (tick_val / tick_sz)) * tick_sz)
    # = 200 / ((1000 * (1.2 / 0.01)) * 0.01) = 200 / (1000 * 120 * 0.01) = 200 / 1200 = 0.1667 lots
    # Rounded down to step size 0.01 -> 0.16 lots
    lot, sl_points = risk_manager.calculate_lot_size("XAUUSD", 2390.0, 2400.0)
    assert lot == 0.16
    assert sl_points == 1000.0


def test_calculate_lot_size_max_clamp():
    """Verify that lot sizing is correctly clamped to the safety ceiling."""
    config.risk_sizing_mode = "percentage_risk"
    config.risk_percentage = 10.0  # 10% risk
    config.max_allowed_lot_size = 0.5  # Max allowed limit set low
    
    acc_info = MagicMock()
    acc_info.balance = 10000.0
    mock_mt5.account_info.return_value = acc_info
    
    sym_info = MagicMock()
    sym_info.point = 0.01
    sym_info.trade_tick_value = 1.0
    sym_info.trade_tick_size = 0.01
    sym_info.volume_min = 0.01
    sym_info.volume_step = 0.01
    sym_info.volume_max = 50.0
    mock_mt5.symbol_info.return_value = sym_info
    
    # 10% of 10000 is 1000. SL distance is 100 points.
    # Calculation: 1000 / (100 * 1.0) = 10 lots.
    # But max_allowed_lot_size is 0.5. Should clamp to 0.5.
    lot, _ = risk_manager.calculate_lot_size("XAUUSD", 2399.0, 2400.0)
    assert lot == 0.5


def test_build_tp_vector_fallback():
    """Verify TP vector generation and fallback multi-step additions."""
    mock_mt5.initialize.return_value = True
    sym_info = MagicMock()
    sym_info.digits = 2
    sym_info.point = 0.01
    mock_mt5.symbol_info.return_value = sym_info
    
    config.fallback_multi_tp_step = 20.0  # 20 pips step
    
    # In Gold, 20 pips = 2.0 USD (since 1 pip = 0.1 points = 0.1 USD)
    # Buy signal with only 1 TP (TP1 = 2420.0)
    # TP2 = 2420.0 + 2.0 = 2422.0
    # TP3 = 2422.0 + 2.0 = 2424.0
    tps = risk_manager.build_tp_vector(
        entry_price=2400.0,
        sl_price=2390.0,
        tp_parsed_list=[2420.0],
        action="BUY",
        symbol="XAUUSD"
    )
    assert tps == [2420.0, 2422.0, 2424.0]
    
    # Sell signal with only 1 TP (TP1 = 2380.0)
    tps_sell = risk_manager.build_tp_vector(
        entry_price=2400.0,
        sl_price=2410.0,
        tp_parsed_list=[2380.0],
        action="SELL",
        symbol="XAUUSD"
    )
    assert tps_sell == [2380.0, 2378.0, 2376.0]


def test_calculate_tp_volume_slices():
    """Verify that lot size splitting matches the UI split allocations."""
    config.tp1_allocation = 50.0
    config.tp2_allocation = 30.0
    config.tp3_allocation = 20.0
    
    sym_info = MagicMock()
    sym_info.volume_min = 0.01
    sym_info.volume_step = 0.01
    mock_mt5.symbol_info.return_value = sym_info
    
    # Split 1.0 lots: 0.50, 0.30, 0.20
    v1, v2, v3 = risk_manager.calculate_tp_volume_slices(1.0, "XAUUSD")
    assert v1 == 0.50
    assert v2 == 0.30
    assert v3 == 0.20
    assert round(v1 + v2 + v3, 2) == 1.0
    
    # Split tiny amount 0.05 lots
    # 0.05 * 50% = 0.025 -> 0.02
    # 0.05 * 30% = 0.015 -> 0.01
    # 0.05 * 20% = 0.010 -> 0.01
    # Sum: 0.04. Diff: 0.01 adjusted to TP1 -> 0.03, 0.01, 0.01
    v1, v2, v3 = risk_manager.calculate_tp_volume_slices(0.05, "XAUUSD")
    assert v1 == 0.03
    assert v2 == 0.01
    assert v3 == 0.01
    assert round(v1 + v2 + v3, 2) == 0.05


@pytest.mark.asyncio
async def test_validate_preflight_success():
    """Verify validate_preflight allows signals when conditions are met."""
    mock_mt5.initialize.return_value = True
    mock_mt5.positions_get.return_value = []  # No open positions
    
    # Mock Account: Equity = balance. Drawdown = 0%
    acc_info = MagicMock()
    acc_info.equity = 10000.0
    mock_mt5.account_info.return_value = acc_info
    
    config.max_concurrent_open_trades = 5
    config.max_daily_drawdown_percent = 5.0
    
    is_valid, reason = await risk_manager.validate_preflight("channel_ok")
    assert is_valid is True
    assert reason == ""


@pytest.mark.asyncio
async def test_validate_preflight_max_positions():
    """Verify rejection when max concurrent positions limit is exceeded."""
    mock_mt5.initialize.return_value = True
    # Mock 5 open positions
    mock_mt5.positions_get.return_value = [MagicMock()] * 5
    
    config.max_concurrent_open_trades = 5
    
    is_valid, reason = await risk_manager.validate_preflight("channel_max_pos")
    assert is_valid is False
    assert "Max concurrent open trades limit" in reason


@pytest.mark.asyncio
async def test_validate_preflight_drawdown():
    """Verify rejection when account exceeds daily drawdown limit."""
    mock_mt5.initialize.return_value = True
    mock_mt5.positions_get.return_value = []
    
    # Set high equity reference to $10,000
    risk_manager.update_daily_high_equity(10000.0)
    
    # Current equity dropped to $9,400 (6.0% drawdown)
    acc_info = MagicMock()
    acc_info.equity = 9400.0
    mock_mt5.account_info.return_value = acc_info
    
    config.max_daily_drawdown_percent = 5.0
    
    is_valid, reason = await risk_manager.validate_preflight("channel_drawdown")
    assert is_valid is False
    assert "Max daily drawdown percentage limit" in reason


@pytest.mark.asyncio
async def test_validate_preflight_paused_channel():
    """Verify rejection when a channel is paused due to loss streak."""
    channel = "paused_streak_channel"
    magic = await risk_manager.get_or_create_magic_number(channel)
    await risk_manager.set_channel_paused(magic, True)
    
    is_valid, reason = await risk_manager.validate_preflight(channel)
    assert is_valid is False
    assert "is currently paused due to consecutive loss streak" in reason


@pytest.mark.asyncio
async def test_closed_deals_sync_consecutive_losses():
    """Verify deals synchronizer calculates streak stats and flags pauses."""
    mock_mt5.initialize.return_value = True
    
    # Map a channel to magic number 1000999
    channel_name = "test_losses_channel"
    magic = 1000999
    
    # Force DB record
    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO channels (channel_name, magic_number, paused, consecutive_losses) VALUES (?, ?, 0, 0)",
        (channel_name, magic)
    )
    conn.commit()
    conn.close()
    
    # Mock closed deals history: 5 consecutive losing deals
    # DEAL_ENTRY_OUT indicates trade closing
    mock_deals = []
    for i in range(5):
        deal = MagicMock()
        deal.entry = 1  # DEAL_ENTRY_OUT (represented as 1 in MT5)
        deal.magic = magic
        deal.profit = -25.0
        deal.commission = -1.0
        deal.swap = 0.0
        deal.time = 1000 + i
        mock_deals.append(deal)
        
    mock_mt5.DEAL_ENTRY_OUT = 1
    mock_mt5.history_deals_get.return_value = mock_deals
    
    config.auto_pause_loss_streak_threshold = 5
    
    # Run the synchronizer logic (extract the core portion normally in the loop)
    # We call run_closed_deals_sync as a task, but since it has a while True,
    # let's mock asyncio.sleep to execute once and then raise CancelledError.
    with patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError()]):
        try:
            await risk_manager.run_closed_deals_sync()
        except asyncio.CancelledError:
            pass
            
    # Query fresh database record
    status = await risk_manager.get_channel_status(channel_name)
    assert status["paused"] is True
    assert status["consecutive_losses"] == 0
