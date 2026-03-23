"""Configuration module for the aggressive MT5 XAUUSD Bot.

This module houses all the static configuration, risk limits, and connection 
parameters required to operate the bot securely and efficiently.
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotConfig(BaseSettings):
    """Primary configuration model for the XAUUSD Trading Bot."""
    
    # API & Account Settings
    mt5_login: Optional[int] = Field(default=None, description="MT5 Account Login ID")
    mt5_password: Optional[str] = Field(default=None, description="MT5 Account Password")
    mt5_server: Optional[str] = Field(default=None, description="MT5 Broker Server Name")
    
    # Trade Identification
    magic_number: int = Field(default=777888, description="Magic number to identify bot trades")
    symbol: str = Field(default="XAUUSD", description="The trading symbol (Gold vs USD)")
    
    # Risk Management (Aggressive 10% cap for $1000 -> $10000 goal)
    max_risk_per_trade_percent: float = Field(
        default=5.0, 
        description="Aggressive risk percentage for rapid compounding."
    )
    max_slippage_points: int = Field(default=10, description="Maximum allowed slippage in points")
    
    # Strategy Settings
    reward_to_risk_target: float = Field(
        default=0.2, 
        description="Hyper-Scalping R:R target to force 80%+ win rates."
    )

    trailing_stop_activation_rr: float = Field(
        default=1.0,
        description="At what R:R the trailing stop should move to break-even or start trailing"
    )

    model_config = SettingsConfigDict(
        env_prefix="XAUUSD_BOT_",
        env_file=".env",
        extra="ignore"
    )

# Global configuration instance
config = BotConfig()
