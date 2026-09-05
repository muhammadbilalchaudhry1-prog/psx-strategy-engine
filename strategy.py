"""Quantitative trading strategy for PSX stocks."""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

from config import (
    ATR_PERIOD,
    EMA_FAST_PERIOD,
    EMA_SLOW_PERIOD,
    SMA_PERIOD,
    Z_SCORE_PERIOD,
    VOL_RATIO_THRESHOLD,
    CONVICTION_BUY_THRESHOLD,
    CONVICTION_SELL_THRESHOLD,
    HIGH_VOL_REGIME_WEIGHTS,
    LOW_VOL_REGIME_WEIGHTS,
    STOP_LOSS_ATR_MULTIPLIER,
)

logger = logging.getLogger(__name__)


@dataclass
class StrategySignal:
    """Represents a trading signal and associated metrics."""
    signal: str  # 'BUY', 'SELL', 'HOLD'
    price: float
    atr: float
    trend_score: float
    z_score: float
    conviction: float
    regime: str
    stop_loss: Optional[float]
    position_size: float
    vol_ratio: float
    confidence: float  # 0.0 to 1.0


class StrategyEngine:
    """Quantitative strategy engine for PSX trading."""
    
    def __init__(self):
        self.logger = logger
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all technical indicators.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with added indicator columns
        """
        df = df.copy()
        
        # 1. Volatility (ATR - Average True Range)
        df['TR'] = np.maximum(
            df['High'] - df['Low'],
            np.maximum(
                abs(df['High'] - df['Close'].shift(1)),
                abs(df['Low'] - df['Close'].shift(1))
            )
        )
        df['ATR'] = df['TR'].rolling(window=ATR_PERIOD).mean()
        
        # 2. Trend Indicators (EMAs)
        df['EMA_12'] = df['Close'].ewm(span=EMA_FAST_PERIOD, adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=EMA_SLOW_PERIOD, adjust=False).mean()
        
        # 3. Trend Score (normalized momentum)
        # Guard against division by zero
        df['Trend_Score'] = 0.0
        mask = df['ATR'] > 0
        df.loc[mask, 'Trend_Score'] = (
            (df.loc[mask, 'EMA_12'] - df.loc[mask, 'EMA_26']) / df.loc[mask, 'ATR']
        )
        
        # 4. Mean Reversion Z-Score
        df['SMA_20'] = df['Close'].rolling(window=SMA_PERIOD).mean()
        df['Std_20'] = df['Close'].rolling(window=Z_SCORE_PERIOD).std()
        
        # Guard against division by zero
        df['Z_Score'] = 0.0
        mask = df['Std_20'] > 0
        df.loc[mask, 'Z_Score'] = (
            (df.loc[mask, 'Close'] - df.loc[mask, 'SMA_20']) / df.loc[mask, 'Std_20']
        )
        
        return df
    
    def generate_signal(self, df: pd.DataFrame, risk_pct: float) -> StrategySignal:
        """
        Generate trading signal based on current market data.
        
        Args:
            df: DataFrame with OHLC data and indicators
            risk_pct: Target risk percentage per trade
            
        Returns:
            StrategySignal object with trading recommendation
        """
        latest = df.iloc[-1]
        
        price = float(latest['Close'])
        atr = float(latest['ATR'])
        trend_score = float(latest['Trend_Score'])
        z_score = float(latest['Z_Score'])
        
        # Volatility analysis
        vol_ratio = atr / price if price > 0 else 0
        
        # Regime detection
        if vol_ratio > VOL_RATIO_THRESHOLD:
            regime = "High Volatility (Sideways/Range)"
            trend_weight, mr_weight = HIGH_VOL_REGIME_WEIGHTS
        else:
            regime = "Low Volatility (Trending)"
            trend_weight, mr_weight = LOW_VOL_REGIME_WEIGHTS
        
        # Conviction score (weighted combination of signals)
        conviction = (trend_weight * trend_score) + (mr_weight * z_score)
        
        # Signal determination
        if conviction > CONVICTION_BUY_THRESHOLD:
            signal = "BUY"
            stop_loss = price - (STOP_LOSS_ATR_MULTIPLIER * atr)
            confidence = min(conviction / 2.0, 1.0)  # Normalize to 0-1
        elif conviction < CONVICTION_SELL_THRESHOLD:
            signal = "SELL"
            stop_loss = price + (STOP_LOSS_ATR_MULTIPLIER * atr)
            confidence = min(abs(conviction) / 2.0, 1.0)
        else:
            signal = "HOLD"
            stop_loss = None
            confidence = 0.5  # Neutral confidence
        
        # Position sizing with guard against extreme volatility
        if vol_ratio > 0:
            pos_size = (risk_pct / 100.0 / vol_ratio) * 100
            pos_size = min(pos_size, 100.0)  # Cap at 100%
        else:
            pos_size = 50.0  # Default to 50% if vol_ratio is zero
        
        return StrategySignal(
            signal=signal,
            price=price,
            atr=atr,
            trend_score=trend_score,
            z_score=z_score,
            conviction=conviction,
            regime=regime,
            stop_loss=stop_loss,
            position_size=pos_size,
            vol_ratio=vol_ratio,
            confidence=confidence
        )
    
    def analyze(self, df: pd.DataFrame, risk_pct: float) -> StrategySignal:
        """
        Complete analysis pipeline: calculate indicators and generate signal.
        
        Args:
            df: DataFrame with OHLC data
            risk_pct: Target risk percentage per trade
            
        Returns:
            StrategySignal object
        """
        df_analyzed = self.calculate_indicators(df)
        signal = self.generate_signal(df_analyzed, risk_pct)
        return signal
