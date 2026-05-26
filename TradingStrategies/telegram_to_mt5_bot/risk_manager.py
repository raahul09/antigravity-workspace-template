"""Risk Management and Interceptor Middleware.

Manages position sizing, Take Profit splitting, pre-flight circuit breakers,
and asynchronous monitoring of active positions and historical deals.
"""

import os
import sqlite3
import logging
import asyncio
import datetime
from typing import Dict, Any, List, Optional, Tuple

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from config import config

logger = logging.getLogger(__name__)

DB_PATH = "risk_management.db"
db_lock = asyncio.Lock()

# Global in-memory state for daily drawdown tracking
daily_high_equity: float = 0.0
last_high_reset_date: Optional[datetime.date] = None


def init_db() -> None:
    """Initialize the SQLite database schema if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        # Channels table: stores magic number mapping and performance stats
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_name TEXT UNIQUE,
                magic_number INTEGER UNIQUE,
                paused INTEGER DEFAULT 0,
                consecutive_losses INTEGER DEFAULT 0,
                consecutive_wins INTEGER DEFAULT 0
            )
        """)
        
        # Tracked orders table: for partial closes and auto break-even monitoring
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracked_orders (
                ticket_id INTEGER PRIMARY KEY,
                channel_name TEXT,
                magic_number INTEGER,
                symbol TEXT,
                action TEXT,
                entry_price REAL,
                sl REAL,
                tp1 REAL,
                tp2 REAL,
                tp3 REAL,
                tp1_vol REAL,
                tp2_vol REAL,
                tp3_vol REAL,
                tp1_hit INTEGER DEFAULT 0,
                tp2_hit INTEGER DEFAULT 0,
                tp3_hit INTEGER DEFAULT 0,
                volume_remaining REAL,
                is_active INTEGER DEFAULT 1
            )
        """)
        conn.commit()
    except Exception as e:
        logger.error(f"Error initializing risk database: {e}")
    finally:
        conn.close()


# Initialize database schema at import time
init_db()


async def get_or_create_magic_number(channel_name: str) -> int:
    """Get the persistent magic number for a channel name, or create one.

    Magic numbers start at 1000000 + increment.

    Args:
        channel_name: Unique Telegram channel identifier.

    Returns:
        int: Unique magic number assigned.
    """
    async with db_lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT magic_number FROM channels WHERE channel_name = ?", (channel_name,))
            row = cursor.fetchone()
            if row:
                return row[0]
            
            # Find next magic number
            cursor.execute("SELECT MAX(magic_number) FROM channels")
            max_magic = cursor.fetchone()[0]
            next_magic = 1000001 if max_magic is None else max_magic + 1
            
            cursor.execute(
                "INSERT INTO channels (channel_name, magic_number) VALUES (?, ?)",
                (channel_name, next_magic)
            )
            conn.commit()
            logger.info(f"Assigned magic number {next_magic} to new channel source '{channel_name}'")
            return next_magic
        except Exception as e:
            logger.error(f"Error managing channel magic numbers: {e}")
            # Fall back to base config magic number if DB fails
            return config.magic_number
        finally:
            conn.close()


async def get_channel_status(channel_name: str) -> Dict[str, Any]:
    """Retrieve current stats and pause state for a channel.

    Args:
        channel_name: Unique Telegram channel identifier.

    Returns:
        Dict: Channel parameters.
    """
    async with db_lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT magic_number, paused, consecutive_losses, consecutive_wins FROM channels WHERE channel_name = ?",
                (channel_name,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "channel_name": channel_name,
                    "magic_number": row[0],
                    "paused": bool(row[1]),
                    "consecutive_losses": row[2],
                    "consecutive_wins": row[3]
                }
            return {
                "channel_name": channel_name,
                "magic_number": None,
                "paused": False,
                "consecutive_losses": 0,
                "consecutive_wins": 0
            }
        finally:
            conn.close()


async def set_channel_paused(magic_number: int, paused: bool) -> bool:
    """Manually pause or unpause a channel.

    Args:
        magic_number: Persistent magic number identifier.
        paused: True to pause, False to unpause.

    Returns:
        bool: True if successful, False otherwise.
    """
    async with db_lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE channels SET paused = ?, consecutive_losses = 0 WHERE magic_number = ?",
                (1 if paused else 0, magic_number)
            )
            conn.commit()
            logger.info(f"Channel {magic_number} pause status updated to: {paused}")
            return True
        except Exception as e:
            logger.error(f"Error resetting channel: {e}")
            return False
        finally:
            conn.close()


async def get_all_channels() -> List[Dict[str, Any]]:
    """Get all channels stored in the database.

    Returns:
        List[Dict]: List of channels statistics.
    """
    async with db_lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT channel_name, magic_number, paused, consecutive_losses, consecutive_wins FROM channels")
            rows = cursor.fetchall()
            return [
                {
                    "channel_name": row[0],
                    "magic_number": row[1],
                    "paused": bool(row[2]),
                    "consecutive_losses": row[3],
                    "consecutive_wins": row[4]
                } for row in rows
            ]
        except Exception as e:
            logger.error(f"Error loading channels list: {e}")
            return []
        finally:
            conn.close()


def update_daily_high_equity(equity: float) -> float:
    """Update and return the daily high water mark for drawdown calculation."""
    global daily_high_equity, last_high_reset_date
    today = datetime.date.today()
    if last_high_reset_date is None or last_high_reset_date != today:
        daily_high_equity = equity
        last_high_reset_date = today
        logger.info(f"Resetting daily high equity water mark to: {equity}")
    elif equity > daily_high_equity:
        daily_high_equity = equity
        logger.info(f"Updating daily high equity water mark to: {equity}")
    return daily_high_equity


def get_current_drawdown_percent() -> float:
    """Calculate the current daily drawdown percentage."""
    if mt5 is None or not mt5.initialize():
        return 0.0
    acc = mt5.account_info()
    if acc is None:
        return 0.0
    
    update_daily_high_equity(acc.equity)
    if daily_high_equity <= 0:
        return 0.0
    
    drawdown = (daily_high_equity - acc.equity) / daily_high_equity * 100.0
    return max(0.0, drawdown)


# =====================================================================
# INTERCEPTOR logic
# =====================================================================

async def validate_preflight(channel_source: str) -> Tuple[bool, str]:
    """Execute Account-Level Pre-Flight Checks before routing.

    Args:
        channel_source: Name or ID of the Telegram channel sending the signal.

    Returns:
        Tuple[bool, str]: (isValid, rejectionReason)
    """
    if mt5 is None:
        return False, "MetaTrader5 package is not available"

    # 1. Check channel pause status
    channel_info = await get_channel_status(channel_source)
    if channel_info["paused"]:
        return False, f"Channel '{channel_source}' is currently paused due to consecutive loss streak"

    # Ensure MT5 is initialized
    if not mt5.initialize():
        return False, "Failed to connect to MetaTrader 5 terminal"

    # 2. Check total active positions in MT5
    positions = mt5.positions_get()
    if positions is not None:
        active_count = len(positions)
        if active_count >= config.max_concurrent_open_trades:
            return False, f"Max concurrent open trades limit ({config.max_concurrent_open_trades}) reached. Active positions: {active_count}"

    # 3. Check current daily drawdown
    drawdown = get_current_drawdown_percent()
    if drawdown >= config.max_daily_drawdown_percent:
        return False, f"Max daily drawdown percentage limit ({config.max_daily_drawdown_percent}%) exceeded. Current drawdown: {drawdown:.2f}%"

    return True, ""


def calculate_lot_size(symbol: str, sl_price: float, entry_price: float) -> Tuple[float, float]:
    """Calculate dynamic position sizing using broker parameters and constraints.

    Formula:
        Total Lots = (Balance * Risk Percentage) / (SL Distance in Points * Tick Value)

    Args:
        symbol: Financial instrument symbol (e.g. XAUUSD).
        sl_price: Parsed stop loss.
        entry_price: Target entry price.

    Returns:
        Tuple[float, float]: (calculated_lot, sl_distance_points)
    """
    if mt5 is None or not mt5.initialize():
        return config.fixed_lot_size, 0.0

    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        logger.error(f"Failed to get symbol info for {symbol}. Using default sizing.")
        return config.fixed_lot_size, 0.0

    point = symbol_info.point
    tick_value = symbol_info.trade_tick_value
    tick_size = symbol_info.trade_tick_size
    min_volume = symbol_info.volume_min
    step_volume = symbol_info.volume_step
    max_volume = symbol_info.volume_max

    sl_distance = abs(entry_price - sl_price)
    sl_points = sl_distance / point if point > 0 else 0.0

    # Ensure safe defaults if data is missing
    if sl_points <= 0:
        return config.fixed_lot_size, 0.0

    if config.risk_sizing_mode == "fixed_lot":
        raw_lot = config.fixed_lot_size
    else:
        # Percentage Risk mode
        acc = mt5.account_info()
        if not acc:
            logger.error("Failed to get MT5 account info. Using default fixed lot sizing.")
            return config.fixed_lot_size, sl_points

        balance = acc.balance
        risk_amount = balance * (config.risk_percentage / 100.0)

        if tick_size <= 0 or tick_value <= 0:
            logger.error(f"Invalid tick size ({tick_size}) or value ({tick_value}) for {symbol}")
            return config.fixed_lot_size, sl_points

        # Sizing calculation based on contract dimensions
        raw_lot = risk_amount / ((sl_points * (tick_value / tick_size)) * tick_size)

    # Normalize lots to contract step size (round down)
    steps = int(raw_lot / step_volume)
    norm_lot = steps * step_volume

    # Clamp lot size between broker constraints and user max lot size ceiling
    max_cap = min(max_volume, config.max_allowed_lot_size)
    norm_lot = max(min_volume, min(norm_lot, max_cap))
    
    # Rounded to standard 2 decimal precision
    final_lot = round(norm_lot, 2)
    return final_lot, sl_points


def build_tp_vector(entry_price: float, sl_price: float, tp_parsed_list: List[float], action: str, symbol: str) -> List[float]:
    """Generates the three Take Profit targets, applying fallback pip step if necessary.

    Args:
        entry_price: Entry price.
        sl_price: Stop loss price.
        tp_parsed_list: List of parsed TPs from signal parser.
        action: "BUY" or "SELL".
        symbol: Financial instrument symbol (to retrieve symbol digits/pip sizes).

    Returns:
        List[float]: Vector containing TP1, TP2, and TP3 levels.
    """
    digits = 2
    point = 0.01
    
    if mt5 is not None and mt5.initialize():
        sym_info = mt5.symbol_info(symbol)
        if sym_info:
            digits = sym_info.digits
            point = sym_info.point

    # Calculate pip size dynamically
    # Forex (5-digit): 1 pip = 0.0001 (10 points)
    # Gold (2-digit/3-digit): 1 pip = 0.1 (10 points)
    is_gold = any(x in symbol.upper() for x in ["XAU", "GOLD"])
    pip_multiplier = 0.1 if is_gold else 0.0001
    
    fallback_step_points = config.fallback_multi_tp_step * (pip_multiplier / point) * point

    # Clean empty lists
    tps = [t for t in tp_parsed_list if t is not None]
    
    if len(tps) == 0:
        # If no TP parsed at all, make a default TP1 based on default SL or 1:1 risk reward
        sl_dist = abs(entry_price - sl_price)
        if action == "BUY":
            tps.append(entry_price + sl_dist)
        else:
            tps.append(entry_price - sl_dist)

    # Auto-generate TP2 and TP3 if only 1 target value is present
    if len(tps) == 1:
        tp1 = tps[0]
        if action == "BUY":
            tp2 = tp1 + fallback_step_points
            tp3 = tp2 + fallback_step_points
        else:
            tp2 = tp1 - fallback_step_points
            tp3 = tp2 - fallback_step_points
        tps.extend([tp2, tp3])
    elif len(tps) == 2:
        tp2 = tps[1]
        if action == "BUY":
            tp3 = tp2 + fallback_step_points
        else:
            tp3 = tp2 - fallback_step_points
        tps.append(tp3)
        
    return [round(tps[0], digits), round(tps[1], digits), round(tps[2], digits)]


def calculate_tp_volume_slices(total_lots: float, symbol: str) -> Tuple[float, float, float]:
    """Splits total lots into three slices based on allocation configurations.

    Ensures broker minimum step constraints and checks that sum of parts equals total.

    Args:
        total_lots: Total calculated position lot size.
        symbol: Trading symbol (to retrieve step size).

    Returns:
        Tuple[float, float, float]: (Lot1, Lot2, Lot3)
    """
    step = 0.01
    min_vol = 0.01
    if mt5 is not None and mt5.initialize():
        sym_info = mt5.symbol_info(symbol)
        if sym_info:
            step = sym_info.volume_step
            min_vol = sym_info.volume_min

    # Calculate raw volume slices
    v1_raw = total_lots * (config.tp1_allocation / 100.0)
    v2_raw = total_lots * (config.tp2_allocation / 100.0)
    v3_raw = total_lots * (config.tp3_allocation / 100.0)

    # Normalize to step sizes (round down)
    v1 = round(int((v1_raw + 1e-9) / step) * step, 2)
    v2 = round(int((v2_raw + 1e-9) / step) * step, 2)
    v3 = round(int((v3_raw + 1e-9) / step) * step, 2)

    # Ensure all are at least min_vol
    v1 = max(min_vol, v1)
    v2 = max(min_vol, v2)
    v3 = max(min_vol, v3)

    # Adjust remaining differences to fit exactly total_lots
    diff = round(total_lots - (v1 + v2 + v3), 2)
    if diff != 0:
        # Adjust TP1 slice
        v1 = round(v1 + diff, 2)
        if v1 < min_vol:
            # Fallback to make sure they sum up to total_lots
            v1 = min_vol
            # If total_lots is too small to split, merge slices
            total_remaining = round(total_lots - v1, 2)
            v2 = max(0.0, round(total_remaining * 0.6, 2))
            v3 = max(0.0, round(total_remaining - v2, 2))

    return round(v1, 2), round(v2, 2), round(v3, 2)


# =====================================================================
# Database operations for Tracking Orders
# =====================================================================

async def add_tracked_order(
    ticket_id: int, channel_name: str, magic_number: int, symbol: str, action: str,
    entry_price: float, sl: float, tps: List[float], vols: List[float]
) -> None:
    """Store order parameters in database for live price tracking."""
    async with db_lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO tracked_orders (
                    ticket_id, channel_name, magic_number, symbol, action,
                    entry_price, sl, tp1, tp2, tp3, tp1_vol, tp2_vol, tp3_vol,
                    volume_remaining, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                ticket_id, channel_name, magic_number, symbol, action,
                entry_price, sl, tps[0], tps[1], tps[2], vols[0], vols[1], vols[2],
                sum(vols)
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Error adding tracked order: {e}")
        finally:
            conn.close()


async def get_active_tracked_orders() -> List[Dict[str, Any]]:
    """Retrieve all open tracked orders for price checks."""
    async with db_lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ticket_id, channel_name, magic_number, symbol, action,
                       entry_price, sl, tp1, tp2, tp3, tp1_vol, tp2_vol, tp3_vol,
                       tp1_hit, tp2_hit, tp3_hit, volume_remaining
                FROM tracked_orders WHERE is_active = 1
            """)
            rows = cursor.fetchall()
            return [
                {
                    "ticket_id": r[0],
                    "channel_name": r[1],
                    "magic_number": r[2],
                    "symbol": r[3],
                    "action": r[4],
                    "entry_price": r[5],
                    "sl": r[6],
                    "tp1": r[7],
                    "tp2": r[8],
                    "tp3": r[9],
                    "tp1_vol": r[10],
                    "tp2_vol": r[11],
                    "tp3_vol": r[12],
                    "tp1_hit": bool(r[13]),
                    "tp2_hit": bool(r[14]),
                    "tp3_hit": bool(r[15]),
                    "volume_remaining": r[16]
                } for r in rows
            ]
        except Exception as e:
            logger.error(f"Error fetching active tracked orders: {e}")
            return []
        finally:
            conn.close()


