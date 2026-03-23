"""Liquidity Engine for Smart Money Concepts (SMC).

This module manages the detection of 15M sequence swing points (liquidity pools)
and monitors 1M/5M price action for liquidity sweeps accompanied by 
changes of character (CHoCH) indicating a market reversal setup.
"""

from typing import Optional, Dict
import pandas as pd
import numpy as np

class LiquidityEngine:
    def __init__(self, swing_lookback: int = 5, ema_period: int = 50):
        """Initialize the liquidity engine.
        
        Args:
            swing_lookback (int): Number of candles to the left and right required 
            to qualify a wick as a valid swing high/low.
            ema_period (int): Lookback for the 15M trend filter.
        """
        self.swing_lookback = swing_lookback
        self.ema_period = ema_period
        self.active_swing_highs = []
        self.active_swing_lows = []
        
    def find_15m_swing_points(self, df_15m: pd.DataFrame) -> None:
        """Analyze a 15M DataFrame to identify structural swing highs and lows.
        
        A swing high requires N lower highs on the left and right.
        A swing low requires N higher lows on the left and right.
        
        Args:
            df_15m (pd.DataFrame): DataFrame of 15m OHLCV data.
        """
        if df_15m is None or len(df_15m) < self.swing_lookback * 2 + 1:
            return

        self.active_swing_highs.clear()
        self.active_swing_lows.clear()
        
        # Simple rolling logic for swings. For a true SMC bot, this would be highly refined.
        for i in range(self.swing_lookback, len(df_15m) - self.swing_lookback):
            window = df_15m.iloc[i - self.swing_lookback : i + self.swing_lookback + 1]
            
            # Check swing high (current high is the highest in the window)
            if df_15m['high'].iloc[i] == window['high'].max():
                self.active_swing_highs.append({
                    'price': df_15m['high'].iloc[i],
                    'time': df_15m.index[i]
                })
                
            # Check swing low (current low is the lowest in the window)
            if df_15m['low'].iloc[i] == window['low'].min():
                self.active_swing_lows.append({
                    'price': df_15m['low'].iloc[i],
                    'time': df_15m.index[i]
                })

    def detect_liquidity_sweep(self, current_price: float, current_1m: pd.DataFrame, df_15m_context: pd.DataFrame = None) -> Optional[Dict[str, float]]:
        """Determine if current 1M price action has swept a 15M swing point and reversed.
        
        Args:
            current_price (float): The current Bid/Ask price.
            current_1m (pd.DataFrame): The latest 1M OHLCV data to confirm reversal (CHoCH).
            df_15m_context (pd.DataFrame): 15M dataframe for trend filtering.
            
        Returns:
            Optional[Dict[str, float]]: A dictionary with setup details if a sweep is confirmed.
        """
        if not self.active_swing_highs and not self.active_swing_lows:
            return None
            
        if len(current_1m) < 2:
            return None
            
        # Get the latest COMPLETELY CLOSED 1M candle
        last_closed_candle = current_1m.iloc[-2]
        
        # Calculate 50 EMA Trend and 14 RSI if provided
        trend_direction = 0  # 1 for UP, -1 for DOWN
        rsi_value = 50.0
        
        if df_15m_context is not None and len(df_15m_context) >= self.ema_period:
            ema = df_15m_context['close'].ewm(span=self.ema_period, adjust=False).mean()
            last_15m_close = df_15m_context['close'].iloc[-1]
            last_ema = ema.iloc[-1]
            if last_15m_close > last_ema:
                trend_direction = 1
            elif last_15m_close < last_ema:
                trend_direction = -1
                
            # Calculate 14-period RSI
            delta = df_15m_context['close'].diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            rsi_value = rsi.iloc[-1]

        candle_high = last_closed_candle['high']
        candle_low = last_closed_candle['low']
        candle_open = last_closed_candle['open']
        candle_close = last_closed_candle['close']
        candle_range = candle_high - candle_low

        # Check Bearish Sweep (Only if trend is DOWN/Neutral AND RSI is slightly high)
        if trend_direction <= 0 and rsi_value > 55:
            for sh in self.active_swing_highs:
                if candle_high > sh['price']:
                    # Criteria: Candle sweeps above, and closes below the swing high.
                    if candle_close < sh['price']:
                        return {
                            'direction': -1,  # Sell setup
                            'stop_loss': candle_high, 
                            'swing_level': sh['price']
                        }
                        
        # Check Bullish Sweep (Only if trend is UP/Neutral AND RSI is slightly low)
        if trend_direction >= 0 and rsi_value < 45:
            for sl in self.active_swing_lows:
                if candle_low < sl['price']:
                    # Criteria: Candle sweeps below, and closes above the swing low.
                    if candle_close > sl['price']:
                        return {
                            'direction': 1,  # Buy setup
                            'stop_loss': candle_low, 
                            'swing_level': sl['price']
                        }


        return None
