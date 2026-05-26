"""Main entrypoint for the Telegram-to-MT5 Signal Automation Bot.

Orchestrates initialization of MT5 connection, starts the Telegram client listener,
and routes incoming signal messages to the parser and executor. Supports Web GUI mode.
"""

import sys
import asyncio
import logging
import signal
import argparse
from typing import Dict, Any

from config import config
import parser
import executor
from listener import TelegramSignalListener

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("telegram_to_mt5.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("telegram_mt5_bot")


def handle_incoming_signal(raw_text: str, channel_source: str = "default") -> None:
    """Callback function triggered when a new Telegram message is received.

    Args:
        raw_text: Raw message content.
        channel_source: Unique ID of the source Telegram channel.
    """
    logger.info("Evaluating message for potential trading signal...")
    
    # 1. Parse message
    signal_data = parser.parse_signal(raw_text)
    if not signal_data:
        logger.info("Message did not match signal criteria. Skipping execution.")
        return

    logger.info(f"Parsed Trade Signal: {signal_data} from channel source: {channel_source}")

    # 2. Execute on MT5 using risk manager
    import risk_manager
    asyncio.create_task(_process_signal_async(signal_data, channel_source))


async def _process_signal_async(signal_data: dict, channel_source: str) -> None:
    try:
        import risk_manager
        tickets = await risk_manager.execute_signal_with_risk(signal_data, channel_source)
        if tickets:
            logger.info(f"Successfully processed signal! Order Tickets: {tickets}")
        else:
            logger.error("Signal parsed but execution failed in MetaTrader 5 or was blocked by risk limits.")
    except Exception as e:
        logger.exception(f"Unexpected error executing parsed signal: {e}")


async def run_headless() -> None:
    """Start the main execution loop in headless mode (no GUI)."""
    logger.info("=" * 60)
    logger.info("Starting Telegram to MT5 Signal Automation (Headless)...")
    logger.info("=" * 60)

    # 1. Initialize MetaTrader 5
    if not executor.initialize_mt5():
        logger.error("Failed to establish connection to MetaTrader 5. Exiting.")
        sys.exit(1)

    # 2. Initialize Telegram listener
    listener = TelegramSignalListener()
    listener.set_signal_callback(handle_incoming_signal)

    # Start Risk Management background tasks
    import risk_manager
    risk_monitor = asyncio.create_task(risk_manager.run_live_risk_monitor())
    deals_sync = asyncio.create_task(risk_manager.run_closed_deals_sync())

    # Handle shutdown signals
    loop = asyncio.get_running_loop()
    
    def shutdown_handler():
        logger.info("Shutdown signal received. Cleaning up resources...")
        executor.shutdown_mt5()
        # Cancel risk tasks
        risk_monitor.cancel()
        deals_sync.cancel()
        # Schedule disconnect task
        asyncio.create_task(listener.disconnect())
        sys.exit(0)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown_handler)
        except NotImplementedError:
            # signal handler not implemented on Windows event loops sometimes
            pass

    # 3. Start listener
    try:
        await listener.start()
    except KeyboardInterrupt:
        logger.info("Service stopped via KeyboardInterrupt.")
    except Exception as e:
        logger.exception(f"Fatal error in service loop: {e}")
    finally:
        executor.shutdown_mt5()
        await listener.disconnect()
        logger.info("Service stopped.")


if __name__ == "__main__":
    # Command-line arguments
    parser_arg = argparse.ArgumentParser(description="GrootTrade Telegram-to-MT5 Automation Bot")
    parser_arg.add_argument("--headless", action="store_true", help="Run in headless terminal mode (no Web Dashboard)")
    parser_arg.add_argument("--host", default="127.0.0.1", help="Host address for the Web Dashboard (default: 127.0.0.1)")
    parser_arg.add_argument("--port", type=int, default=8000, help="Port for the Web Dashboard (default: 8000)")
    args = parser_arg.parse_args()

    if args.headless:
        # Run standard headless terminal bot
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        try:
            asyncio.run(run_headless())
        except KeyboardInterrupt:
            logger.info("Process terminated.")
    else:
        # Run FastAPI web dashboard (which auto-starts the bot manager)
        from web_dashboard import run_web_server
        logger.info("Starting GrootTrade Web Control Panel...")
        try:
            run_web_server(host=args.host, port=args.port)
        except KeyboardInterrupt:
            logger.info("Web server terminated.")
