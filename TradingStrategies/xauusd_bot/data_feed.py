"""Data feed and MT5 connection management module.

Handles connection to the MetaTrader 5 terminal and continuous retrieval 
of tick and candlestick data for the specified symbol across multiple timeframes.
"""

import MetaTrader5 as mt5
import pandas as pd
from typing import Optional, Union
import logging

from bot_config import config

logger = logging.getLogger(__name__)

def initialize_mt5() -> bool:
    """Initialize the connection to the MetaTrader 5 terminal.
    
    Returns:
        bool: True if connection is successful, False otherwise.
    """
    if not mt5.initialize():
        logger.error(f"MT5 initialization failed. Error code: {mt5.last_error()}")
        return False
        
    # Attempt to login if credentials are provided in the config
    if config.mt5_login and config.mt5_password and config.mt5_server:
        authorized = mt5.login(
            login=config.mt5_login, 
            password=config.mt5_password, 
            server=config.mt5_server
        )
        if not authorized:
            logger.error(f"MT5 login failed. Error code: {mt5.last_error()}")
            return False
            
    logger.info("Successfully connected to MetaTrader 5.")
    return True

def shutdown_mt5() -> None:
    """Gracefully shutdown the MetaTrader 5 connection."""
    mt5.shutdown()
    logger.info("MT5 connection closed.")

def get_historical_candles(timeframe: int, count: int = 100) -> Optional[pd.DataFrame]:
    """Fetch historical candlestick data for the configured symbol.
    
    Args:
        timeframe (int): The MT5 timeframe constant (e.g., mt5.TIMEFRAME_M1).
        count (int): The number of recent candles to retrieve.
        
    Returns:
        Optional[pd.DataFrame]: A DataFrame containing formatting OHLCV data, 
        or None if the fetch fails.
    """
    rates = mt5.copy_rates_from_pos(config.symbol, timeframe, 0, count)
    
    if rates is None or len(rates) == 0:
        logger.warning(f"Failed to fetch data for {config.symbol} on timeframe {timeframe}. Error: {mt5.last_error()}")
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

def get_1m_candles(count: int = 100) -> Optional[pd.DataFrame]:
    """Fetch 1-minute (M1) candles."""
    return get_historical_candles(mt5.TIMEFRAME_M1, count)

def get_5m_candles(count: int = 100) -> Optional[pd.DataFrame]:
    """Fetch 5-minute (M5) candles."""
    return get_historical_candles(mt5.TIMEFRAME_M5, count)

def get_15m_candles(count: int = 100) -> Optional[pd.DataFrame]:
    """Fetch 15-minute (M15) candles."""
    return get_historical_candles(mt5.TIMEFRAME_M15, count)

def get_historical_candles_range(timeframe: int, date_from, date_to) -> Optional[pd.DataFrame]:
    """Fetch candlestick data between two dates.
    
    Args:
        timeframe (int): The MT5 timeframe constant.
        date_from (datetime): Start datetime.
        date_to (datetime): End datetime.
    """
    rates = mt5.copy_rates_range(config.symbol, timeframe, date_from, date_to)
    if rates is None or len(rates) == 0:
        logger.warning(f"Failed to fetch data range. Error: {mt5.last_error()}")
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

def get_current_tick() -> Optional[dict]:
    """Fetch the latest tick data (Bid/Ask) for the configured symbol.
    
    Returns:
        Optional[dict]: A dictionary representing the tick data, or None on failure.
    """
    tick = mt5.symbol_info_tick(config.symbol)
    if tick is None:
        logger.warning(f"Failed to fetch tick for {config.symbol}. Error: {mt5.last_error()}")
        return None
    return tick._asdict()
