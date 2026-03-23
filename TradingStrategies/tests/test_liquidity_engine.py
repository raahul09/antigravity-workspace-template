"""Tests for the Liquidity Engine (SMC Logic).

These tests run entirely offline using mock pandas DataFrames to ensure the 
sweep detection logic is watertight before ever connecting to MT5.
"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Provide access to the bot modules
current_dir = Path(__file__).resolve().parent
xauusd_bot_dir = current_dir.parent / 'xauusd_bot'
if str(xauusd_bot_dir) not in sys.path:
    sys.path.insert(0, str(xauusd_bot_dir))

from liquidity_engine import LiquidityEngine

@pytest.fixture
def sample_15m_data():
    """Create a mock 15M DataFrame representing a distinct swing high and low."""
    dates = pd.date_range("2026-01-01 00:00", periods=20, freq="15min")
    
    # Create simple mock data: a clear peak in the middle for a Swing High
    highs = np.linspace(2000, 2010, 10).tolist() + np.linspace(2009, 2000, 10).tolist()
    # Create a clear trough for a Swing Low
    lows = np.linspace(1990, 1980, 10).tolist() + np.linspace(1982, 1990, 10).tolist()
    
    df = pd.DataFrame({
        'open': np.array(lows) + 1,
        'high': highs,
        'low': lows,
        'close': np.array(lows) + 2
    }, index=dates)
    return df

@pytest.fixture
def engine():
    return LiquidityEngine(swing_lookback=3)

def test_find_15m_swing_points(engine, sample_15m_data):
    """Test that the engine successfully locates the mocked swing high/low."""
    engine.find_15m_swing_points(sample_15m_data)
    
    assert len(engine.active_swing_highs) > 0, "Failed to detect Swing High"
    assert engine.active_swing_highs[0]['price'] == 2010.0, "Incorrect Swing High detected"
    
    assert len(engine.active_swing_lows) > 0, "Failed to detect Swing Low"
    assert engine.active_swing_lows[0]['price'] == 1980.0, "Incorrect Swing Low detected"

def test_bearish_sweep_detection(engine, sample_15m_data):
    """Test detection of a Bearish Liquidity Sweep (price breaks high, then closes lower)."""
    engine.find_15m_swing_points(sample_15m_data)
    
    # Mocking 1M data where price swept above 2010 to 2012, then reversed.
    dates_1m = pd.date_range("2026-01-01 04:00", periods=5, freq="1min")
    df_1m = pd.DataFrame({
        'open': [2008, 2010, 2011, 2010, 2009],
        'high': [2009, 2012, 2012, 2011, 2009], # Max is 2012 (the sweep)
        'low': [2007, 2009, 2010, 2008, 2007],
        'close': [2009, 2011, 2010, 2009, 2008]
    }, index=dates_1m)
    
    # Current price has broken back down under the 2010 swing high
    current_price = 2008.5
    
    setup = engine.detect_liquidity_sweep(current_price, df_1m)
    
    assert setup is not None, "Failed to detect valid bearish sweep"
    assert setup['direction'] == -1, "Expected Sell (-1) direction"
    assert setup['stop_loss'] == 2012.0, "Stop Loss should be exactly above the 1M sweep high"
