"""Telegram listener service.

Connects to Telegram using the Client API (Telethon) and listens for new 
messages in monitored chats or channels.
"""

import os
import logging
from typing import Callable, Union, List, Optional
from telethon import TelegramClient, events

from config import config

logger = logging.getLogger(__name__)


class TelegramSignalListener:
    """Listens to Telegram messages and routes signals to a callback handler."""

    def __init__(self, session_name: str = "telegram_mt5_session"):
        """Initialize the listener.

        Args:
            session_name: Name of the session file to store authorization state.
        """
        self.session_name = session_name
        self.client = TelegramClient(
            self.session_name,
            config.telegram_api_id,
            config.telegram_api_hash
        )
        self.on_signal_callback: Optional[Callable[[str], None]] = None

    def set_signal_callback(self, callback: Callable[[str], None]) -> None:
        """Set the function to call when a potential signal message is received.

        Args:
            callback: Callable that accepts a raw message string.
        """
        self.on_signal_callback = callback

    async def start(self) -> None:
        """Start the Telegram client and register event handlers."""
        logger.info("Connecting to Telegram...")
        
        # This will sign in the user if not already authorized, prompting
        # for phone number and code in the terminal if necessary.
        await self.client.start()
        
        me = await self.client.get_me()
        logger.info(f"Successfully logged in as: {me.first_name} (@{me.username or 'NoUsername'})")

        # Resolve chats/channels to monitor (supports comma-separated list)
        source_chat = config.telegram_source_chat
        
        if source_chat:
            chats = []
            for part in source_chat.split(","):
                part_clean = part.strip()
                if not part_clean:
                    continue
                if part_clean.startswith("-") or part_clean.isdigit():
                    try:
                        chats.append(int(part_clean))
                    except ValueError:
                        chats.append(part_clean)
                else:
                    chats.append(part_clean)
            
            logger.info(f"Configured to monitor chats: {chats}")
        else:
            chats = None
            logger.info("No source chat configured. Monitoring ALL incoming messages (Direct Messages & Groups)")

        # Register event handler for incoming messages
        @self.client.on(events.NewMessage(chats=chats))
        async def on_new_message(event):
            # Ignore empty messages
            if not event.raw_text:
                return

            chat = await event.get_input_chat()
            chat_title = getattr(event.chat, 'title', 'Direct Message')
            sender = await event.get_sender()
            sender_name = getattr(sender, 'username', getattr(sender, 'first_name', 'Unknown'))
            
            logger.info(f"New message from {sender_name} in '{chat_title}': {event.raw_text.strip()}")

            chat_id = str(event.chat_id)
            if self.on_signal_callback:
                try:
                    # Pass the chat ID (channel source) as the second argument
                    self.on_signal_callback(event.raw_text, chat_id)
                except Exception as e:
                    logger.error(f"Error executing signal callback: {e}")

        logger.info("Telegram event listener registered. Waiting for messages...")
        await self.client.run_until_disconnected()

    async def disconnect(self) -> None:
        """Disconnect the Telegram client session."""
        if self.client.is_connected():
            logger.info("Disconnecting from Telegram...")
            await self.client.disconnect()
