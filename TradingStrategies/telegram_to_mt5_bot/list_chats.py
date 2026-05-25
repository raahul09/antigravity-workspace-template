"""Helper script to list all Telegram groups and channels for the logged-in user.

Connects to Telegram using the credentials in .env, prompts for login code,
and prints a list of all chat titles and IDs.
"""

import asyncio
import sys
import logging
from telethon import TelegramClient

from config import config

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("list_chats")


async def main() -> None:
    """Connect to Telegram and list all chats/groups/channels."""
    if not config.telegram_api_id or not config.telegram_api_hash:
        logger.error("TELEGRAM_API_ID and TELEGRAM_API_HASH must be configured in .env")
        sys.exit(1)

    logger.info("Initializing Telegram client...")
    client = TelegramClient("telegram_mt5_session", config.telegram_api_id, config.telegram_api_hash)
    
    await client.start()
    logger.info("Successfully connected to Telegram!")

    print("\n" + "=" * 80)
    print("YOUR TELEGRAM CHATS, GROUPS, AND CHANNELS:")
    print("=" * 80)
    print(f"{'Title':<45} | {'ID':<15} | {'Type':<15}")
    print("-" * 80)

    # Get dialogs
    async for dialog in client.iter_dialogs():
        chat_type = "User/DM"
        if dialog.is_group:
            chat_type = "Group"
        elif dialog.is_channel:
            chat_type = "Channel"
            
        # Clean title to avoid Windows console Unicode encoding crash (cp1252 limit)
        clean_name = dialog.name.encode("ascii", "ignore").decode("ascii").strip()
        if not clean_name:
            clean_name = f"Unnamed ({dialog.id})"
        title = clean_name[:43] + "..." if len(clean_name) > 43 else clean_name
        print(f"{title:<45} | {dialog.id:<15} | {chat_type:<15}")

    print("=" * 80 + "\n")
    await client.disconnect()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
