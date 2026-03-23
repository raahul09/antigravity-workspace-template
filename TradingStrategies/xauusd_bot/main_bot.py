"""Main control loop for the MT5 XAUUSD Bot.

This module acts as the orchestrator, connecting the data feed, liquidity engine, 
and execution module in an asynchronous infinite loop during market hours.
"""

import asyncio
import logging
import sys

from bot_config import config
import data_feed as feed
from liquidity_engine import LiquidityEngine
import execution as exec

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def run_bot_loop():
    """The main asynchronous loop executing the SMC strategy."""
    
    logger.info(f"Starting {config.symbol} SMC Trading Bot...")
    if not feed.initialize_mt5():
        logger.error("Failed to connect to MT5. Exiting.")
        sys.exit(1)

    engine = LiquidityEngine(swing_lookback=5)

    try:
        while True:
            # 1. Fetch 15M Data & Map Structure
            df_15m = feed.get_15m_candles(count=200)
            if df_15m is not None:
                engine.find_15m_swing_points(df_15m)
            
            # 2. Fetch 1M Data for Sweep Confirmations
            df_1m = feed.get_1m_candles(count=50)
            tick = feed.get_current_tick()
            
            if df_1m is not None and tick is not None:
                current_price = tick['bid'] # Simplified: usually Bid for Sells, Ask for Buys
                
                # 3. Analyze for Sweeps & CHoCH (Trend Filtered)
                setup = engine.detect_liquidity_sweep(current_price, df_1m, df_15m_context=df_15m)
                
                # 4. Execute if Setup is Valid
                if setup:
                    direction = setup['direction']
                    sl = setup['stop_loss']
                    
                    logger.info(f"🚨 SWEEP DETECTED! Direction: {direction}, SL: {sl}")
                    
                    # We use Bid to sell, Ask to buy
                    entry_price = tick['ask'] if direction == 1 else tick['bid']
                    ticket = exec.execute_market_order(direction, sl, entry_price)
                    
                    if ticket:
                        logger.info(f"Trade successfully placed! Ticket: {ticket}")
                        # Sleep for a bit to avoid multi-entries on the same setup
                        await asyncio.sleep(60)
            
            # Poll at regular intervals (e.g. 5 seconds)
            await asyncio.sleep(5)
            
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.exception(f"Unexpected error in main loop: {e}")
    finally:
        feed.shutdown_mt5()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_bot_loop())
