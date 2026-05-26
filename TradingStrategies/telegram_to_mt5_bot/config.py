"""Configuration module for the Telegram-to-MT5 Signal Automation Bot.

Loads credentials, risk settings, and parsing configurations from environment 
variables and a local .env file.
"""

from typing import Optional, Union, List, Any
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotConfig(BaseSettings):
    """Configuration model for the Telegram to MT5 Signal execution bot."""

    # MetaTrader 5 Connection Settings
    mt5_login: Optional[int] = Field(
        default=None, 
        alias="XAUUSD_BOT_MT5_LOGIN", 
        description="MT5 Account Login ID"
    )
    mt5_password: Optional[str] = Field(
        default=None, 
        alias="XAUUSD_BOT_MT5_PASSWORD", 
        description="MT5 Account Password"
    )
    mt5_server: Optional[str] = Field(
        default=None, 
        alias="XAUUSD_BOT_MT5_SERVER", 
        description="MT5 Broker Server Name"
    )

    # Telegram API Credentials
    telegram_api_id: int = Field(
        ..., 
        alias="TELEGRAM_API_ID", 
        description="Telegram App api_id from my.telegram.org"
    )
    telegram_api_hash: str = Field(
        ..., 
        alias="TELEGRAM_API_HASH", 
        description="Telegram App api_hash from my.telegram.org"
    )
    telegram_source_chat: Optional[str] = Field(
        default=None, 
        alias="TELEGRAM_SOURCE_CHAT", 
        description="Username or ID of the Telegram chat/channel to monitor"
    )

    # Execution Parameters
    default_risk_percent: float = Field(
        default=2.0, 
        alias="TELEGRAM_BOT_DEFAULT_RISK_PERCENT", 
        description="Percentage of account equity to risk per trade"
    )
    magic_number: int = Field(
        default=888999, 
        alias="TELEGRAM_BOT_MAGIC_NUMBER", 
        description="Magic number to identify orders placed by this bot"
    )
    default_symbol: str = Field(
        default="XAUUSD", 
        alias="TELEGRAM_BOT_DEFAULT_SYMBOL", 
        description="Default symbol to trade if not parsed from signal"
    )

    # Risk Management & Position Sizing Engine
    risk_sizing_mode: str = Field(
        default="fixed_lot",
        alias="TELEGRAM_BOT_RISK_SIZING_MODE",
        description="Lot sizing mode: 'fixed_lot' or 'percentage_risk'"
    )
    fixed_lot_size: float = Field(
        default=0.01,
        alias="TELEGRAM_BOT_FIXED_LOT_SIZE",
        description="Fixed lot size if sizing mode is 'fixed_lot'"
    )
    risk_percentage: float = Field(
        default=1.0,
        alias="TELEGRAM_BOT_RISK_PERCENTAGE",
        description="Risk percentage if sizing mode is 'percentage_risk'"
    )
    max_allowed_lot_size: float = Field(
        default=1.0,
        alias="TELEGRAM_BOT_MAX_LOT_SIZE",
        description="Hard safety ceiling cap for lot sizes"
    )

    # Take Profit Splitter Engine
    tp_execution_mode: str = Field(
        default="multiple_tickets",
        alias="TELEGRAM_BOT_TP_EXECUTION_MODE",
        description="TP Execution: 'multiple_tickets' (Separate tickets) or 'single_ticket_partial' (Single ticket with partial closes)"
    )
    tp1_allocation: float = Field(
        default=50.0,
        alias="TELEGRAM_BOT_TP1_ALLOCATION",
        description="TP1 volume allocation percentage"
    )
    tp2_allocation: float = Field(
        default=30.0,
        alias="TELEGRAM_BOT_TP2_ALLOCATION",
        description="TP2 volume allocation percentage"
    )
    tp3_allocation: float = Field(
        default=20.0,
        alias="TELEGRAM_BOT_TP3_ALLOCATION",
        description="TP3 volume allocation percentage"
    )
    move_sl_to_be_on_tp1: bool = Field(
        default=True,
        alias="TELEGRAM_BOT_MOVE_SL_BE",
        description="Move SL to entry price for remaining volume when TP1 is hit"
    )
    fallback_multi_tp_step: float = Field(
        default=20.0,
        alias="TELEGRAM_BOT_FALLBACK_MULTI_TP_STEP",
        description="Fallback step in pips used to calculate TP2 and TP3 if only 1 TP is parsed"
    )

    # Signal Validation & Guard Filters
    max_entry_slippage: float = Field(
        default=5.0,
        alias="TELEGRAM_BOT_MAX_ENTRY_SLIPPAGE",
        description="Max entry slippage in pips"
    )
    default_fallback_sl: float = Field(
        default=30.0,
        alias="TELEGRAM_BOT_DEFAULT_FALLBACK_SL",
        description="Default fallback SL in pips if missing in signal"
    )

    # Account & Channel Circuit Breakers
    max_daily_drawdown_percent: float = Field(
        default=5.0,
        alias="TELEGRAM_BOT_MAX_DAILY_DRAWDOWN_PERCENT",
        description="Max daily drawdown percentage of account balance/equity"
    )
    max_concurrent_open_trades: int = Field(
        default=5,
        alias="TELEGRAM_BOT_MAX_CONCURRENT_OPEN_TRADES",
        description="Max concurrent open trades allowed"
    )
    auto_pause_loss_streak_threshold: int = Field(
        default=5,
        alias="TELEGRAM_BOT_AUTO_PAUSE_LOSS_STREAK_THRESHOLD",
        description="Consecutive loss streak threshold to auto-pause channel payloads"
    )

    # Parsing Settings
    use_llm_parser: bool = Field(
        default=False, 
        alias="TELEGRAM_BOT_USE_LLM_PARSER", 
        description="Toggle local LLM parsing for conversational signals"
    )
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434/", 
        alias="TELEGRAM_BOT_OLLAMA_BASE_URL", 
        description="Base URL for local Ollama API"
    )
    ollama_model: str = Field(
        default="llama3.2", 
        alias="TELEGRAM_BOT_OLLAMA_MODEL", 
        description="Local LLM model to use for signal parsing"
    )

    # Customizable parsing keywords
    sl_keywords: str = Field(
        default="SL,S.L.,S.L,S/L,STOP LOSS,STOPLOSS,STOP-LOSS,STOP_LOSS,STOP,INVALIDATION,INVALID", 
        alias="TELEGRAM_BOT_SL_KEYWORDS", 
        description="Comma-separated Stop Loss keywords"
    )
    tp_keywords: str = Field(
        default="TP,T.P.,T.P,T/P,TAKE PROFIT,TAKEPROFIT,TAKE-PROFIT,TAKE_PROFIT,TARGET,PROFIT", 
        alias="TELEGRAM_BOT_TP_KEYWORDS", 
        description="Comma-separated Take Profit keywords"
    )
    entry_keywords: str = Field(
        default="ENTRY,ENTRY PRICE,@,AT,BUY NOW AT,SELL NOW AT", 
        alias="TELEGRAM_BOT_ENTRY_KEYWORDS", 
        description="Comma-separated Entry Price keywords"
    )

    @model_validator(mode="before")
    @classmethod
    def clean_empty_strings(cls, data: Any) -> Any:
        """Convert empty strings to None/omitted for optional fields to avoid validation errors."""
        if isinstance(data, dict):
            cleaned = {}
            for k, v in data.items():
                if isinstance(v, str) and v.strip() == "":
                    # Convert to None so default fields are used or optional fields remain None
                    cleaned[k] = None
                else:
                    cleaned[k] = v
            return cleaned
        return data

    def save_to_env(self, updates: dict) -> None:
        """Save updated fields back to the .env file.

        Args:
            updates: Dict mapping configuration field names to their new values.
        """
        import os
        
        env_path = self.model_config.get("env_file", ".env")
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        
        # Convert field names to alias names
        alias_updates = {}
        for k, v in updates.items():
            field = self.model_fields.get(k)
            if field and field.alias:
                alias_updates[field.alias] = str(v) if v is not None else ""
            else:
                alias_updates[k] = str(v) if v is not None else ""

        # Update existing keys, track what we updated
        updated_keys = set()
        new_lines = []
        for line in lines:
            line_strip = line.strip()
            if line_strip and not line_strip.startswith("#") and "=" in line_strip:
                key, _ = line_strip.split("=", 1)
                key = key.strip()
                if key in alias_updates:
                    new_lines.append(f"{key}={alias_updates[key]}\n")
                    updated_keys.add(key)
                    continue
            new_lines.append(line)

        # Add any new keys that weren't in the .env file
        for key, val in alias_updates.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={val}\n")

        # Write back to .env
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True
    )


# Instantiate global configuration
config = BotConfig()