async def update_tracked_order_tp_hit(ticket_id: int, tp_level: int, remaining_vol: float, set_inactive: bool = False) -> None:
    """Update target tracking parameter in database."""
    async with db_lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            tp_field = f"tp{tp_level}_hit"
            is_active = 0 if set_inactive else 1
            cursor.execute(f"""
                UPDATE tracked_orders 
                SET {tp_field} = 1, volume_remaining = ?, is_active = ? 
                WHERE ticket_id = ?
            """, (remaining_vol, is_active, ticket_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating tracked order: {e}")
        finally:
            conn.close()


async def deactivate_tracked_order(ticket_id: int) -> None:
    """Flag order as inactive (position closed)."""
    async with db_lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE tracked_orders SET is_active = 0 WHERE ticket_id = ?", (ticket_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Error deactivating tracked order: {e}")
        finally:
            conn.close()


# =====================================================================
# ASYNCHRONOUS ENGINE MONITORING LOOP
# =====================================================================

async def run_live_risk_monitor() -> None:
    """Asynchronous background worker loop monitoring live prices and positions.

    - Detects if TP1 is hit -> shifts remaining volumes to Break-Even.
    - Manages Partial Closes for 'single_ticket_partial' execution mode.
    - Synchronizes inactive positions.
    """
    logger.info("Starting Live Risk & Position monitoring thread...")
    while True:
        try:
            if mt5 is None or not mt5.initialize():
                await asyncio.sleep(5)
                continue

            active_tracks = await get_active_tracked_orders()
            if not active_tracks:
                await asyncio.sleep(2)
                continue

            # Query all active positions in MT5 to cross-reference
            mt5_positions = mt5.positions_get()
            active_tickets = {p.ticket: p for p in mt5_positions} if mt5_positions else {}

            for track in active_tracks:
                ticket_id = track["ticket_id"]
                symbol = track["symbol"]
                action = track["action"]
                entry_price = track["entry_price"]
                sl = track["sl"]

                # Case A: Position closed externally (e.g. SL hit or manually closed)
                if ticket_id not in active_tickets:
                    # Double check MT5 deal history to verify if it was actually closed
                    closed_deals = mt5.history_deals_get(position=ticket_id)
                    was_closed = False
                    if closed_deals is not None:
                        for d in closed_deals:
                            if d.entry == mt5.DEAL_ENTRY_OUT:
                                was_closed = True
                                break
                    if was_closed:
                        logger.info(f"Position {ticket_id} no longer active in terminal. Removing from tracking.")
                        await deactivate_tracked_order(ticket_id)
                    else:
                        logger.debug(f"Position {ticket_id} not found in active positions, but no closed deal found in history. Retaining tracking (lag protection).")
                    continue

                position = active_tickets[ticket_id]
                current_price = position.price_current
                current_sl = position.sl
                volume = position.volume

                # Check if TP1 has been hit (Buy price >= TP1 or Sell price <= TP1)
                if not track["tp1_hit"]:
                    tp1_hit = False
                    if action == "BUY" and current_price >= track["tp1"]:
                        tp1_hit = True
                    elif action == "SELL" and current_price <= track["tp1"]:
                        tp1_hit = True

                    if tp1_hit:
                        logger.info(f"Take Profit level 1 ({track['tp1']}) hit for ticket {ticket_id}")
                        
                        # Apply Auto Break-Even if checkbox enabled
                        if config.move_sl_to_be_on_tp1:
                            logger.info(f"Auto Break-Even active. Shifting SL of ticket {ticket_id} to Entry ({entry_price})")
                            request = {
                                "action": mt5.TRADE_ACTION_SLTP,
                                "position": ticket_id,
                                "sl": entry_price,
                                "tp": position.tp
                            }
                            res = mt5.order_send(request)
                            if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
                                logger.error(f"Failed to move SL to break-even. Retcode: {res.retcode if res else 'None'}")

                        # If Single Ticket Partial Close mode, shave off TP1 volume allocation
                        if config.tp_execution_mode == "single_ticket_partial":
                            shave_vol = min(track["tp1_vol"], volume)
                            if shave_vol > 0 and volume > shave_vol:
                                logger.info(f"Executing partial close: Shaving {shave_vol} lots off ticket {ticket_id}")
                                request = {
                                    "action": mt5.TRADE_ACTION_DEAL,
                                    "symbol": symbol,
                                    "volume": shave_vol,
                                    "type": mt5.ORDER_TYPE_SELL if action == "BUY" else mt5.ORDER_TYPE_BUY,
                                    "position": ticket_id,
                                    "price": mt5.symbol_info_tick(symbol).bid if action == "BUY" else mt5.symbol_info_tick(symbol).ask,
                                    "deviation": 20,
                                    "comment": "TP1 Partial Close"
                                }
                                res = mt5.order_send(request)
                                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                    # Update remaining volume
                                    new_volume = round(volume - shave_vol, 2)
                                    await update_tracked_order_tp_hit(ticket_id, 1, new_volume)
                                else:
                                    logger.error(f"TP1 partial close failed: {res.comment if res else 'No Response'}")
                            else:
                                # Volume too small, close entire position
                                logger.info(f"Remaining volume ({volume}) <= TP1 allocation ({track['tp1_vol']}). Closing entire ticket.")
                                request = {
                                    "action": mt5.TRADE_ACTION_DEAL,
                                    "symbol": symbol,
                                    "volume": volume,
                                    "type": mt5.ORDER_TYPE_SELL if action == "BUY" else mt5.ORDER_TYPE_BUY,
                                    "position": ticket_id,
                                    "price": mt5.symbol_info_tick(symbol).bid if action == "BUY" else mt5.symbol_info_tick(symbol).ask,
                                    "deviation": 20,
                                    "comment": "TP1 Full Close"
                                }
                                res = mt5.order_send(request)
                                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                    await update_tracked_order_tp_hit(ticket_id, 1, 0.0, set_inactive=True)
                        else:
                            # In multiple tickets mode, we just record that this ticket hit TP1
                            await update_tracked_order_tp_hit(ticket_id, 1, volume)

                # Check TP2 Hit (Only relevant for Single Ticket mode)
                elif not track["tp2_hit"] and config.tp_execution_mode == "single_ticket_partial":
                    tp2_hit = False
                    if action == "BUY" and current_price >= track["tp2"]:
                        tp2_hit = True
                    elif action == "SELL" and current_price <= track["tp2"]:
                        tp2_hit = True

                    if tp2_hit:
                        logger.info(f"Take Profit level 2 ({track['tp2']}) hit for ticket {ticket_id}")
                        shave_vol = min(track["tp2_vol"], volume)
                        if shave_vol > 0 and volume > shave_vol:
                            logger.info(f"Executing partial close: Shaving {shave_vol} lots off ticket {ticket_id}")
                            request = {
                                "action": mt5.TRADE_ACTION_DEAL,
                                "symbol": symbol,
                                "volume": shave_vol,
                                "type": mt5.ORDER_TYPE_SELL if action == "BUY" else mt5.ORDER_TYPE_BUY,
                                "position": ticket_id,
                                "price": mt5.symbol_info_tick(symbol).bid if action == "BUY" else mt5.symbol_info_tick(symbol).ask,
                                "deviation": 20,
                                "comment": "TP2 Partial Close"
                            }
                            res = mt5.order_send(request)
                            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                new_volume = round(volume - shave_vol, 2)
                                await update_tracked_order_tp_hit(ticket_id, 2, new_volume)
                            else:
                                logger.error(f"TP2 partial close failed: {res.comment if res else 'No Response'}")
                        else:
                            logger.info(f"Remaining volume ({volume}) <= TP2 allocation. Closing entire ticket.")
                            request = {
                                "action": mt5.TRADE_ACTION_DEAL,
                                "symbol": symbol,
                                "volume": volume,
                                "type": mt5.ORDER_TYPE_SELL if action == "BUY" else mt5.ORDER_TYPE_BUY,
                                "position": ticket_id,
                                "price": mt5.symbol_info_tick(symbol).bid if action == "BUY" else mt5.symbol_info_tick(symbol).ask,
                                "deviation": 20,
                                "comment": "TP2 Full Close"
                            }
                            res = mt5.order_send(request)
                            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                await update_tracked_order_tp_hit(ticket_id, 2, 0.0, set_inactive=True)

                # Check TP3 Hit (Only relevant for Single Ticket mode)
                elif not track["tp3_hit"] and config.tp_execution_mode == "single_ticket_partial":
                    tp3_hit = False
                    if action == "BUY" and current_price >= track["tp3"]:
                        tp3_hit = True
                    elif action == "SELL" and current_price <= track["tp3"]:
                        tp3_hit = True

                    if tp3_hit:
                        logger.info(f"Take Profit level 3 ({track['tp3']}) hit for ticket {ticket_id}. Closing remaining position.")
                        request = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "symbol": symbol,
                            "volume": volume,
                            "type": mt5.ORDER_TYPE_SELL if action == "BUY" else mt5.ORDER_TYPE_BUY,
                            "position": ticket_id,
                            "price": mt5.symbol_info_tick(symbol).bid if action == "BUY" else mt5.symbol_info_tick(symbol).ask,
                            "deviation": 20,
                            "comment": "TP3 Target Reached"
                        }
                        res = mt5.order_send(request)
                        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                            await update_tracked_order_tp_hit(ticket_id, 3, 0.0, set_inactive=True)
                        else:
                            logger.error(f"TP3 closing failed: {res.comment if res else 'No Response'}")

        except Exception as e:
            logger.error(f"Error in Live Risk Monitor: {e}")
        
        await asyncio.sleep(1)


