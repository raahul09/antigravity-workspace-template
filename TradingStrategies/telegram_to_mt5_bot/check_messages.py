"""Debug script to check the last few messages of the teesterbro channel."""

import asyncio
import sys
from telethon import TelegramClient

from config import config


async def main() -> None:
    """Connect to Telegram and fetch last 5 messages from teesterbro."""
    client = TelegramClient("telegram_mt5_session", config.telegram_api_id, config.telegram_api_hash)
    await client.start()
    
    print("\nConnecting and fetching messages...")
    try:
        channel = await client.get_entity("teesterbro")
        print(f"Channel resolved: {channel.title} (ID: {channel.id})")
        
        async for message in client.iter_messages(channel, limit=5):
            print(f"Date: {message.date} | Sender ID: {message.sender_id} | Text: {repr(message.text)}")
    except Exception as e:
        print(f"Error fetching channel/messages: {e}")
        
    await client.disconnect()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
