"""FastAPI Web Dashboard and configuration GUI.

Allows dynamic control of the bot lifecycle, monitoring connection statuses,
selecting chats to monitor, editing settings, testing signals, and viewing logs.
"""

import os
import sys
import logging
import asyncio
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# MT5 package is only importable on Windows, mock/protect it
try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from config import config, BotConfig
import parser
import executor
from listener import TelegramSignalListener
import risk_manager
import license_manager

logger = logging.getLogger("web_dashboard")

# Define request schemas
class ConfigUpdateRequest(BaseModel):
    mt5_login: int | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None
    telegram_api_id: int
    telegram_api_hash: str
    telegram_source_chat: str | None = None
    default_risk_percent: float = 2.0
    magic_number: int = 888999
    default_symbol: str = "XAUUSD"
    use_llm_parser: bool = False
    sl_keywords: str
    tp_keywords: str
    entry_keywords: str
    
    # New Risk management settings
    risk_sizing_mode: str = "fixed_lot"
    fixed_lot_size: float = 0.01
    risk_percentage: float = 1.0
    max_allowed_lot_size: float = 1.0
    tp_execution_mode: str = "multiple_tickets"
    tp1_allocation: float = 50.0
    tp2_allocation: float = 30.0
    tp3_allocation: float = 20.0
    move_sl_to_be_on_tp1: bool = True
    fallback_multi_tp_step: float = 20.0
    max_entry_slippage: float = 5.0
    default_fallback_sl: float = 30.0
    max_daily_drawdown_percent: float = 5.0
    max_concurrent_open_trades: int = 5
    auto_pause_loss_streak_threshold: int = 5

class SignalTestRequest(BaseModel):
    text: str

class ControlRequest(BaseModel):
    action: str  # "start", "stop", "restart"

class LicenseActivateRequest(BaseModel):
    key: str


class BotManager:
    """Manages the background Telegram listener task and MT5 connection lifecycle."""

    def __init__(self):
        self.listener: TelegramSignalListener | None = None
        self.bot_task: asyncio.Task | None = None
        self.risk_monitor_task: asyncio.Task | None = None
        self.deals_sync_task: asyncio.Task | None = None
        self.is_running: bool = False

    def handle_incoming_signal(self, raw_text: str, channel_source: str = "default") -> None:
        """Callback for incoming Telegram signals, routing to risk manager and executor."""
        logger.info("Evaluating message for potential trading signal...")
        signal_data = parser.parse_signal(raw_text)
        if not signal_data:
            logger.info("Message did not match signal criteria. Skipping execution.")
            return

        logger.info(f"Parsed Trade Signal: {signal_data} from channel source: {channel_source}")
        
        # Schedule the async execution since SQLite and order sends are async-friendly
        asyncio.create_task(self._process_signal_async(signal_data, channel_source))

    async def _process_signal_async(self, signal_data: dict, channel_source: str) -> None:
        try:
            tickets = await risk_manager.execute_signal_with_risk(signal_data, channel_source)
            if tickets:
                logger.info(f"Successfully processed signal! Order Tickets: {tickets}")
            else:
                logger.error("Signal parsed but execution failed in MetaTrader 5 or was blocked by risk limits.")
        except Exception as e:
            logger.exception(f"Unexpected error executing parsed signal: {e}")

    async def start(self) -> bool:
        """Start MT5 connection and the Telegram listener task."""
        if self.is_running:
            logger.warning("Bot is already running.")
            return True

        # Check license activation first
        status = license_manager.get_license_status()
        if not status["active"]:
            logger.error(f"Cannot start bot execution engine: {status['message']}")
            return False

        logger.info("Starting bot execution engine...")
        
        # 1. Initialize MT5
        if not executor.initialize_mt5():
            logger.error("Failed to connect to MetaTrader 5.")
            # Note: We still allow starting Telegram listener even if MT5 fails,
            # so the user can see log output and configure properly.

        # 2. Start Telethon Listener
        try:
            self.listener = TelegramSignalListener()
            self.listener.set_signal_callback(self.handle_incoming_signal)
            
            # Run start in a background task
            self.bot_task = asyncio.create_task(self.listener.start())
            
            # Start Risk Management background tasks
            self.risk_monitor_task = asyncio.create_task(risk_manager.run_live_risk_monitor())
            self.deals_sync_task = asyncio.create_task(risk_manager.run_closed_deals_sync())
            
            self.is_running = True
            logger.info("Telegram listener and Risk Management tasks started successfully.")
            return True
        except Exception as e:
            logger.exception(f"Failed to start Telegram listener: {e}")
            self.is_running = False
            return False

    async def stop(self) -> bool:
        """Stop Telegram listener and shutdown MT5 connection."""
        if not self.is_running:
            return True

        logger.info("Stopping bot execution engine...")
        
        # 1. Disconnect Telegram
        if self.listener:
            try:
                await self.listener.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting Telegram client: {e}")
            self.listener = None

        # Cancel Risk Management tasks
        if self.risk_monitor_task:
            self.risk_monitor_task.cancel()
            try:
                await self.risk_monitor_task
            except asyncio.CancelledError:
                pass
            self.risk_monitor_task = None

        if self.deals_sync_task:
            self.deals_sync_task.cancel()
            try:
                await self.deals_sync_task
            except asyncio.CancelledError:
                pass
            self.deals_sync_task = None

        # 2. Cancel loop task
        if self.bot_task:
            self.bot_task.cancel()
            try:
                await self.bot_task
            except asyncio.CancelledError:
                pass
            self.bot_task = None

        # 3. Shutdown MT5
        try:
            executor.shutdown_mt5()
        except Exception as e:
            logger.error(f"Error shutting down MT5 connection: {e}")

        self.is_running = False
        logger.info("Bot execution engine stopped.")
        return True

    async def restart(self) -> bool:
        """Restart the bot runner."""
        await self.stop()
        await asyncio.sleep(1)
        return await self.start()


