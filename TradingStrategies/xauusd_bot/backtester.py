"""Historical Backtester for the MT5 XAUUSD SMC Bot.

This script fetches historical 1M and 15M candles from MetaTrader 5 and 
runs them chronologically through the `liquidity_engine.py` to simulate
trades and calculate theoretical P&L.
"""

import MetaTrader5 as mt5
import pandas as pd
import logging
import sys

from bot_config import config
import data_feed as feed
from liquidity_engine import LiquidityEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("Backtester")

def run_backtest(days_back: int = 5):
    """Run a historical backtest.
    
    Args:
        days_back (int): Number of days of 1-minute data to fetch and simulate.
    """
    logger.info("Initializing connection to MT5 for historical data...")
    if not feed.initialize_mt5():
        logger.error("Failed to connect to MT5. Ensure the terminal is open.")
        return

    # 1.5 years of 1M candles is roughly 450,000 to 500,000 candles depending on market open hours.
    # MT5 will return the maximum allowed by your Max Bars In History terminal setting.
    total_1m_candles = 400000 
    
    logger.info(f"Fetching up to {total_1m_candles} M1 candles for {config.symbol} (Target: Jan 1 2025)...")
    df_1m_full = feed.get_1m_candles(count=total_1m_candles)
    
    total_15m_candles = int(total_1m_candles / 15) + 100
    df_15m_full = feed.get_15m_candles(count=total_15m_candles)

    if df_1m_full is None or df_15m_full is None:
        logger.error("Failed to fetch historical data. Aborting backtest.")
        feed.shutdown_mt5()
        return

    engine = LiquidityEngine(swing_lookback=5)
    
    wins = 0
    losses = 0
    total_pnl = 0.0 # Standardized R units (1 R = 1% Risk)
    
    logger.info("Starting simulation loop...")
    
    # Track the last 15M alignment so we don't recalculate 15m structure 
    # every single minute unnecessarily.
    last_15m_time = None
    
    # In a real tick backtester, we iterate tick by tick. For this speed test, 
    # we iterate minute by minute (candle closes).
    for i in range(50, len(df_1m_full)):
        current_time = df_1m_full.index[i]
        
        # Get matching 15M context up to this exact minute
        current_15m = df_15m_full[df_15m_full.index <= current_time]
        if len(current_15m) < 20:
            continue
            
        # Update 15M structure only when a new 15M candle has closed
        latest_15m_time = current_15m.index[-1]
        if last_15m_time != latest_15m_time:
            engine.find_15m_swing_points(current_15m)
            last_15m_time = latest_15m_time
            
        # Get short window of recent 1M action up to right now
        recent_1m = df_1m_full.iloc[i-15 : i+1]
        current_price = df_1m_full['close'].iloc[i] # Approximating execution at candle close
        
        setup = engine.detect_liquidity_sweep(current_price, recent_1m, df_15m_context=current_15m)
        
        if setup:
            direction = setup['direction']
            sl = setup['stop_loss']
            entry = current_price
            
            sl_dist = abs(entry - sl)
            tp_dist = sl_dist * config.reward_to_risk_target
            tp = entry + tp_dist if direction == 1 else entry - tp_dist
            
            # Simulate trade outcome by looking ahead
            # Naive simulation: check if high/low hits TP/SL in the next X candles
            outcome = "TIMED_OUT"
            pnl_r = 0.0
            
            future_1m = df_1m_full.iloc[i+1 : i+60] # Look ahead 1 hour
            
            for f_i in range(len(future_1m)):
                f_high = future_1m['high'].iloc[f_i]
                f_low = future_1m['low'].iloc[f_i]
                
                if direction == 1: # Buy
                    if f_low <= sl:
                        outcome = "LOSS"
                        pnl_r = -1.0
                        break
                    elif f_high >= tp:
                        outcome = "WIN"
                        pnl_r = config.reward_to_risk_target
                        break
                else: # Sell
                    if f_high >= sl:
                        outcome = "LOSS"
                        pnl_r = -1.0
                        break
                    elif f_low <= tp:
                        outcome = "WIN"
                        pnl_r = config.reward_to_risk_target
                        break
            
            if outcome == "WIN":
                wins += 1
            elif outcome == "LOSS":
                losses += 1
                
            total_pnl += pnl_r
            logger.info(f"[{current_time}] Trade: {'BUY' if direction==1 else 'SELL'} @ {entry:.2f} | Setup: {setup['swing_level']} | Outcome: {outcome} | P&L (R): {pnl_r:.2f}")

    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    logger.info("\n========== BACKTEST RESULTS ==========")
    logger.info(f"Symbol: {config.symbol}")
    logger.info(f"Data Set: {len(df_1m_full)} M1 Candles (Approx. {len(df_1m_full)/1440:.1f} Trading Days)")
    logger.info(f"Start Date: {df_1m_full.index[0]}")
    logger.info(f"End Date: {df_1m_full.index[-1]}")
    logger.info(f"Total Trades: {total_trades}")
    logger.info(f"Wins: {wins} | Losses: {losses}")
    logger.info(f"Win Rate: {win_rate:.2f}%")
    logger.info(f"Total P&L (R units): {total_pnl:.2f} R")
    logger.info("======================================")

    feed.shutdown_mt5()

if __name__ == "__main__":
    run_backtest(days_back=5)
