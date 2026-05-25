"""Main entrypoint for the Telegram-to-MT5 Signal Automation Bot.

Orchestrates initialization of MT5 connection, starts the Telegram client listener,
and routes incoming signal messages to the parser and executor.
"""

import sys
import asyncio
import logging
import signal
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


def handle_incoming_signal(raw_text: str) -> None:
    """Callback function triggered when a new Telegram message is received.

    Args:
        raw_text: Raw message content.
    """
    logger.info("Evaluating message for potential trading signal...")
    
    # 1. Parse message
    signal_data = parser.parse_signal(raw_text)
    if not signal_data:
        logger.info("Message did not match signal criteria. Skipping execution.")
        return

    logger.info(f"Parsed Trade Signal: {signal_data}")

    # 2. Execute on MT5
    try:
        ticket = executor.execute_signal(signal_data)
        if ticket:
            logger.info(f"Successfully processed signal! Order Ticket: {ticket}")
        else:
            logger.error("Signal parsed but execution failed in MetaTrader 5.")
    except Exception as e:
        logger.exception(f"Unexpected error executing parsed signal: {e}")


async def main() -> None:
    """Start the main execution loop."""
    logger.info("=" * 60)
    logger.info("Starting Telegram to MT5 Signal Automation Service...")
    logger.info("=" * 60)

    # 1. Initialize MetaTrader 5
    if not executor.initialize_mt5():
        logger.error("Failed to establish connection to MetaTrader 5. Exiting.")
        sys.exit(1)

    # 2. Initialize Telegram listener
    listener = TelegramSignalListener()
    listener.set_signal_callback(handle_incoming_signal)

    # Handle shutdown signals
    loop = asyncio.get_running_loop()
    
    def shutdown_handler():
        logger.info("Shutdown signal received. Cleaning up resources...")
        executor.shutdown_mt5()
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
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process terminated.")
