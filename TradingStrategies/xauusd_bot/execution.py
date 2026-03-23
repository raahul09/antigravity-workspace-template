"""Execution module bridging signals to real MT5 Market Orders.

Manages dynamic lot sizing based on account equity and 1% risk caps, and 
handles Stop Loss, Take Profit routing directly into the MT5 terminal.
"""

import MetaTrader5 as mt5
import logging
from typing import Optional

from bot_config import config

logger = logging.getLogger(__name__)

def get_dynamic_lot_size(sl_distance_points: float) -> float:
    """Calculate the lot size ensuring we risk exactly the maximum configured percent (e.g., 1%).
    
    Args:
        sl_distance_points (float): Distance in points from entry to Stop Loss.
        
    Returns:
        float: Calculated lot size adjusted to broker parameters.
    """
    account_info = mt5.account_info()
    if account_info is None:
        logger.error("Failed to retrieve account info for lot calculation")
        return 0.01

    equity = account_info.equity
    risk_amount = equity * (config.max_risk_per_trade_percent / 100)
    
    # 1 standard lot of XAUUSD is typically 100 oz. 1 point move (e.g., 2000.00 to 2000.01)
    # usually equals $1 per lot (varies by broker). We use symbol_info to get precise tick value.
    symbol_info = mt5.symbol_info(config.symbol)
    if not symbol_info:
        return 0.01
        
    tick_value = symbol_info.trade_tick_value
    tick_size = symbol_info.trade_tick_size
    
    if sl_distance_points == 0 or tick_size == 0:
        return symbol_info.volume_min

    # Calculate lot size
    # Risk Amount = Lot Size * (SL Distance / Tick Size) * Tick Value
    # Lot Size = Risk Amount / ((SL Distance / Tick Size) * Tick Value)
    raw_lot = risk_amount / ((sl_distance_points / tick_size) * tick_value)
    
    # Floor to nearest volume step
    step = symbol_info.volume_step
    lot_size = (raw_lot // step) * step
    
    # Clamp to min/max
    lot_size = max(symbol_info.volume_min, min(lot_size, symbol_info.volume_max))
    return round(lot_size, 2)

def execute_market_order(direction: int, stop_loss: float, current_price: float) -> Optional[int]:
    """Execute a market order on MT5.
    
    Args:
        direction (int): 1 for BUY, -1 for SELL.
        stop_loss (float): Exact price level of the Stop Loss.
        current_price (float): The current Ask (for buy) or Bid (for sell).
        
    Returns:
        Optional[int]: The Order Ticket ID if successful, otherwise None.
    """
    sl_distance = abs(current_price - stop_loss)
    lot_size = get_dynamic_lot_size(sl_distance)
    
    # Calculate Take Profit based on configured R:R target
    if direction == 1:
        order_type = mt5.ORDER_TYPE_BUY
        tp = current_price + (sl_distance * config.reward_to_risk_target)
    else:
        order_type = mt5.ORDER_TYPE_SELL
        tp = current_price - (sl_distance * config.reward_to_risk_target)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": config.symbol,
        "volume": lot_size,
        "type": order_type,
        "price": current_price,
        "sl": stop_loss,
        "tp": tp,
        "deviation": config.max_slippage_points,
        "magic": config.magic_number,
        "comment": "SMC Bot Sweep",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"Order failed. Err code: {result.retcode}")
        return None
        
    logger.info(f"Order {result.order} successful. Lot: {lot_size}, SL: {stop_loss}, TP: {tp}")
    return result.order
