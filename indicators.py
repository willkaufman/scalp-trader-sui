"""
Technical indicator calculations.
Implements RSI, SMA, and other indicators from scratch.
"""

from typing import List, Optional
from collections import deque


def calculate_sma(values: List[float], period: int) -> Optional[float]:
    """
    Calculate Simple Moving Average.
    
    Args:
        values: List of values (most recent last)
        period: Number of periods for SMA
        
    Returns:
        SMA value or None if insufficient data
    """
    if len(values) < period:
        return None
    
    return sum(values[-period:]) / period


def calculate_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """
    Calculate Relative Strength Index.
    
    Uses the standard Wilder's smoothing method.
    
    Args:
        closes: List of closing prices (most recent last)
        period: RSI period (default 14)
        
    Returns:
        RSI value (0-100) or None if insufficient data
    """
    if len(closes) < period + 1:
        return None
    
    # Calculate price changes
    changes = []
    for i in range(1, len(closes)):
        changes.append(closes[i] - closes[i - 1])
    
    # Separate gains and losses
    gains = [max(0, change) for change in changes]
    losses = [abs(min(0, change)) for change in changes]
    
    # Calculate initial average gain and loss
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # Apply Wilder's smoothing for remaining periods
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    # Calculate RSI
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_percentage_change(old_price: float, new_price: float) -> float:
    """
    Calculate percentage change between two prices.
    
    Args:
        old_price: Starting price
        new_price: Ending price
        
    Returns:
        Percentage change (e.g., -2.5 for -2.5%)
    """
    if old_price == 0:
        return 0.0
    
    return ((new_price - old_price) / old_price) * 100


def calculate_ratio(numerator: float, denominator: float) -> Optional[float]:
    """
    Calculate ratio of two values.
    
    Args:
        numerator: Top value
        denominator: Bottom value
        
    Returns:
        Ratio or None if denominator is zero
    """
    if denominator == 0:
        return None
    
    return numerator / denominator


def get_24h_low(candles: List[dict]) -> Optional[float]:
    """
    Get the 24-hour low from candle data.
    
    Args:
        candles: List of candle dicts with 'low' key
        
    Returns:
        Lowest low price or None if no data
    """
    if not candles:
        return None
    
    return min(c['low'] for c in candles)


def get_24h_high(candles: List[dict]) -> Optional[float]:
    """
    Get the 24-hour high from candle data.
    
    Args:
        candles: List of candle dicts with 'high' key
        
    Returns:
        Highest high price or None if no data
    """
    if not candles:
        return None
    
    return max(c['high'] for c in candles)


class RollingIndicator:
    """
    Maintains rolling calculations for efficient updates.
    """
    
    def __init__(self, period: int):
        self.period = period
        self.values: deque = deque(maxlen=period)
    
    def add_value(self, value: float) -> None:
        """Add a new value to the rolling window."""
        self.values.append(value)
    
    def get_sma(self) -> Optional[float]:
        """Get current SMA."""
        if len(self.values) < self.period:
            return None
        return sum(self.values) / len(self.values)
    
    def is_ready(self) -> bool:
        """Check if we have enough data."""
        return len(self.values) >= self.period
