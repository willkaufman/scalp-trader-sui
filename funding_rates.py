"""
Funding rate data fetching from Coinglass and Binance.
Uses Coinglass as primary source with Binance as fallback.
"""

import asyncio
import aiohttp
from typing import Dict, Optional, List
from datetime import datetime

from config import Config
from data.cache import cache
from utils.logger import logger, log_error, log_data_update


class FundingRateFetcher:
    """
    Fetches funding rates from Coinglass (primary) or Binance (fallback).
    Runs as a background task, polling at configured intervals.
    """
    
    COINGLASS_API_URL = "https://open-api.coinglass.com/public/v2/funding"
    BINANCE_FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
    BINANCE_PREMIUM_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"
    
    def __init__(self, altcoins: Optional[List[str]] = None):
        """
        Initialize the funding rate fetcher.
        
        Args:
            altcoins: List of altcoin symbols to monitor
        """
        self.altcoins = [coin.upper() for coin in (altcoins or Config.get_altcoins())]
        self._running = False
        self._last_fetch: Optional[datetime] = None
        self._use_coinglass = bool(Config.COINGLASS_API_KEY)
    
    async def _fetch_from_coinglass(self, symbol: str) -> Optional[float]:
        """
        Fetch funding rate from Coinglass API.
        
        Args:
            symbol: The trading symbol (e.g., "BTC", "SUI")
            
        Returns:
            Funding rate as percentage or None if failed
        """
        if not Config.COINGLASS_API_KEY:
            return None
        
        headers = {
            "accept": "application/json",
            "coinglassSecret": Config.COINGLASS_API_KEY
        }
        
        params = {
            "symbol": symbol.upper()
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.COINGLASS_API_URL,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Coinglass API error: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    if data.get("success") and data.get("data"):
                        # Find Binance funding rate (preferred exchange)
                        for exchange_data in data["data"]:
                            if exchange_data.get("exchangeName") == "Binance":
                                rate = exchange_data.get("fundingRate")
                                if rate is not None:
                                    return float(rate)
                        
                        # Fall back to first available
                        if data["data"]:
                            rate = data["data"][0].get("fundingRate")
                            if rate is not None:
                                return float(rate)
                    
                    return None
                    
        except Exception as e:
            log_error("coinglass_fetch", e)
            return None
    
    async def _fetch_from_binance(self, symbol: str) -> Optional[float]:
        """
        Fetch funding rate from Binance Futures API.
        
        Args:
            symbol: The trading symbol (e.g., "BTC", "SUI")
            
        Returns:
            Funding rate as percentage or None if failed
        """
        # Binance uses full pair names
        pair = f"{symbol.upper()}USDT"
        
        try:
            async with aiohttp.ClientSession() as session:
                # Use premium index endpoint for current funding rate
                async with session.get(
                    self.BINANCE_PREMIUM_URL,
                    params={"symbol": pair},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Binance API error: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    if "lastFundingRate" in data:
                        # Binance returns as decimal (0.0001 = 0.01%)
                        rate = float(data["lastFundingRate"]) * 100
                        return rate
                    
                    return None
                    
        except Exception as e:
            log_error("binance_funding_fetch", e)
            return None
    
    async def fetch_funding_rate(self, symbol: str) -> Optional[float]:
        """
        Fetch funding rate, trying Coinglass first then Binance.
        
        Args:
            symbol: The base symbol (e.g., "BTC", "SUI")
            
        Returns:
            Funding rate as percentage or None if failed
        """
        # Try Coinglass first if API key is configured
        if self._use_coinglass:
            rate = await self._fetch_from_coinglass(symbol)
            if rate is not None:
                return rate
            logger.debug(f"Coinglass failed for {symbol}, falling back to Binance")
        
        # Fall back to Binance
        return await self._fetch_from_binance(symbol)
    
    async def fetch_all_funding_rates(self) -> Dict[str, Optional[float]]:
        """
        Fetch funding rates for all monitored symbols.
        
        Returns:
            Dict mapping symbol to funding rate (or None if failed)
        """
        symbols = ["BTC"] + self.altcoins
        rates = {}
        
        for symbol in symbols:
            rate = await self.fetch_funding_rate(symbol)
            rates[symbol] = rate
            
            # Update cache
            if rate is not None:
                cache.set_funding_rate(f"{symbol}USDT", rate)
                log_data_update("funding", f"{symbol}: {rate:.4f}%")
            
            # Small delay between requests
            await asyncio.sleep(0.1)
        
        self._last_fetch = datetime.utcnow()
        return rates
    
    async def run(self) -> None:
        """
        Main run loop. Periodically fetches funding rates.
        """
        self._running = True
        logger.info(
            f"Starting funding rate fetcher (interval: {Config.FUNDING_POLL_INTERVAL}s, "
            f"source: {'Coinglass' if self._use_coinglass else 'Binance'})"
        )
        
        while self._running:
            try:
                await self.fetch_all_funding_rates()
                await asyncio.sleep(Config.FUNDING_POLL_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                log_error("funding_rate_run", e)
                await asyncio.sleep(30)  # Wait before retrying on error
    
    async def stop(self) -> None:
        """Stop the funding rate fetcher."""
        self._running = False
        logger.info("Funding rate fetcher stopped")
    
    def is_running(self) -> bool:
        """Check if the fetcher is running."""
        return self._running
    
    def get_last_fetch_time(self) -> Optional[datetime]:
        """Get the timestamp of the last successful fetch."""
        return self._last_fetch
