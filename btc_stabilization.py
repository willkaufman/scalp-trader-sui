"""
BTC stabilization detection.
Checks if BTC has stopped making new lows after a dip.
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass

from data.cache import cache, Candle
from config import Config
from utils.indicators import calculate_percentage_change
from utils.logger import logger


@dataclass
class BTCStatus:
    """Current BTC market status."""
    current_price: float
    change_5m: float
    change_15m: float
    change_1h: float
    is_stabilizing: bool
    has_sufficient_dip: bool
    message: str


def get_btc_candles_1m(count: int = 60) -> List[Candle]:
    """Get recent BTC 1-minute candles."""
    return cache.get_candles_1m("BTCUSDT", count)


def is_btc_stabilizing(candles_1m: Optional[List[Candle]] = None) -> bool:
    """
    Check if BTC has stopped making new lows.
    Uses last 5 one-minute candles.
    
    The logic:
    - Get the lowest low of the first 4 candles
    - Compare to the current (5th) candle's low
    - If current low is higher, BTC is stabilizing
    
    Args:
        candles_1m: List of 1-minute candles (optional, will fetch if not provided)
        
    Returns:
        True if BTC appears to be stabilizing
    """
    if candles_1m is None:
        candles_1m = get_btc_candles_1m(5)
    
    if len(candles_1m) < 5:
        logger.debug(f"Not enough BTC candles for stabilization check ({len(candles_1m)}/5)")
        return False
    
    recent_candles = candles_1m[-5:]
    
    # Get the lowest low of the first 4 candles
    lowest_low = min(c.low for c in recent_candles[:-1])
    
    # Get the current candle's low
    current_low = recent_candles[-1].low
    
    # Current candle's low must be higher than the lowest of previous 4
    is_stable = current_low > lowest_low
    
    logger.debug(
        f"BTC stabilization: current_low=${current_low:.2f}, "
        f"lowest_of_prev4=${lowest_low:.2f}, stabilizing={is_stable}"
    )
    
    return is_stable


def calculate_btc_changes() -> Tuple[float, float, float]:
    """
    Calculate BTC price changes over different timeframes.
    
    Returns:
        Tuple of (5m change, 15m change, 1h change) as percentages
    """
    candles = get_btc_candles_1m(60)
    
    if len(candles) < 60:
        # Not enough data, return zeros
        return (0.0, 0.0, 0.0)
    
    current_price = candles[-1].close
    
    # 5-minute change (last 5 candles)
    price_5m_ago = candles[-5].close if len(candles) >= 5 else current_price
    change_5m = calculate_percentage_change(price_5m_ago, current_price)
    
    # 15-minute change
    price_15m_ago = candles[-15].close if len(candles) >= 15 else current_price
    change_15m = calculate_percentage_change(price_15m_ago, current_price)
    
    # 1-hour change
    price_1h_ago = candles[-60].close if len(candles) >= 60 else current_price
    change_1h = calculate_percentage_change(price_1h_ago, current_price)
    
    return (change_5m, change_15m, change_1h)


def has_sufficient_btc_dip(change_1h: Optional[float] = None) -> bool:
    """
    Check if BTC has dropped enough in the last hour to trigger the strategy.
    
    Args:
        change_1h: 1-hour price change (optional, will calculate if not provided)
        
    Returns:
        True if BTC has dropped at least BTC_MIN_DROP_1H
    """
    if change_1h is None:
        _, _, change_1h = calculate_btc_changes()
    
    # Note: BTC_MIN_DROP_1H is negative (e.g., -0.5)
    # We need the change to be MORE negative (a bigger drop)
    return change_1h <= Config.BTC_MIN_DROP_1H


def get_btc_status() -> BTCStatus:
    """
    Get comprehensive BTC status for signal evaluation.
    
    Returns:
        BTCStatus object with all relevant metrics
    """
    candles = get_btc_candles_1m(60)
    
    if len(candles) < 5:
        return BTCStatus(
            current_price=0.0,
            change_5m=0.0,
            change_15m=0.0,
            change_1h=0.0,
            is_stabilizing=False,
            has_sufficient_dip=False,
            message="Insufficient BTC data"
        )
    
    current_price = candles[-1].close
    change_5m, change_15m, change_1h = calculate_btc_changes()
    is_stable = is_btc_stabilizing(candles)
    has_dip = has_sufficient_btc_dip(change_1h)
    
    # Generate status message
    if not has_dip:
        message = f"BTC hasn't dipped enough (1h: {change_1h:+.2f}%, need: {Config.BTC_MIN_DROP_1H}%)"
    elif not is_stable:
        message = f"BTC still making new lows at ${current_price:,.0f}"
    else:
        message = f"BTC stabilizing at ${current_price:,.0f} after {change_1h:+.2f}% dip"
    
    return BTCStatus(
        current_price=current_price,
        change_5m=change_5m,
        change_15m=change_15m,
        change_1h=change_1h,
        is_stabilizing=is_stable,
        has_sufficient_dip=has_dip,
        message=message
    )
