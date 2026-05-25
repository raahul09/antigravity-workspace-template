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

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True
    )


# Instantiate global configuration
config = BotConfig()
