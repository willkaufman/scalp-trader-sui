"""
Discord alert integration.
Sends trading signals via Discord webhook.
"""

import asyncio
import aiohttp
from typing import Optional, Dict, Any

from config import Config
from strategy.signal_generator import Signal
from alerts.formatter import format_discord_alert
from utils.logger import logger, log_error


class DiscordAlertSender:
    """
    Sends alerts via Discord webhook.
    """
    
    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Discord sender.
        
        Args:
            webhook_url: Discord webhook URL (default from config)
        """
        self.webhook_url = webhook_url or Config.DISCORD_WEBHOOK_URL
        self._enabled = bool(self.webhook_url)
        
        if not self._enabled:
            logger.info("Discord alerts disabled - no webhook URL configured")
    
    async def send_message(
        self,
        content: Optional[str] = None,
        embed: Optional[Dict[str, Any]] = None,
        username: str = "BTC Lag Scalper"
    ) -> bool:
        """
        Send a message via Discord webhook.
        
        Args:
            content: Plain text content
            embed: Embed object
            username: Bot username to display
            
        Returns:
            True if sent successfully
        """
        if not self._enabled:
            logger.debug("Discord disabled, skipping message")
            return False
        
        payload = {
            "username": username
        }
        
        if content:
            payload["content"] = content
        
        if embed:
            payload["embeds"] = [embed]
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    # Discord returns 204 on success
                    if response.status in (200, 204):
                        logger.debug("Discord message sent successfully")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Discord webhook error: {response.status} - {error_text}")
                        return False
                        
        except asyncio.TimeoutError:
            logger.error("Discord request timed out")
            return False
        except Exception as e:
            log_error("discord_send", e)
            return False
    
    async def send_signal(self, signal: Signal) -> bool:
        """
        Send a trading signal alert.
        
        Args:
            signal: The trading signal
            
        Returns:
            True if sent successfully
        """
        embed = format_discord_alert(signal)
        return await self.send_message(embed=embed)
    
    async def send_error(self, error: str, context: str = "") -> bool:
        """
        Send an error alert.
        
        Args:
            error: Error message
            context: Additional context
            
        Returns:
            True if sent successfully
        """
        embed = {
            "title": "🚨 BTC Lag Scalper Error",
            "description": error,
            "color": 0xFF0000,  # Red
            "fields": []
        }
        
        if context:
            embed["fields"].append({
                "name": "Context",
                "value": context,
                "inline": False
            })
        
        return await self.send_message(embed=embed)
    
    async def send_startup_message(self) -> bool:
        """Send a startup notification."""
        embed = {
            "title": "🚀 BTC Lag Scalper Started",
            "description": f"Monitoring: {', '.join(Config.get_altcoins())}",
            "color": 0x00FF00,  # Green
            "footer": {"text": "System is now running"}
        }
        return await self.send_message(embed=embed)
    
    async def send_shutdown_message(self, reason: str = "Manual shutdown") -> bool:
        """Send a shutdown notification."""
        embed = {
            "title": "🔴 BTC Lag Scalper Stopped",
            "description": f"Reason: {reason}",
            "color": 0xFF6600  # Orange
        }
        return await self.send_message(embed=embed)
    
    async def test_connection(self) -> bool:
        """
        Test the Discord connection by sending a test message.
        
        Returns:
            True if connection is working
        """
        if not self._enabled:
            return False
        
        # Send a simple test message
        result = await self.send_message(content="🔌 Connection test - BTC Lag Scalper")
        
        if result:
            logger.info("Discord webhook connected successfully")
        
        return result
    
    def is_enabled(self) -> bool:
        """Check if Discord alerts are enabled."""
        return self._enabled


# Create default instance
discord_sender = DiscordAlertSender()