# Global bot manager instance
bot_manager = BotManager()

# FastAPI application setup
app = FastAPI(title="Telegram to MT5 Bot Dashboard")

@app.on_event("startup")
async def startup_event():
    """Trigger bot connection automatically on dashboard web startup."""
    logger.info("FastAPI Web Server started. Auto-triggering trading bot engine...")
    # Use create_task to start it asynchronously so startup doesn't block
    asyncio.create_task(bot_manager.start())
    
    # Automatically open default web browser to dashboard
    import webbrowser
    try:
        url = "http://127.0.0.1:8000/"
        logger.info(f"Opening dashboard in default browser: {url}")
        webbrowser.open(url)
    except Exception as e:
        logger.error(f"Failed to automatically open browser: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Trigger bot disconnect cleanly on web server shutdown."""
    logger.info("FastAPI Web Server shutting down. Cleaning up bot engines...")
    await bot_manager.stop()


# Get static path
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    static_dir = os.path.join(sys._MEIPASS, "static")
else:
    static_dir = os.path.join(os.path.dirname(__file__), "static")

if not os.path.exists(static_dir):
    os.makedirs(static_dir)

# API Endpoints

@app.get("/")
async def read_index():
    """Serve index.html at root."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h3>Static dashboard files not created yet! Check directory.</h3>")


@app.get("/api/status")
async def get_status():
    """Get dynamic status of bot execution, Telegram, and MT5 connections."""
    tg_connected = False
    tg_authorized = False
    tg_user = None
    
    if bot_manager.listener and bot_manager.listener.client:
        try:
            tg_connected = bot_manager.listener.client.is_connected()
            if tg_connected:
                tg_authorized = await bot_manager.listener.client.is_user_authorized()
                if tg_authorized:
                    me = await bot_manager.listener.client.get_me()
                    if me:
                        tg_user = f"{me.first_name} (@{me.username})" if me.username else me.first_name
        except Exception as e:
            logger.error(f"Error querying Telegram status: {e}")

    mt5_connected = False
    mt5_account = None
    mt5_broker = None
    
    if mt5 is not None:
        try:
            # Query active account information
            acc = mt5.account_info()
            if acc is not None:
                mt5_connected = True
                mt5_account = acc.login
                mt5_broker = acc.server
        except Exception as e:
            logger.error(f"Error querying MT5 status: {e}")

    return {
        "bot_running": bot_manager.is_running,
        "telegram": {
            "connected": tg_connected,
            "authorized": tg_authorized,
            "user": tg_user
        },
        "mt5": {
            "connected": mt5_connected,
            "account": mt5_account,
            "broker": mt5_broker
        }
    }


@app.post("/api/control")
async def post_control(req: ControlRequest):
    """Start, stop, or restart the bot execution."""
    action = req.action.lower()
    success = False
    
    if action == "start":
        success = await bot_manager.start()
    elif action == "stop":
        success = await bot_manager.stop()
    elif action == "restart":
        success = await bot_manager.restart()
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use start, stop, or restart.")
        
    return {"success": success, "bot_running": bot_manager.is_running}


@app.get("/api/config")
async def get_config():
    """Get active configuration values (excluding MT5 password for security)."""
    cfg_dict = {}
    for field in config.model_fields:
        if field == "mt5_password":
            cfg_dict[field] = "******" if config.mt5_password else ""
        else:
            cfg_dict[field] = getattr(config, field)
    return cfg_dict


@app.post("/api/config")
async def update_config(req: ConfigUpdateRequest):
    """Save configuration changes to .env, reload config object, and restart if running."""
    new_data = req.model_dump()
    
    # Handle password masking: if masked or empty, preserve existing password
    if new_data["mt5_password"] == "******" or not new_data["mt5_password"]:
        new_data["mt5_password"] = config.mt5_password

    try:
        # Validate using Pydantic model
        validated_config = BotConfig(**new_data)
        
        # Apply properties to global configuration object in-place
        for field in validated_config.model_fields:
            setattr(config, field, getattr(validated_config, field))
            
        # Write updates to .env file
        config.save_to_env(new_data)
        logger.info("Configuration saved and reloaded in memory.")
        
        # If running, restart the bot to apply the new configurations (e.g. source chat, login details)
        was_running = bot_manager.is_running
        if was_running:
            logger.info("Restarting bot execution task to apply config updates...")
            await bot_manager.restart()
            
        return {"success": True, "restarted": was_running}
    except Exception as e:
        logger.exception("Error saving configuration updates")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/telegram/chats")
async def get_telegram_chats():
    """Fetch all dialogs/chats for selection from Telethon client."""
    if not bot_manager.listener or not bot_manager.listener.client:
        return {"success": False, "message": "Bot is not running. Please start the bot first to connect to Telegram."}
        
    client = bot_manager.listener.client
    if not client.is_connected():
        return {"success": False, "message": "Telegram client is not connected."}

    try:
        chats = []
        async for dialog in client.iter_dialogs():
            chat_type = "User"
            if dialog.is_channel:
                chat_type = "Channel"
            elif dialog.is_group:
                chat_type = "Group"
                
            # Filter unnamed/empty
            title = dialog.name.strip() if dialog.name else f"Unnamed Chat ({dialog.id})"
            chats.append({
                "id": str(dialog.id),
                "title": title,
                "type": chat_type
            })
            
        return {"success": True, "chats": chats}
    except Exception as e:
        logger.error(f"Error fetching Telegram dialogs: {e}")
        return {"success": False, "message": f"Failed to fetch dialogs: {str(e)}"}


@app.post("/api/parser/test")
async def post_parser_test(req: SignalTestRequest):
    """Test parse raw signal message using current parser configurations."""
    try:
        parsed_signal = parser.parse_signal(req.text)
        return {
            "success": parsed_signal is not None,
            "signal": parsed_signal,
            "raw_text": req.text
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/logs")
async def get_logs():
    """Read the last 150 lines of the bot log file."""
    log_path = "telegram_to_mt5.log"
    if not os.path.exists(log_path):
        return {"success": True, "logs": ["[Log file does not exist yet. Start the bot to create logs.]"]}
        
    try:
        # Open with read-only and ignore encoding issues
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return {"success": True, "logs": [line.strip() for line in lines[-150:]]}
    except Exception as e:
        return {"success": False, "message": f"Failed to read logs: {str(e)}"}


@app.get("/api/risk/channels")
async def get_risk_channels():
    """Retrieve all monitored channel statistics and pause states."""
    try:
        channels = await risk_manager.get_all_channels()
        return {"success": True, "channels": channels}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch channels: {str(e)}")


@app.post("/api/risk/channels/{magic_number}/reset")
async def reset_risk_channel(magic_number: int):
    """Manually reset win/loss streaks and unpause a paused channel."""
    try:
        success = await risk_manager.set_channel_paused(magic_number, False)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset channel: {str(e)}")


@app.get("/api/license/status")
async def get_license_status():
    """Retrieve current license details and validity."""
    try:
        return license_manager.get_license_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve license details: {str(e)}")


@app.get("/api/license/machine-id")
async def get_license_machine_id():
    """Retrieve local computer unique hardware ID."""
    try:
        return {"machine_id": license_manager.get_machine_id()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve machine ID: {str(e)}")


@app.post("/api/license/activate")
async def activate_license(req: LicenseActivateRequest):
    """Attempt to activate the bot with a license key."""
    try:
        success = license_manager.save_license_key(req.key)
        status = license_manager.get_license_status()
        return {"success": success, "status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to activate license: {str(e)}")


# Mount static assets directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")


def run_web_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Launch the Uvicorn server for the FastAPI app."""
    import uvicorn
    uvicorn.run("web_dashboard:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    # Standard startup wrapper
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    run_web_server()
