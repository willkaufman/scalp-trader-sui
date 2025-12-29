"""
BTC Lag Scalper - Main Entry Point

A trading alert system that monitors BTC and altcoins for mean-reversion opportunities.
This system does NOT execute trades - it only sends alerts when conditions are met.
"""

import asyncio
import signal
import sys
from datetime import datetime
from typing import Optional

from config import Config
from data.price_feed import BinancePriceFeed, initialize_cache
from data.funding_rates import FundingRateFetcher
from data.liquidations import LiquidationFetcher
from data.cache import cache, Candle
from strategy.signal_generator import SignalGenerator, Signal
from alerts.telegram import telegram_sender
from alerts.discord import discord_sender
from utils.cooldown import cooldown_manager
from utils.logger import logger, log_alert_sent


class BTCLagScalper:
    """
    Main application class for the BTC Lag Scalper alert system.
    """
    
    def __init__(self):
        self.altcoins = Config.get_altcoins()
        
        # Initialize components
        self.price_feed = BinancePriceFeed(self.altcoins)
        self.funding_fetcher = FundingRateFetcher(self.altcoins)
        self.liquidation_fetcher = LiquidationFetcher(self.altcoins)
        self.signal_generator = SignalGenerator(self.liquidation_fetcher)
        
        # State
        self._running = False
        self._start_time: Optional[datetime] = None
        self._signals_sent = 0
        self._errors_count = 0
        
        # Register candle callback
        self.price_feed.add_candle_callback(self._on_candle_close)
    
    def _on_candle_close(self, symbol: str, interval: str, candle: Candle) -> None:
        """
        Callback when a candle closes.
        Triggers signal checking on 1-minute candle closes.
        """
        if interval != "1m":
            return
        
        # Only check signals for altcoins
        for altcoin in self.altcoins:
            if symbol == f"{altcoin}USDT":
                # Schedule signal check (non-blocking)
                asyncio.create_task(self._check_and_send_signal(altcoin))
    
    async def _check_and_send_signal(self, altcoin: str) -> None:
        """
        Check for signal and send alerts if conditions are met.
        """
        try:
            signal = self.signal_generator.check_signal(altcoin)
            
            if signal:
                await self._send_alert(signal)
                
        except Exception as e:
            logger.error(f"Error checking signal for {altcoin}: {e}")
            self._errors_count += 1
    
    async def _send_alert(self, signal: Signal) -> None:
        """
        Send alert via all configured channels.
        """
        # Send via Telegram (primary)
        telegram_success = await telegram_sender.send_signal(signal)
        
        # Send via Discord (secondary)
        discord_success = await discord_sender.send_signal(signal)
        
        if telegram_success or discord_success:
            log_alert_sent(signal.altcoin, signal.current_price)
            cooldown_manager.record_alert(signal.altcoin)
            self._signals_sent += 1
        else:
            logger.error(f"Failed to send alert for {signal.altcoin}")
            self._errors_count += 1
    
    async def _run_health_check_server(self) -> None:
        """
        Run a simple HTTP health check server.
        """
        if not Config.ENABLE_HEALTH_CHECK:
            return
        
        from aiohttp import web
        
        async def health_handler(request):
            status = {
                "status": "running",
                "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds() if self._start_time else 0,
                "signals_sent": self._signals_sent,
                "errors": self._errors_count,
                "altcoins": self.altcoins,
                "cache": cache.get_status()
            }
            return web.json_response(status)
        
        app = web.Application()
        app.router.add_get("/", health_handler)
        app.router.add_get("/health", health_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, "0.0.0.0", Config.HEALTH_CHECK_PORT)
        await site.start()
        
        logger.info(f"Health check server running on port {Config.HEALTH_CHECK_PORT}")
    
    async def start(self) -> None:
        """
        Start the BTC Lag Scalper system.
        """
        logger.info("=" * 50)
        logger.info("Starting BTC Lag Scalper")
        logger.info("=" * 50)
        
        # Validate configuration
        if not Config.validate():
            logger.error("Configuration validation failed")
            sys.exit(1)
        
        Config.print_config()
        
        self._running = True
        self._start_time = datetime.utcnow()
        
        # Test alert connections
        logger.info("Testing alert connections...")
        
        if telegram_sender.is_enabled():
            await telegram_sender.test_connection()
        
        if discord_sender.is_enabled():
            await discord_sender.test_connection()
        
        # Initialize cache with historical data
        await initialize_cache(self.altcoins)
        
        # Send startup notification
        await telegram_sender.send_startup_message()
        await discord_sender.send_startup_message()
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self.price_feed.run()),
            asyncio.create_task(self.funding_fetcher.run()),
        ]
        
        # Add liquidation fetcher if enabled
        if self.liquidation_fetcher.is_enabled():
            tasks.append(asyncio.create_task(self.liquidation_fetcher.run()))
        
        # Add health check server
        if Config.ENABLE_HEALTH_CHECK:
            tasks.append(asyncio.create_task(self._run_health_check_server()))
        
        logger.info("System running. Waiting for signals...")
        
        try:
            # Wait for all tasks
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await telegram_sender.send_error(str(e), "Main loop error")
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """
        Stop the BTC Lag Scalper system.
        """
        logger.info("Stopping BTC Lag Scalper...")
        self._running = False
        
        # Stop components
        await self.price_feed.stop()
        await self.funding_fetcher.stop()
        await self.liquidation_fetcher.stop()
        
        # Send shutdown notification
        await telegram_sender.send_shutdown_message()
        await discord_sender.send_shutdown_message()
        
        # Log summary
        uptime = (datetime.utcnow() - self._start_time).total_seconds() if self._start_time else 0
        logger.info(f"Shutdown complete. Uptime: {uptime:.0f}s, Signals: {self._signals_sent}, Errors: {self._errors_count}")


async def main():
    """Main entry point."""
    scalper = BTCLagScalper()
    
    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    
    def shutdown_handler(sig):
        logger.info(f"Received signal {sig.name}")
        asyncio.create_task(scalper.stop())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: shutdown_handler(s))
    
    await scalper.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
