"""Tests for the Telegram Signal Parser.

Verifies that the regex parsing engine handles standard and slightly messy 
signal strings, normalizes symbols, and correctly rejects non-signal messages.
"""

import sys
import pytest
from pathlib import Path

# Provide access to the telegram_to_mt5_bot modules
current_dir = Path(__file__).resolve().parent
bot_dir = current_dir.parent / 'telegram_to_mt5_bot'
if str(bot_dir) not in sys.path:
    sys.path.insert(0, str(bot_dir))

from parser import parse_signal, clean_symbol


def test_clean_symbol():
    """Verify that common gold and silver names are normalized correctly."""
    assert clean_symbol("gold") == "XAUUSD"
    assert clean_symbol("XAUUSD") == "XAUUSD"
    assert clean_symbol("XAUUSD.pro") == "XAUUSD"
    assert clean_symbol("EURUSD") == "EURUSD"
    assert clean_symbol("eur/usd") == "EURUSD"
    assert clean_symbol("silver") == "XAGUSD"


def test_parse_buy_signal():
    """Test parsing a standard structured BUY signal."""
    message = (
        "BUY GOLD\n"
        "Entry: 2420.50\n"
        "SL: 2410.00\n"
        "TP: 2440.00"
    )
    result = parse_signal(message)
    
    assert result is not None
    assert result["action"] == "BUY"
    assert result["symbol"] == "XAUUSD"
    assert result["entry"] == 2420.50
    assert result["sl"] == 2410.00
    assert result["tp"] == 2440.00


def test_parse_sell_signal():
    """Test parsing a standard structured SELL signal."""
    message = (
        "SELL EURUSD @ 1.0850\n"
        "Stop Loss: 1.0900\n"
        "Take Profit: 1.0750"
    )
    result = parse_signal(message)
    
    assert result is not None
    assert result["action"] == "SELL"
    assert result["symbol"] == "EURUSD"
    assert result["entry"] == 1.0850
    assert result["sl"] == 1.0900
    assert result["tp"] == 1.0750


def test_parse_variations():
    """Test parsing signals with messy formatting or different syntax."""
    # Messy text with multiple spaces, different cases, and no entry price
    msg1 = "long gold sl=2395.5 tp=2450.0"
    res1 = parse_signal(msg1)
    
    assert res1 is not None
    assert res1["action"] == "BUY"
    assert res1["symbol"] == "XAUUSD"
    assert res1["entry"] is None
    assert res1["sl"] == 2395.5
    assert res1["tp"] == 2450.0

    # Message with TP1 and no entry price, using newlines
    msg2 = (
        "sell XAU/USD\n"
        "STOP LOSS: 2435\n"
        "TP1: 2380"
    )
    res2 = parse_signal(msg2)
    assert res2 is not None
    assert res2["action"] == "SELL"
    assert res2["symbol"] == "XAUUSD"
    assert res2["sl"] == 2435.0
    assert res2["tp"] == 2380.0

    # Message matching user's exact signal formatting (stoploss/tp with no spaces, fallback symbol)
    msg3 = (
        "sell  4571 \n"
        "stoploss 4575\n"
        "tp 4568"
    )
    res3 = parse_signal(msg3)
    assert res3 is not None
    assert res3["action"] == "SELL"
    assert res3["symbol"] == "XAUUSD"
    assert res3["entry"] == 4571.0
    assert res3["sl"] == 4575.0
    assert res3["tp"] == 4568.0


def test_invalid_messages_ignored():
    """Verify that messages without trading signals are ignored (returns None)."""
    # Random conversational text
    assert parse_signal("Hello everyone, how is trading going today?") is None
    
    # Message with action and symbol, but missing mandatory Stop Loss
    assert parse_signal("BUY XAUUSD at 2400.00, looking for targets!") is None


def test_sl_tp_combinations():
    """Verify various spelling and formatting combinations for SL and TP."""
    # Test s.l. and target
    msg = "buy gold entry: 2400 s.l. 2390 target 2420"
    res = parse_signal(msg)
    assert res is not None
    assert res["sl"] == 2390.0
    assert res["tp"] == 2420.0

    # Test stop-loss and take-profit
    msg = "sell gold stop-loss 2450 take-profit 2410"
    res = parse_signal(msg)
    assert res is not None
    assert res["sl"] == 2450.0
    assert res["tp"] == 2410.0

    # Test invalidation and profit
    msg = "buy gold invalid: 2380 profit 2430"
    res = parse_signal(msg)
    assert res is not None
    assert res["sl"] == 2380.0
    assert res["tp"] == 2430.0


def test_mrsimpletrader_signals():
    """Verify parsing of signals containing commas in prices and parenthesis around keywords (like mrsimpletrader style)."""
    message = (
        "XAUUSD (GOLD) SELL SETUP\n"
        "Based on the 1-minute chart, we have a clean bearish rejection and a break out.\n"
        "Entry Price: 4,527.62\n"
        "Stop Loss (SL): 4,531.26 (36 Pips)\n"
        "Target (TP): 4,517.45 (101 Pips)\n"
        "Risk/Reward: 1:2.8"
    )
    res = parse_signal(message)
    assert res is not None
    assert res["action"] == "SELL"
    assert res["symbol"] == "XAUUSD"
    assert res["entry"] == 4527.62
    assert res["sl"] == 4531.26
    assert res["tp"] == 4517.45


def test_customizable_keywords():
    """Verify that parsing works correctly when keywords are customized in config."""
    from config import config
    
    # Save original keywords
    orig_sl = config.sl_keywords
    orig_tp = config.tp_keywords
    orig_entry = config.entry_keywords
    
    try:
        # Customize keywords
        config.sl_keywords = "INVALID_AT,EXIT"
        config.tp_keywords = "TARGET_LEVEL"
        config.entry_keywords = "START_PRICE"
        
        message = (
            "BUY XAUUSD\n"
            "START_PRICE: 2400.00\n"
            "INVALID_AT: 2390.00\n"
            "TARGET_LEVEL: 2420.00"
        )
        res = parse_signal(message)
        assert res is not None
        assert res["entry"] == 2400.0
        assert res["sl"] == 2390.0
        assert res["tp"] == 2420.0
    finally:
        # Restore original keywords
        config.sl_keywords = orig_sl
        config.tp_keywords = orig_tp
        config.entry_keywords = orig_entry


