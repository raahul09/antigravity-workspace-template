"""Execution engine for MetaTrader 5 trading orders.

Handles login, session management, dynamic lot sizing, and sending market/pending 
orders to MT5 using the MetaTrader5 Python library.
"""

import sys
import logging
from typing import Optional, Dict, Any

# MT5 package is only importable on Windows, mock/protect it for test runs
try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from config import config

logger = logging.getLogger(__name__)


def initialize_mt5() -> bool:
    """Initialize connection to MetaTrader 5 terminal.

    Returns:
        bool: True if connection successful, False otherwise.
    """
    if mt5 is None:
        logger.error("MetaTrader5 package is not available (Windows only)")
        return False

    # Try initializing using configured credentials
    init_args = {}
    if config.mt5_login:
        init_args["login"] = config.mt5_login
    if config.mt5_password:
        init_args["password"] = config.mt5_password
    if config.mt5_server:
        init_args["server"] = config.mt5_server

    logger.info("Initializing MT5 connection...")
    if not mt5.initialize(**init_args):
        logger.error(f"mt5.initialize() failed. Error code: {mt5.last_error()}")
        return False

    # Check terminal connection status
    terminal_info = mt5.terminal_info()
    if terminal_info is None:
        logger.error("Failed to retrieve terminal info")
        mt5.shutdown()
        return False

    logger.info(f"Connected to terminal: {terminal_info.name} ({'Demo' if terminal_info.trade_allowed == 0 else 'Live'})")
    return True


def shutdown_mt5() -> None:
    """Disconnect and shutdown MetaTrader 5 connection."""
    if mt5 is not None:
        logger.info("Shutting down MT5 connection...")
        mt5.shutdown()


def calculate_lot_size(symbol: str, sl_distance_points: float, risk_percent: float) -> float:
    """Calculate volume (lot size) to risk exactly the specified percentage of equity.

    Args:
        symbol: The trading symbol.
        sl_distance_points: Distance from entry to Stop Loss in points.
        risk_percent: Percentage of account equity to risk.

    Returns:
        float: Volume (lot size) to execute. Returns volume_min if calculation fails.
    """
    if mt5 is None:
        return 0.01

    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        logger.error(f"Cannot get symbol info for {symbol}")
        return 0.01

    account_info = mt5.account_info()
    if not account_info:
        logger.error("Cannot get account info for lot size calculation")
        return symbol_info.volume_min

    # Risk amount in account currency (usually USD)
    equity = account_info.equity
    risk_amount = equity * (risk_percent / 100.0)

    tick_value = symbol_info.trade_tick_value
    tick_size = symbol_info.trade_tick_size

    if sl_distance_points == 0 or tick_size == 0 or tick_value == 0:
        return symbol_info.volume_min

    # Calculate lot size:
    # Lot Size = Risk Amount / ((SL Distance / Tick Size) * Tick Value)
    raw_lot = risk_amount / ((sl_distance_points / tick_size) * tick_value)

    # Round to volume step
    step = symbol_info.volume_step
    lot_size = (raw_lot // step) * step
    
    # Clamp between min and max volume allowed by broker
    lot_size = max(symbol_info.volume_min, min(lot_size, symbol_info.volume_max))
    
    return round(lot_size, 2)


def execute_signal(signal: Dict[str, Any]) -> Optional[int]:
    """Execute a parsed trading signal on MetaTrader 5.

    Args:
        signal: Dictionary containing:
            - action: "BUY" or "SELL"
            - symbol: str (e.g. "XAUUSD")
            - entry: float or None
            - sl: float
            - tp: float or None

    Returns:
        Optional[int]: Order ticket number if successful, None otherwise.
    """
    if mt5 is None:
        logger.error("Cannot execute trade: MetaTrader5 library is not loaded")
        return None

    symbol = signal["symbol"]

    # 1. Enable symbol visibility in Market Watch
    if not mt5.symbol_select(symbol, True):
        logger.error(f"Symbol {symbol} is not available on this broker/server")
        return None

    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        logger.error(f"Failed to fetch symbol info for {symbol}")
        return None

    # Get current price
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        logger.error(f"Failed to get current tick for {symbol}")
        return None

    current_ask = tick.ask
    current_bid = tick.bid
    digits = symbol_info.digits
    point = symbol_info.point

    # 2. Determine Order execution type and entry price
    target_entry = signal["entry"]
    action = signal["action"]
    
    # Threshold to determine if entry price is close enough to execute at market
    # (within 15 points / pips tolerance)
    market_tolerance = 15 * point
    
    is_market = False
    if target_entry is None:
        is_market = True
    else:
        # Check if requested entry is very close to current price
        current_ref = current_ask if action == "BUY" else current_bid
        if abs(target_entry - current_ref) <= market_tolerance:
            is_market = True

    # Define order parameters
    sl_price = round(signal["sl"], digits)
    tp_price = round(signal["tp"], digits) if signal.get("tp") else 0.0

    if is_market:
        # Market execution
        entry_price = current_ask if action == "BUY" else current_bid
        order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
        action_type = mt5.TRADE_ACTION_DEAL
        logger.info(f"Preparing MARKET {action} order for {symbol} at {entry_price}")
    else:
        # Pending execution
        entry_price = round(target_entry, digits)
        action_type = mt5.TRADE_ACTION_PENDING
        
        # Decide pending type (Limit vs Stop)
        if action == "BUY":
            if entry_price < current_ask:
                order_type = mt5.ORDER_TYPE_BUY_LIMIT
                type_name = "BUY LIMIT"
            else:
                order_type = mt5.ORDER_TYPE_BUY_STOP
                type_name = "BUY STOP"
        else: # SELL
            if entry_price > current_bid:
                order_type = mt5.ORDER_TYPE_SELL_LIMIT
                type_name = "SELL LIMIT"
            else:
                order_type = mt5.ORDER_TYPE_SELL_STOP
                type_name = "SELL STOP"
        logger.info(f"Preparing PENDING {type_name} order for {symbol} at {entry_price}")

    # 3. Calculate Risk & Lot Size
    sl_distance = abs(entry_price - sl_price)
    sl_points = sl_distance / point

    lot_size = calculate_lot_size(symbol, sl_points, config.default_risk_percent)
    logger.info(f"Lot size calculated: {lot_size} lots (Risking {config.default_risk_percent}% with SL distance {sl_points:.1f} points)")

    # 4. Construct Order Request
    request = {
        "action": action_type,
        "symbol": symbol,
        "volume": lot_size,
        "type": order_type,
        "price": entry_price,
        "sl": sl_price,
        "deviation": 20,
        "magic": config.magic_number,
        "comment": f"TG Signal ({signal['parser']})",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC if is_market else mt5.ORDER_TIME_GTC,
    }

    if tp_price > 0:
        request["tp"] = tp_price

    # 5. Send order to MT5
    logger.info(f"Sending order request: {action} {lot_size} {symbol} SL:{sl_price} TP:{tp_price}")
    result = mt5.order_send(request)

    if result is None:
        logger.error("mt5.order_send returned None. Terminal may be frozen.")
        return None

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"Trade execution failed! Return code: {result.retcode} ({mt5.last_error()})")
        return None

    logger.info(f"Order executed successfully! Ticket: {result.order}. Position volume: {result.volume}")
    return result.order
