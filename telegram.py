"""
Telegram alert integration.
Sends trading signals via Telegram bot.
"""

import asyncio
import aiohttp
from typing import Optional

from config import Config
from strategy.signal_generator import Signal
from alerts.formatter import format_telegram_alert, format_error_alert
from utils.logger import logger, log_error


class TelegramAlertSender:
    """
    Sends alerts via Telegram Bot API.
    """
    
    API_BASE = "https://api.telegram.org/bot"
    
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ):
        """
        Initialize Telegram sender.
        
        Args:
            bot_token: Telegram bot token (default from config)
            chat_id: Chat ID to send to (default from config)
        """
        self.bot_token = bot_token or Config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or Config.TELEGRAM_CHAT_ID
        self._enabled = bool(self.bot_token and self.chat_id)
        
        if not self._enabled:
            logger.warning("Telegram alerts disabled - missing bot token or chat ID")
    
    @property
    def api_url(self) -> str:
        """Get the API base URL."""
        return f"{self.API_BASE}{self.bot_token}"
    
    async def send_message(
        self,
        text: str,
        parse_mode: str = "Markdown",
        disable_notification: bool = False
    ) -> bool:
        """
        Send a message via Telegram.
        
        Args:
            text: Message text
            parse_mode: "Markdown" or "HTML"
            disable_notification: If True, send silently
            
        Returns:
            True if sent successfully
        """
        if not self._enabled:
            logger.debug("Telegram disabled, skipping message")
            return False
        
        url = f"{self.api_url}/sendMessage"
        
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.debug("Telegram message sent successfully")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Telegram API error: {response.status} - {error_text}")
                        return False
                        
        except asyncio.TimeoutError:
            logger.error("Telegram request timed out")
            return False
        except Exception as e:
            log_error("telegram_send", e)
            return False
    
    async def send_signal(self, signal: Signal) -> bool:
        """
        Send a trading signal alert.
        
        Args:
            signal: The trading signal
            
        Returns:
            True if sent successfully
        """
        message = format_telegram_alert(signal)
        return await self.send_message(message)
    
    async def send_error(self, error: str, context: str = "") -> bool:
        """
        Send an error alert.
        
        Args:
            error: Error message
            context: Additional context
            
        Returns:
            True if sent successfully
        """
        message = format_error_alert(error, context)
        return await self.send_message(message, disable_notification=True)
    
    async def send_startup_message(self) -> bool:
        """Send a startup notification."""
        message = (
            "🚀 *BTC Lag Scalper Started*\n\n"
            f"Monitoring: {', '.join(Config.get_altcoins())}\n"
            "System is now running."
        )
        return await self.send_message(message, disable_notification=True)
    
    async def send_shutdown_message(self, reason: str = "Manual shutdown") -> bool:
        """Send a shutdown notification."""
        message = (
            "🔴 *BTC Lag Scalper Stopped*\n\n"
            f"Reason: {reason}"
        )
        return await self.send_message(message, disable_notification=True)
    
    async def test_connection(self) -> bool:
        """
        Test the Telegram connection.
        
        Returns:
            True if connection is working
        """
        if not self._enabled:
            return False
        
        url = f"{self.api_url}/getMe"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        bot_name = data.get("result", {}).get("username", "Unknown")
                        logger.info(f"Telegram connected: @{bot_name}")
                        return True
                    else:
                        logger.error(f"Telegram connection failed: {response.status}")
                        return False
                        
        except Exception as e:
            log_error("telegram_test", e)
            return False
    
    def is_enabled(self) -> bool:
        """Check if Telegram alerts are enabled."""
        return self._enabled


# Create default instance
telegram_sender = TelegramAlertSender()
