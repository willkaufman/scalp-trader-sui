"""
In-memory cache for candle data and other frequently accessed data.
"""

from collections import deque
from typing import Dict, List, Optional, Deque
from dataclasses import dataclass, field
from datetime import datetime
import threading
from config import Config
from utils.logger import logger


@dataclass
class Candle:
    """Represents a single candlestick."""
    timestamp: int  # Unix timestamp in milliseconds
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = True
    
    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'is_closed': self.is_closed
        }


class CandleCache:
    """
    Thread-safe cache for storing candle data.
    Maintains separate buffers for different timeframes.
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # 1-minute candles per symbol
        self._candles_1m: Dict[str, Deque[Candle]] = {}
        
        # 15-minute candles per symbol  
        self._candles_15m: Dict[str, Deque[Candle]] = {}
        
        # Current (incomplete) candle per symbol and timeframe
        self._current_1m: Dict[str, Optional[Candle]] = {}
        self._current_15m: Dict[str, Optional[Candle]] = {}
        
        # Funding rates per symbol
        self._funding_rates: Dict[str, float] = {}
        
        # Last update timestamps
        self._last_update: Dict[str, datetime] = {}
    
    def _get_or_create_buffer(
        self, 
        buffers: Dict[str, Deque[Candle]], 
        symbol: str, 
        maxlen: int
    ) -> Deque[Candle]:
        """Get or create a candle buffer for a symbol."""
        if symbol not in buffers:
            buffers[symbol] = deque(maxlen=maxlen)
        return buffers[symbol]
    
    def add_candle_1m(self, symbol: str, candle: Candle) -> None:
        """
        Add a 1-minute candle to the cache.
        Only adds closed candles; updates current candle for open ones.
        """
        symbol = symbol.upper()
        
        with self._lock:
            if candle.is_closed:
                buffer = self._get_or_create_buffer(
                    self._candles_1m, 
                    symbol, 
                    Config.CANDLES_1M_BUFFER
                )
                buffer.append(candle)
                self._current_1m[symbol] = None
            else:
                self._current_1m[symbol] = candle
            
            self._last_update[f"{symbol}_1m"] = datetime.utcnow()
    
    def add_candle_15m(self, symbol: str, candle: Candle) -> None:
        """Add a 15-minute candle to the cache."""
        symbol = symbol.upper()
        
        with self._lock:
            if candle.is_closed:
                buffer = self._get_or_create_buffer(
                    self._candles_15m, 
                    symbol, 
                    Config.CANDLES_15M_BUFFER
                )
                buffer.append(candle)
                self._current_15m[symbol] = None
            else:
                self._current_15m[symbol] = candle
            
            self._last_update[f"{symbol}_15m"] = datetime.utcnow()
    
    def get_candles_1m(self, symbol: str, count: Optional[int] = None) -> List[Candle]:
        """
        Get 1-minute candles for a symbol.
        
        Args:
            symbol: Trading pair symbol
            count: Number of candles to return (None for all)
            
        Returns:
            List of candles (oldest first)
        """
        symbol = symbol.upper()
        
        with self._lock:
            if symbol not in self._candles_1m:
                return []
            
            candles = list(self._candles_1m[symbol])
            
            if count is not None:
                candles = candles[-count:]
            
            return candles
    
    def get_candles_15m(self, symbol: str, count: Optional[int] = None) -> List[Candle]:
        """Get 15-minute candles for a symbol."""
        symbol = symbol.upper()
        
        with self._lock:
            if symbol not in self._candles_15m:
                return []
            
            candles = list(self._candles_15m[symbol])
            
            if count is not None:
                candles = candles[-count:]
            
            return candles
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get the most recent price for a symbol."""
        symbol = symbol.upper()
        
        with self._lock:
            # Try current candle first
            if symbol in self._current_1m and self._current_1m[symbol]:
                return self._current_1m[symbol].close
            
            # Fall back to last closed candle
            if symbol in self._candles_1m and self._candles_1m[symbol]:
                return self._candles_1m[symbol][-1].close
            
            return None
    
    def get_closes_1m(self, symbol: str, count: Optional[int] = None) -> List[float]:
        """Get closing prices from 1-minute candles."""
        candles = self.get_candles_1m(symbol, count)
        return [c.close for c in candles]
    
    def get_closes_15m(self, symbol: str, count: Optional[int] = None) -> List[float]:
        """Get closing prices from 15-minute candles."""
        candles = self.get_candles_15m(symbol, count)
        return [c.close for c in candles]
    
    def set_funding_rate(self, symbol: str, rate: float) -> None:
        """Set funding rate for a symbol."""
        symbol = symbol.upper()
        with self._lock:
            self._funding_rates[symbol] = rate
            self._last_update[f"{symbol}_funding"] = datetime.utcnow()
    
    def get_funding_rate(self, symbol: str) -> Optional[float]:
        """Get funding rate for a symbol."""
        symbol = symbol.upper()
        with self._lock:
            return self._funding_rates.get(symbol)
    
    def get_last_update(self, key: str) -> Optional[datetime]:
        """Get last update time for a cache key."""
        with self._lock:
            return self._last_update.get(key)
    
    def get_status(self) -> dict:
        """Get cache status for health check."""
        with self._lock:
            status = {
                'candles_1m': {
                    symbol: len(candles) 
                    for symbol, candles in self._candles_1m.items()
                },
                'candles_15m': {
                    symbol: len(candles) 
                    for symbol, candles in self._candles_15m.items()
                },
                'funding_rates': dict(self._funding_rates),
                'last_updates': {
                    k: v.isoformat() 
                    for k, v in self._last_update.items()
                }
            }
            return status
    
    def clear(self) -> None:
        """Clear all cached data."""
        with self._lock:
            self._candles_1m.clear()
            self._candles_15m.clear()
            self._current_1m.clear()
            self._current_15m.clear()
            self._funding_rates.clear()
            self._last_update.clear()
            logger.info("Cache cleared")


# Global cache instance
cache = CandleCache()