# =====================================================================
# DEALS SYNC & CIRCUIT BREAKERS
# =====================================================================

async def run_closed_deals_sync() -> None:
    """60-second Closed Deal Synchronization Worker.

    Queries closed trades history from MT5 terminal since midnight.
    Calculates consecutive win/loss streaks grouped by magic number.
    Auto-pauses channel if loss streak limit is breached.
    """
    logger.info("Starting MT5 Closed-Deal Synchronization background worker...")
    while True:
        try:
            await asyncio.sleep(60)

            if mt5 is None or not mt5.initialize():
                continue

            # Query deals since midnight today
            today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            now = datetime.datetime.now()
            
            # Fetch closed deals
            deals = mt5.history_deals_get(today_start, now)
            if deals is None:
                continue

            # Group closed out transactions (DEAL_ENTRY_OUT)
            closed_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
            if not closed_deals:
                continue

            # Sort deals chronologically
            closed_deals.sort(key=lambda d: d.time)

            # Map magic numbers to channel DB entries
            channels_list = await get_all_channels()
            magic_to_channel = {c["magic_number"]: c for c in channels_list if c["magic_number"] is not None}

            # Map magic number -> list of deal outcomes (True = Win/Profit >= 0, False = Loss)
            deal_outcomes: Dict[int, List[bool]] = {}
            for deal in closed_deals:
                magic = deal.magic
                if magic not in magic_to_channel:
                    continue
                profit = deal.profit + deal.commission + deal.swap
                is_win = profit >= 0
                if magic not in deal_outcomes:
                    deal_outcomes[magic] = []
                deal_outcomes[magic].append(is_win)

            # Update streaks in DB
            for magic, outcomes in deal_outcomes.items():
                consecutive_losses = 0
                consecutive_wins = 0

                # Trace backwards to compute current active streaks
                # Wins streak
                for win in reversed(outcomes):
                    if win:
                        consecutive_wins += 1
                    else:
                        break
                
                # Losses streak
                for win in reversed(outcomes):
                    if not win:
                        consecutive_losses += 1
                    else:
                        break

                # Update database
                conn = sqlite3.connect(DB_PATH)
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE channels 
                        SET consecutive_losses = ?, consecutive_wins = ? 
                        WHERE magic_number = ?
                    """, (consecutive_losses, consecutive_wins, magic))
                    conn.commit()
                except Exception as e:
                    logger.error(f"Error updating channel streaks: {e}")
                finally:
                    conn.close()

                # Trigger Auto-Pause if Loss Streak threshold is breached
                channel_name = magic_to_channel[magic]["channel_name"]
                if consecutive_losses >= config.auto_pause_loss_streak_threshold:
                    # Retrieve database record again to check if already paused
                    fresh_status = await get_channel_status(channel_name)
                    if not fresh_status["paused"]:
                        logger.warning(
                            f"Auto-Pause Breaker Triggered: Channel '{channel_name}' has reached "
                            f"{consecutive_losses} consecutive losses. Pausing trading payloads."
                        )
                        await set_channel_paused(magic, True)

        except Exception as e:
            logger.error(f"Error in Closed Deals Sync loop: {e}")


async def execute_signal_with_risk(signal: Dict[str, Any], channel_source: str) -> Optional[List[int]]:
    """Execute trade signal applying risk parameters and routing rules.
    
    Args:
        signal: Parsed signal data dictionary.
        channel_source: Unique Telegram chat/channel source ID.
        
    Returns:
        Optional[List[int]]: List of order ticket numbers placed if successful.
    """
    if mt5 is None:
        logger.error("MetaTrader5 package is not available")
        return None

    # Check license activation status
    import license_manager
    lic_status = license_manager.get_license_status()
    if not lic_status["active"]:
        logger.warning(f"Trade signal rejected: {lic_status['message']}")
        return None

    # 1. Run Account-Level Pre-flight checks
    is_valid, reason = await validate_preflight(channel_source)
    if not is_valid:
        logger.warning(f"Trade signal rejected by pre-flight checks: {reason}")
        return None

    symbol = signal["symbol"]
    action = signal["action"]

    # 2. Select symbol in MT5
    if not mt5.symbol_select(symbol, True):
        logger.error(f"Symbol {symbol} is not available on this broker/server")
        return None

    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        logger.error(f"Failed to fetch symbol info for {symbol}")
        return None

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        logger.error(f"Failed to get current tick for {symbol}")
        return None

    current_ask = tick.ask
    current_bid = tick.bid
    current_price = current_ask if action == "BUY" else current_bid
    digits = symbol_info.digits
    point = symbol_info.point

    # 3. Resolve entry price
    target_entry = signal.get("entry")
    if target_entry is None:
        entry_price = current_price
    else:
        entry_price = target_entry

    # 4. Check entry slippage if entry target is specified
    if target_entry is not None:
        is_gold = any(x in symbol.upper() for x in ["XAU", "GOLD"])
        pip_size = 0.1 if is_gold else 0.0001
        slippage_pips = abs(current_price - target_entry) / pip_size
        if slippage_pips > config.max_entry_slippage:
            logger.warning(
                f"Slippage limit exceeded for {symbol}. "
                f"Target: {target_entry}, Current: {current_price}, "
                f"Slippage: {slippage_pips:.1f} pips. Limit: {config.max_entry_slippage} pips."
            )
            return None

    # 5. Resolve SL with fallback if missing
    sl_price = signal.get("sl")
    if sl_price is None or sl_price <= 0:
        is_gold = any(x in symbol.upper() for x in ["XAU", "GOLD"])
        pip_multiplier = 0.1 if is_gold else 0.0001
        fallback_points = config.default_fallback_sl * (pip_multiplier / point) * point
        if action == "BUY":
            sl_price = entry_price - fallback_points
        else:
            sl_price = entry_price + fallback_points
        logger.info(f"Stop Loss is missing. Applied default fallback SL of {config.default_fallback_sl} pips: {sl_price}")

    # 6. Calculate position sizing and Take Profit vectors
    total_lots, sl_points = calculate_lot_size(symbol, sl_price, entry_price)
    if total_lots <= 0:
        logger.error("Calculated lot size is 0. Cannot trade.")
        return None

    # Build Take Profit vector
    tp_raw = signal.get("tp")
    tp_list = []
    if isinstance(tp_raw, list):
        tp_list = tp_raw
    elif tp_raw is not None:
        tp_list = [tp_raw]
    if "tps" in signal and signal["tps"]:
        tp_list = signal["tps"]

    tps = build_tp_vector(entry_price, sl_price, tp_list, action, symbol)
    vols = calculate_tp_volume_slices(total_lots, symbol)
    magic_number = await get_or_create_magic_number(channel_source)

    # 7. Check if entry is near market price to determine execution type
    is_market = False
    market_tolerance = 15 * point
    current_ref = current_ask if action == "BUY" else current_bid
    if abs(entry_price - current_ref) <= market_tolerance:
        is_market = True

    tickets = []

    # CASE 1: Multiple Separate Tickets Mode
    if config.tp_execution_mode == "multiple_tickets":
        for i, (tp_level, vol_slice) in enumerate(zip(tps, vols)):
            if vol_slice <= 0:
                continue

            if is_market:
                order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
                action_type = mt5.TRADE_ACTION_DEAL
                exec_price = current_ask if action == "BUY" else current_bid
            else:
                action_type = mt5.TRADE_ACTION_PENDING
                if action == "BUY":
                    order_type = mt5.ORDER_TYPE_BUY_LIMIT if entry_price < current_ask else mt5.ORDER_TYPE_BUY_STOP
                else:
                    order_type = mt5.ORDER_TYPE_SELL_LIMIT if entry_price > current_bid else mt5.ORDER_TYPE_SELL_STOP
                exec_price = round(entry_price, digits)

            request = {
                "action": action_type,
                "symbol": symbol,
                "volume": vol_slice,
                "type": order_type,
                "price": exec_price,
                "sl": round(sl_price, digits),
                "tp": round(tp_level, digits),
                "deviation": 20,
                "magic": magic_number,
                "comment": f"TG Split TP{i+1}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC if is_market else mt5.ORDER_TIME_GTC,
            }

            logger.info(f"Sending Split TP{i+1} order request: {action} {vol_slice} {symbol} SL:{sl_price} TP:{tp_level}")
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Split TP{i+1} order executed successfully! Ticket: {res.order}")
                tickets.append(res.order)
                # Register ticket tracking in DB
                await add_tracked_order(
                    res.order, channel_source, magic_number, symbol, action,
                    entry_price, sl_price, tps, vols
                )
            else:
                err = res.retcode if res else "No Response"
                logger.error(f"Failed to place Split TP{i+1} order! Return code: {err}")

    # CASE 2: Single Ticket with Partial Closes Mode
    else:
        if is_market:
            order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
            action_type = mt5.TRADE_ACTION_DEAL
            exec_price = current_ask if action == "BUY" else current_bid
        else:
            action_type = mt5.TRADE_ACTION_PENDING
            if action == "BUY":
                order_type = mt5.ORDER_TYPE_BUY_LIMIT if entry_price < current_ask else mt5.ORDER_TYPE_BUY_STOP
            else:
                order_type = mt5.ORDER_TYPE_SELL_LIMIT if entry_price > current_bid else mt5.ORDER_TYPE_SELL_STOP
            exec_price = round(entry_price, digits)

        # Initial TP set to final target (TP3)
        request = {
            "action": action_type,
            "symbol": symbol,
            "volume": round(total_lots, 2),
            "type": order_type,
            "price": exec_price,
            "sl": round(sl_price, digits),
            "tp": round(tps[2], digits),
            "deviation": 20,
            "magic": magic_number,
            "comment": "TG Single Ticket",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC if is_market else mt5.ORDER_TIME_GTC,
        }

        logger.info(f"Sending Single Ticket order request: {action} {total_lots} {symbol} SL:{sl_price} TP:{tps[2]}")
        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Single Ticket order executed successfully! Ticket: {res.order}")
            tickets.append(res.order)
            # Register ticket tracking in DB
            await add_tracked_order(
                res.order, channel_source, magic_number, symbol, action,
                entry_price, sl_price, tps, vols
            )
        else:
            err = res.retcode if res else "No Response"
            logger.error(f"Failed to place Single Ticket order! Return code: {err}")

    return tickets if tickets else None
