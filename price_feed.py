"""
Real-time price feed using Binance WebSocket streams.
Handles connection, reconnection, and data parsing.
"""

import asyncio
import json
from typing import List, Optional, Callable, Set
from datetime import datetime
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from config import Config
from data.cache import cache, Candle
from utils.logger import logger, log_websocket_event, log_error


class BinancePriceFeed:
    """
    Manages WebSocket connections to Binance for real-time price data.
    Subscribes to kline (candlestick) streams for BTC and altcoins.
    """
    
    BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
    BINANCE_FUTURES_WS_URL = "wss://fstream.binance.com/ws"
    
    # Reconnection settings
    MAX_RECONNECT_ATTEMPTS = 10
    INITIAL_RECONNECT_DELAY = 1.0  # seconds
    MAX_RECONNECT_DELAY = 60.0  # seconds
    
    def __init__(self, altcoins: Optional[List[str]] = None):
        """
        Initialize the price feed.
        
        Args:
            altcoins: List of altcoin symbols to monitor (e.g., ["SUI", "SOL"])
        """
        self.altcoins = [coin.upper() for coin in (altcoins or Config.get_altcoins())]
        self._ws = None
        self._running = False
        self._reconnect_attempts = 0
        self._on_candle_callbacks: List[Callable] = []
        self._subscribed_streams: Set[str] = set()
    
    def _get_streams(self) -> List[str]:
        """Generate list of streams to subscribe to."""
        streams = []
        
        # BTC streams (always included)
        streams.append("btcusdt@kline_1m")
        streams.append("btcusdt@kline_15m")
        
        # Altcoin streams
        for coin in self.altcoins:
            symbol = f"{coin.lower()}usdt"
            streams.append(f"{symbol}@kline_1m")
            streams.append(f"{symbol}@kline_15m")
        
        return streams
    
    def _get_combined_stream_url(self) -> str:
        """Build the combined stream URL."""
        streams = self._get_streams()
        stream_string = "/".join(streams)
        return f"{self.BINANCE_WS_URL}/{stream_string}"
    
    def add_candle_callback(self, callback: Callable) -> None:
        """Add a callback to be called when a new candle is received."""
        self._on_candle_callbacks.append(callback)
    
    def _parse_kline_message(self, data: dict) -> Optional[tuple]:
        """
        Parse a kline WebSocket message.
        
        Returns:
            Tuple of (symbol, timeframe, candle) or None if invalid
        """
        try:
            if 'e' not in data or data['e'] != 'kline':
                return None
            
            kline = data['k']
            symbol = kline['s'].upper()  # e.g., "BTCUSDT"
            interval = kline['i']  # e.g., "1m", "15m"
            
            candle = Candle(
                timestamp=int(kline['t']),
                open=float(kline['o']),
                high=float(kline['h']),
                low=float(kline['l']),
                close=float(kline['c']),
                volume=float(kline['v']),
                is_closed=kline['x']
            )
            
            return (symbol, interval, candle)
            
        except (KeyError, ValueError) as e:
            log_error("parse_kline", e)
            return None
    
    def _process_candle(self, symbol: str, interval: str, candle: Candle) -> None:
        """Process and cache a received candle."""
        # Add to appropriate cache
        if interval == "1m":
            cache.add_candle_1m(symbol, candle)
        elif interval == "15m":
            cache.add_candle_15m(symbol, candle)
        
        # Notify callbacks only for closed candles
        if candle.is_closed:
            for callback in self._on_candle_callbacks:
                try:
                    callback(symbol, interval, candle)
                except Exception as e:
                    log_error("candle_callback", e)
    
    async def _handle_message(self, message: str) -> None:
        """Handle an incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            # Handle combined stream format
            if 'stream' in data and 'data' in data:
                data = data['data']
            
            result = self._parse_kline_message(data)
            if result:
                symbol, interval, candle = result
                self._process_candle(symbol, interval, candle)
                
        except json.JSONDecodeError as e:
            log_error("json_decode", e)
    
    async def _connect(self) -> None:
        """Establish WebSocket connection."""
        url = self._get_combined_stream_url()
        log_websocket_event("CONNECTING", url[:100] + "...")
        
        try:
            self._ws = await websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5
            )
            self._reconnect_attempts = 0
            log_websocket_event("CONNECTED", f"Streams: {len(self._get_streams())}")
            
        except Exception as e:
            log_error("websocket_connect", e)
            raise
    
    async def _listen(self) -> None:
        """Listen for incoming messages."""
        try:
            async for message in self._ws:
                if not self._running:
                    break
                await self._handle_message(message)
                
        except ConnectionClosed as e:
            log_websocket_event("DISCONNECTED", f"Code: {e.code}, Reason: {e.reason}")
            raise
        except Exception as e:
            log_error("websocket_listen", e)
            raise
    
    async def _reconnect(self) -> bool:
        """
        Attempt to reconnect with exponential backoff.
        
        Returns:
            True if reconnection successful, False if max attempts reached
        """
        if self._reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
            logger.error("Max reconnection attempts reached")
            return False
        
        self._reconnect_attempts += 1
        delay = min(
            self.INITIAL_RECONNECT_DELAY * (2 ** (self._reconnect_attempts - 1)),
            self.MAX_RECONNECT_DELAY
        )
        
        log_websocket_event(
            "RECONNECTING", 
            f"Attempt {self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS}, "
            f"waiting {delay:.1f}s"
        )
        
        await asyncio.sleep(delay)
        
        try:
            await self._connect()
            return True
        except Exception:
            return await self._reconnect()
    
    async def run(self) -> None:
        """
        Main run loop. Connects and maintains the WebSocket connection.
        """
        self._running = True
        
        while self._running:
            try:
                await self._connect()
                await self._listen()
                
            except (ConnectionClosed, WebSocketException):
                if self._running:
                    success = await self._reconnect()
                    if not success:
                        logger.error("Failed to reconnect, stopping price feed")
                        break
                        
            except Exception as e:
                log_error("price_feed_run", e)
                if self._running:
                    await asyncio.sleep(5)
    
    async def stop(self) -> None:
        """Stop the price feed."""
        self._running = False
        if self._ws:
            await self._ws.close()
            log_websocket_event("STOPPED", "Connection closed")
    
    def is_running(self) -> bool:
        """Check if the price feed is running."""
        return self._running and self._ws is not None


async def fetch_historical_candles(
    symbol: str, 
    interval: str = "1m", 
    limit: int = 100
) -> List[Candle]:
    """
    Fetch historical candles via REST API for initial data.
    
    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        interval: Candle interval (e.g., "1m", "15m")
        limit: Number of candles to fetch
        
    Returns:
        List of Candle objects
    """
    import aiohttp
    
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol.upper(),
        "interval": interval,
        "limit": limit
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch candles: {response.status}")
                    return []
                
                data = await response.json()
                
                candles = []
                for item in data:
                    candle = Candle(
                        timestamp=int(item[0]),
                        open=float(item[1]),
                        high=float(item[2]),
                        low=float(item[3]),
                        close=float(item[4]),
                        volume=float(item[5]),
                        is_closed=True  # Historical candles are always closed
                    )
                    candles.append(candle)
                
                logger.info(f"Fetched {len(candles)} historical {interval} candles for {symbol}")
                return candles
                
    except Exception as e:
        log_error("fetch_historical_candles", e)
        return []


async def initialize_cache(altcoins: List[str]) -> None:
    """
    Initialize the cache with historical data.
    
    Args:
        altcoins: List of altcoin symbols
    """
    logger.info("Initializing cache with historical data...")
    
    symbols = ["BTCUSDT"] + [f"{coin}USDT" for coin in altcoins]
    
    for symbol in symbols:
        # Fetch 1-minute candles
        candles_1m = await fetch_historical_candles(symbol, "1m", 100)
        for candle in candles_1m:
            cache.add_candle_1m(symbol, candle)
        
        # Fetch 15-minute candles
        candles_15m = await fetch_historical_candles(symbol, "15m", 50)
        for candle in candles_15m:
            cache.add_candle_15m(symbol, candle)
        
        # Small delay to avoid rate limiting
        await asyncio.sleep(0.2)
    
    logger.info("Cache initialization complete")
