"""
Liquidation data fetching from Coinglass API.
This is an optional module - the system works without it.
Provides liquidation heatmap data for additional signal context.
"""

import asyncio
import aiohttp
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime

from config import Config
from utils.logger import logger, log_error, log_data_update


@dataclass
class LiquidationCluster:
    """Represents a liquidation cluster at a price level."""
    price: float
    total_value_usd: float
    is_long: bool  # True if long liquidations, False if short
    distance_percent: float  # Distance from current price as percentage


@dataclass
class LiquidationData:
    """Aggregated liquidation data for a symbol."""
    symbol: str
    timestamp: datetime
    current_price: float
    clusters_above: List[LiquidationCluster]  # Short liquidations above
    clusters_below: List[LiquidationCluster]  # Long liquidations below
    
    def get_nearest_below(self, within_percent: float = 1.5) -> Optional[LiquidationCluster]:
        """Get the largest liquidation cluster below current price within threshold."""
        eligible = [c for c in self.clusters_below if c.distance_percent <= within_percent]
        if not eligible:
            return None
        return max(eligible, key=lambda x: x.total_value_usd)
    
    def get_nearest_above(self, within_percent: float = 2.0) -> Optional[LiquidationCluster]:
        """Get the largest liquidation cluster above current price within threshold."""
        eligible = [c for c in self.clusters_above if c.distance_percent <= within_percent]
        if not eligible:
            return None
        return max(eligible, key=lambda x: x.total_value_usd)


class LiquidationFetcher:
    """
    Fetches liquidation heatmap data from Coinglass.
    Note: This requires a Coinglass API key and may require a paid plan.
    """
    
    COINGLASS_LIQUIDATION_URL = "https://open-api.coinglass.com/public/v2/liquidation_heatmap"
    
    def __init__(self, altcoins: Optional[List[str]] = None):
        """
        Initialize the liquidation fetcher.
        
        Args:
            altcoins: List of altcoin symbols to monitor
        """
        self.altcoins = [coin.upper() for coin in (altcoins or Config.get_altcoins())]
        self._running = False
        self._cache: Dict[str, LiquidationData] = {}
        self._last_fetch: Optional[datetime] = None
        self._enabled = bool(Config.COINGLASS_API_KEY)
    
    async def _fetch_liquidation_data(self, symbol: str) -> Optional[LiquidationData]:
        """
        Fetch liquidation heatmap data for a symbol.
        
        Args:
            symbol: The base symbol (e.g., "BTC", "SUI")
            
        Returns:
            LiquidationData or None if failed/unavailable
        """
        if not Config.COINGLASS_API_KEY:
            return None
        
        headers = {
            "accept": "application/json",
            "coinglassSecret": Config.COINGLASS_API_KEY
        }
        
        params = {
            "symbol": symbol.upper(),
            "interval": "1h"  # 1-hour liquidation data
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.COINGLASS_LIQUIDATION_URL,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 403:
                        logger.warning("Coinglass liquidation API requires paid plan")
                        self._enabled = False
                        return None
                    
                    if response.status != 200:
                        logger.warning(f"Coinglass liquidation API error: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    if not data.get("success") or not data.get("data"):
                        return None
                    
                    return self._parse_liquidation_data(symbol, data["data"])
                    
        except Exception as e:
            log_error("liquidation_fetch", e)
            return None
    
    def _parse_liquidation_data(self, symbol: str, data: dict) -> Optional[LiquidationData]:
        """
        Parse raw liquidation data into our data structure.
        
        Note: The actual structure depends on Coinglass API response format.
        This is a best-effort implementation that may need adjustment.
        """
        try:
            current_price = float(data.get("price", 0))
            if current_price == 0:
                return None
            
            clusters_above = []
            clusters_below = []
            
            # Parse price levels with liquidation volumes
            levels = data.get("levels", [])
            
            for level in levels:
                price = float(level.get("price", 0))
                long_value = float(level.get("longLiquidationUsd", 0))
                short_value = float(level.get("shortLiquidationUsd", 0))
                
                if price == 0:
                    continue
                
                distance = ((price - current_price) / current_price) * 100
                
                if price > current_price and short_value > 0:
                    # Short liquidations above current price
                    clusters_above.append(LiquidationCluster(
                        price=price,
                        total_value_usd=short_value,
                        is_long=False,
                        distance_percent=abs(distance)
                    ))
                elif price < current_price and long_value > 0:
                    # Long liquidations below current price
                    clusters_below.append(LiquidationCluster(
                        price=price,
                        total_value_usd=long_value,
                        is_long=True,
                        distance_percent=abs(distance)
                    ))
            
            # Sort by distance
            clusters_above.sort(key=lambda x: x.distance_percent)
            clusters_below.sort(key=lambda x: x.distance_percent)
            
            return LiquidationData(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                current_price=current_price,
                clusters_above=clusters_above,
                clusters_below=clusters_below
            )
            
        except Exception as e:
            log_error("parse_liquidation", e)
            return None
    
    async def fetch_all_liquidation_data(self) -> Dict[str, Optional[LiquidationData]]:
        """
        Fetch liquidation data for all monitored symbols.
        
        Returns:
            Dict mapping symbol to LiquidationData (or None if failed)
        """
        if not self._enabled:
            return {}
        
        symbols = ["BTC"] + self.altcoins
        results = {}
        
        for symbol in symbols:
            data = await self._fetch_liquidation_data(symbol)
            if data:
                self._cache[symbol] = data
                results[symbol] = data
                log_data_update("liquidation", f"{symbol}: {len(data.clusters_below)} below, {len(data.clusters_above)} above")
            else:
                results[symbol] = self._cache.get(symbol)
            
            # Delay between requests
            await asyncio.sleep(0.5)
        
        self._last_fetch = datetime.utcnow()
        return results
    
    def get_cached_data(self, symbol: str) -> Optional[LiquidationData]:
        """Get cached liquidation data for a symbol."""
        return self._cache.get(symbol.upper())
    
    async def run(self) -> None:
        """
        Main run loop. Periodically fetches liquidation data.
        """
        if not self._enabled:
            logger.info("Liquidation fetcher disabled (no Coinglass API key)")
            return
        
        self._running = True
        logger.info(f"Starting liquidation fetcher (interval: {Config.LIQUIDATION_POLL_INTERVAL}s)")
        
        while self._running:
            try:
                await self.fetch_all_liquidation_data()
                await asyncio.sleep(Config.LIQUIDATION_POLL_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                log_error("liquidation_run", e)
                await asyncio.sleep(60)
    
    async def stop(self) -> None:
        """Stop the liquidation fetcher."""
        self._running = False
        logger.info("Liquidation fetcher stopped")
    
    def is_enabled(self) -> bool:
        """Check if liquidation fetching is enabled."""
        return self._enabled
    
    def is_running(self) -> bool:
        """Check if the fetcher is running."""
        return self._running
