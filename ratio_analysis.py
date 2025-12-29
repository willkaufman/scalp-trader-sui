"""
ALT/BTC ratio analysis.
Calculates RSI and SMA on the altcoin/BTC price ratio.
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass

from data.cache import cache
from config import Config
from utils.indicators import calculate_rsi, calculate_sma, calculate_ratio
from utils.logger import logger


@dataclass
class RatioAnalysis:
    """Result of ALT/BTC ratio analysis."""
    altcoin: str
    current_ratio: float
    ratio_rsi: Optional[float]
    ratio_sma: Optional[float]
    ratio_24h_low: Optional[float]
    is_oversold: bool
    near_24h_low: bool
    message: str


def calculate_ratio_series(altcoin: str, use_15m: bool = True) -> List[float]:
    """
    Calculate the ALT/BTC ratio series.
    
    Args:
        altcoin: The altcoin symbol (e.g., "SUI")
        use_15m: If True, use 15-minute candles; else use 1-minute
        
    Returns:
        List of ratio values (oldest first)
    """
    alt_symbol = f"{altcoin.upper()}USDT"
    btc_symbol = "BTCUSDT"
    
    if use_15m:
        alt_closes = cache.get_closes_15m(alt_symbol)
        btc_closes = cache.get_closes_15m(btc_symbol)
    else:
        alt_closes = cache.get_closes_1m(alt_symbol)
        btc_closes = cache.get_closes_1m(btc_symbol)
    
    # Need same number of data points
    min_len = min(len(alt_closes), len(btc_closes))
    
    if min_len == 0:
        return []
    
    alt_closes = alt_closes[-min_len:]
    btc_closes = btc_closes[-min_len:]
    
    ratios = []
    for alt_price, btc_price in zip(alt_closes, btc_closes):
        ratio = calculate_ratio(alt_price, btc_price)
        if ratio is not None:
            ratios.append(ratio)
    
    return ratios


def get_ratio_rsi(altcoin: str, period: int = 14) -> Optional[float]:
    """
    Calculate RSI on the ALT/BTC ratio.
    
    Args:
        altcoin: The altcoin symbol
        period: RSI period (default 14)
        
    Returns:
        RSI value (0-100) or None if insufficient data
    """
    ratios = calculate_ratio_series(altcoin, use_15m=True)
    
    if len(ratios) < period + 1:
        logger.debug(f"Not enough ratio data for RSI ({len(ratios)}/{period + 1})")
        return None
    
    return calculate_rsi(ratios, period)


def get_ratio_sma(altcoin: str, period: int = 20) -> Optional[float]:
    """
    Calculate SMA on the ALT/BTC ratio.
    
    Args:
        altcoin: The altcoin symbol
        period: SMA period (default 20)
        
    Returns:
        SMA value or None if insufficient data
    """
    ratios = calculate_ratio_series(altcoin, use_15m=True)
    return calculate_sma(ratios, period)


def get_ratio_24h_low(altcoin: str) -> Optional[float]:
    """
    Get the 24-hour low of the ALT/BTC ratio.
    Uses 15-minute candles (96 candles = 24 hours).
    
    Args:
        altcoin: The altcoin symbol
        
    Returns:
        The lowest ratio value in last 24 hours
    """
    ratios = calculate_ratio_series(altcoin, use_15m=True)
    
    # 24 hours = 96 15-minute candles
    if len(ratios) < 96:
        # Use what we have
        if not ratios:
            return None
        return min(ratios)
    
    return min(ratios[-96:])


def get_current_ratio(altcoin: str) -> Optional[float]:
    """
    Get the current ALT/BTC ratio.
    
    Args:
        altcoin: The altcoin symbol
        
    Returns:
        Current ratio or None if prices unavailable
    """
    alt_symbol = f"{altcoin.upper()}USDT"
    
    alt_price = cache.get_current_price(alt_symbol)
    btc_price = cache.get_current_price("BTCUSDT")
    
    if alt_price is None or btc_price is None:
        return None
    
    return calculate_ratio(alt_price, btc_price)


def is_near_24h_low(current_ratio: float, low_ratio: float, threshold_pct: float = 1.0) -> bool:
    """
    Check if current ratio is within threshold of 24h low.
    
    Args:
        current_ratio: Current ALT/BTC ratio
        low_ratio: 24-hour low ratio
        threshold_pct: How close to be considered "near" (default 1%)
        
    Returns:
        True if within threshold of the low
    """
    if low_ratio == 0:
        return False
    
    # Calculate how far we are from the low as a percentage
    distance = ((current_ratio - low_ratio) / low_ratio) * 100
    
    return distance <= threshold_pct


def analyze_ratio(altcoin: str) -> RatioAnalysis:
    """
    Perform complete ratio analysis for an altcoin.
    
    Checks:
    1. RSI below oversold threshold (default 35)
    2. OR ratio near 24h low (within 1%)
    
    Args:
        altcoin: The altcoin symbol
        
    Returns:
        RatioAnalysis with all metrics
    """
    current_ratio = get_current_ratio(altcoin)
    
    if current_ratio is None:
        return RatioAnalysis(
            altcoin=altcoin,
            current_ratio=0.0,
            ratio_rsi=None,
            ratio_sma=None,
            ratio_24h_low=None,
            is_oversold=False,
            near_24h_low=False,
            message="Insufficient data for ratio analysis"
        )
    
    ratio_rsi = get_ratio_rsi(altcoin, Config.RSI_PERIOD)
    ratio_sma = get_ratio_sma(altcoin, Config.SMA_PERIOD)
    ratio_24h_low = get_ratio_24h_low(altcoin)
    
    # Check conditions
    is_oversold = ratio_rsi is not None and ratio_rsi < Config.RATIO_RSI_OVERSOLD
    near_low = (
        ratio_24h_low is not None and 
        is_near_24h_low(current_ratio, ratio_24h_low)
    )
    
    # Generate message
    messages = []
    if is_oversold:
        messages.append(f"RSI({Config.RSI_PERIOD})={ratio_rsi:.1f} (oversold)")
    elif ratio_rsi is not None:
        messages.append(f"RSI({Config.RSI_PERIOD})={ratio_rsi:.1f}")
    
    if near_low:
        messages.append("Near 24h low")
    
    if not is_oversold and not near_low:
        message = f"✗ {altcoin}/BTC ratio not oversold"
    else:
        message = f"✓ {altcoin}/BTC: " + ", ".join(messages)
    
    logger.debug(
        f"Ratio analysis [{altcoin}]: ratio={current_ratio:.10f}, "
        f"RSI={ratio_rsi:.1f if ratio_rsi else 'N/A'}, "
        f"oversold={is_oversold}, near_low={near_low}"
    )
    
    return RatioAnalysis(
        altcoin=altcoin,
        current_ratio=current_ratio,
        ratio_rsi=ratio_rsi,
        ratio_sma=ratio_sma,
        ratio_24h_low=ratio_24h_low,
        is_oversold=is_oversold,
        near_24h_low=near_low,
        message=message
    )
