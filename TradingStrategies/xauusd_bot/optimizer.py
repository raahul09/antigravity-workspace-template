"""Optimizer and Self-Improvement module for the SMC Strategy.

This script fetches a defined historical date range (e.g., Jan 1 2025 - Present)
and iterates through a grid of parameters (R:R, Swing Lookback, Risk %) to
simulate compounding growth from a starting balance (e.g., $1000), seeking 
an optimal configuration (e.g., high win rate, high ending balance).
"""

import MetaTrader5 as mt5
import pandas as pd
import logging
from datetime import datetime, timezone
import itertools

from bot_config import config
import data_feed as feed
from liquidity_engine import LiquidityEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("Optimizer")

def run_simulation(df_1m, df_15m, params, starting_balance=1000.0) -> dict:
    """Core simulation engine calculating compounded returns."""
    swing_lookback = params['swing_lookback']
    rr_target = params['rr_target']
    risk_percent = params['risk_percent']
    
    engine = LiquidityEngine(swing_lookback=swing_lookback)
    
    balance = starting_balance
    wins = 0
    losses = 0
    
    last_15m_time = None
    
    for i in range(50, len(df_1m)):
        if balance <= 0:
            break
            
        current_time = df_1m.index[i]
        
        current_15m = df_15m[df_15m.index <= current_time]
        if len(current_15m) < swing_lookback * 2 + 1:
            continue
            
        latest_15m_time = current_15m.index[-1]
        if last_15m_time != latest_15m_time:
            engine.find_15m_swing_points(current_15m)
            last_15m_time = latest_15m_time
            
        recent_1m = df_1m.iloc[i-15 : i+1]
        current_price = df_1m['close'].iloc[i] 
        
        setup = engine.detect_liquidity_sweep(current_price, recent_1m)
        
        if setup:
            direction = setup['direction']
            sl = setup['stop_loss']
            entry = current_price
            
            sl_dist = abs(entry - sl)
            if sl_dist == 0: continue
            
            tp_dist = sl_dist * rr_target
            tp = entry + tp_dist if direction == 1 else entry - tp_dist
            
            # Risk calculation
            dollar_risk = balance * (risk_percent / 100.0)
            
            outcome = "TIMED_OUT"
            future_1m = df_1m.iloc[i+1 : i+60]
            
            for f_i in range(len(future_1m)):
                f_high = future_1m['high'].iloc[f_i]
                f_low = future_1m['low'].iloc[f_i]
                
                if direction == 1: # Buy
                    if f_low <= sl:
                        outcome = "LOSS"
                        balance -= dollar_risk
                        break
                    elif f_high >= tp:
                        outcome = "WIN"
                        balance += (dollar_risk * rr_target)
                        break
                else: # Sell
                    if f_high >= sl:
                        outcome = "LOSS"
                        balance -= dollar_risk
                        break
                    elif f_low <= tp:
                        outcome = "WIN"
                        balance += (dollar_risk * rr_target)
                        break
                        
            if outcome == "WIN":
                wins += 1
            elif outcome == "LOSS":
                losses += 1
                
    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    return {
        'params': params,
        'ending_balance': balance,
        'win_rate': win_rate,
        'trades': total_trades,
        'roi_percent': ((balance - starting_balance) / starting_balance) * 100
    }

def run_optimizer():
    """Main optimizer loop."""
    logger.info("Initializing connection to MT5...")
    if not feed.initialize_mt5():
        logger.error("Failed to connect to MT5.")
        return

    logger.info(f"Fetching approximately 2 months of historical data (50k M1 candles)...")
    
    df_1m = feed.get_1m_candles(count=50000)
    df_15m = feed.get_15m_candles(count=4000)
    
    if df_1m is None or df_15m is None:
        logger.error("Failed to fetch required optimization data.")
        feed.shutdown_mt5()
        return

    logger.info(f"Loaded {len(df_1m)} M1 candles and {len(df_15m)} M15 candles.")

    # Define Param Grid 
    # High win rates usually require smaller R:R targets or larger lookbacks.
    # To reach $10k from $1k, higher risk % is usually required.
    param_grid = {
        'swing_lookback': [3, 5, 8],
        'rr_target': [0.5, 1.0, 1.5, 2.0],
        'risk_percent': [2.0, 5.0, 10.0]  # Very high risk for compounding 10x
    }
    
    keys = list(param_grid.keys())
    combinations = list(itertools.product(*[param_grid[k] for k in keys]))
    
    results = []
    
    logger.info(f"Starting Grid Search across {len(combinations)} parameter combinations...")
    
    for combo in combinations:
        params = dict(zip(keys, combo))
        logger.info(f"Testing: {params}")
        
        sim_result = run_simulation(df_1m, df_15m, params, starting_balance=1000.0)
        results.append(sim_result)
        
        logger.info(f" -> Balance: ${sim_result['ending_balance']:.2f} | Win Rate: {sim_result['win_rate']:.2f}% | Trades: {sim_result['trades']}")

    # Sort by Ending Balance natively
    best_results = sorted(results, key=lambda x: x['ending_balance'], reverse=True)
    
    logger.info("\n🏆 ====== OPTIMIZATION COMPLETE ====== 🏆")
    logger.info("Top 3 Configurations:")
    for i in range(min(3, len(best_results))):
        res = best_results[i]
        logger.info(f"#{i+1}: {res['params']}")
        logger.info(f"    Ending Balance: ${res['ending_balance']:.2f} ({(res['roi_percent']):.2f}%)")
        logger.info(f"    Win Rate: {res['win_rate']:.2f}%")
        logger.info(f"    Total Trades: {res['trades']}")
    
    feed.shutdown_mt5()

if __name__ == "__main__":
    run_optimizer()
