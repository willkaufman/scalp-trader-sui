"""
Altcoin underperformance detection.
Calculates how much an altcoin has underperformed BTC.
"""

from typing import Optional, Tuple
from dataclasses import dataclass

from data.cache import cache
from config import Config
from utils.indicators import calculate_percentage_change
from utils.logger import logger


@dataclass
class UnderperformanceResult:
    """Result of underperformance calculation."""
    altcoin: str
    btc_change_1h: float
    alt_change_1h: float
    spread: float  # alt_change - btc_change (negative = underperforming)
    is_underperforming: bool
    is_strong_signal: bool
    message: str


def calculate_price_changes(symbol: str, lookback_minutes: int = 60) -> Tuple[float, float, float]:
    """
    Calculate price changes for a symbol over different timeframes.
    
    Args:
        symbol: The trading symbol (e.g., "SUIUSDT")
        lookback_minutes: How many 1-minute candles to look back
        
    Returns:
        Tuple of (5m change, 15m change, 1h change) as percentages
    """
    candles = cache.get_candles_1m(symbol, lookback_minutes)
    
    if len(candles) < lookback_minutes:
        # Not enough data
        return (0.0, 0.0, 0.0)
    
    current_price = candles[-1].close
    
    # 5-minute change
    price_5m_ago = candles[-5].close if len(candles) >= 5 else current_price
    change_5m = calculate_percentage_change(price_5m_ago, current_price)
    
    # 15-minute change
    price_15m_ago = candles[-15].close if len(candles) >= 15 else current_price
    change_15m = calculate_percentage_change(price_15m_ago, current_price)
    
    # 1-hour change
    price_1h_ago = candles[-60].close if len(candles) >= 60 else current_price
    change_1h = calculate_percentage_change(price_1h_ago, current_price)
    
    return (change_5m, change_15m, change_1h)


def calculate_underperformance(
    altcoin: str,
    btc_change_1h: Optional[float] = None
) -> UnderperformanceResult:
    """
    Calculate how much an altcoin has underperformed BTC.
    
    The "underperformance spread" is:
        spread = altcoin_change_1h - btc_change_1h
    
    Example:
        BTC: -1.5%, SUI: -3.8%
        spread = -3.8 - (-1.5) = -2.3%
        (SUI underperformed by 2.3%)
    
    Args:
        altcoin: The altcoin symbol (e.g., "SUI")
        btc_change_1h: Pre-calculated BTC 1h change (optional)
        
    Returns:
        UnderperformanceResult with all metrics
    """
    symbol = f"{altcoin.upper()}USDT"
    
    # Get altcoin price changes
    alt_5m, alt_15m, alt_1h = calculate_price_changes(symbol)
    
    # Get BTC price changes if not provided
    if btc_change_1h is None:
        _, _, btc_change_1h = calculate_price_changes("BTCUSDT")
    
    # Calculate spread
    spread = alt_1h - btc_change_1h
    
    # Check thresholds
    # Note: UNDERPERFORMANCE_THRESHOLD is negative (e.g., -1.0)
    is_underperforming = spread <= Config.UNDERPERFORMANCE_THRESHOLD
    is_strong = spread <= Config.UNDERPERFORMANCE_STRONG
    
    # Generate message
    if is_strong:
        message = f"🔥 STRONG: {altcoin} underperformed BTC by {abs(spread):.2f}%"
    elif is_underperforming:
        message = f"✓ {altcoin} underperformed BTC by {abs(spread):.2f}%"
    else:
        message = f"✗ {altcoin} spread ({spread:+.2f}%) not significant enough"
    
    logger.debug(
        f"Underperformance [{altcoin}]: BTC={btc_change_1h:+.2f}%, "
        f"ALT={alt_1h:+.2f}%, spread={spread:+.2f}%"
    )
    
    return UnderperformanceResult(
        altcoin=altcoin,
        btc_change_1h=btc_change_1h,
        alt_change_1h=alt_1h,
        spread=spread,
        is_underperforming=is_underperforming,
        is_strong_signal=is_strong,
        message=message
    )


def get_current_price(altcoin: str) -> Optional[float]:
    """Get the current price of an altcoin."""
    symbol = f"{altcoin.upper()}USDT"
    return cache.get_current_price(symbol)


def get_all_changes(altcoin: str) -> dict:
    """
    Get all price changes for an altcoin.
    
    Returns:
        Dict with 5m, 15m, 1h changes
    """
    symbol = f"{altcoin.upper()}USDT"
    change_5m, change_15m, change_1h = calculate_price_changes(symbol)
    
    return {
        'change_5m': change_5m,
        'change_15m': change_15m,
        'change_1h': change_1h
    }
