"""
Alert cooldown management.
Prevents spam by tracking last alert time per altcoin.
"""

import time
from typing import Dict, Optional
from config import Config
from utils.logger import logger


class CooldownManager:
    """
    Manages alert cooldowns per altcoin.
    Prevents sending multiple alerts for the same coin within the cooldown period.
    """
    
    def __init__(self, cooldown_seconds: Optional[int] = None):
        """
        Initialize cooldown manager.
        
        Args:
            cooldown_seconds: Cooldown period in seconds (default from config)
        """
        self.cooldown_seconds = cooldown_seconds or Config.ALERT_COOLDOWN_SECONDS
        self._last_alerts: Dict[str, float] = {}
    
    def can_send_alert(self, altcoin: str) -> bool:
        """
        Check if an alert can be sent for the given altcoin.
        
        Args:
            altcoin: The altcoin symbol (e.g., "SUI")
            
        Returns:
            True if alert can be sent, False if still in cooldown
        """
        altcoin = altcoin.upper()
        current_time = time.time()
        
        if altcoin not in self._last_alerts:
            return True
        
        last_alert_time = self._last_alerts[altcoin]
        elapsed = current_time - last_alert_time
        
        if elapsed >= self.cooldown_seconds:
            return True
        
        remaining = self.cooldown_seconds - elapsed
        logger.debug(
            f"Cooldown active for {altcoin}: {remaining:.0f}s remaining"
        )
        return False
    
    def record_alert(self, altcoin: str) -> None:
        """
        Record that an alert was sent for an altcoin.
        
        Args:
            altcoin: The altcoin symbol
        """
        altcoin = altcoin.upper()
        self._last_alerts[altcoin] = time.time()
        logger.debug(f"Recorded alert for {altcoin}, cooldown started")
    
    def get_remaining_cooldown(self, altcoin: str) -> float:
        """
        Get remaining cooldown time for an altcoin.
        
        Args:
            altcoin: The altcoin symbol
            
        Returns:
            Remaining seconds, or 0 if no cooldown active
        """
        altcoin = altcoin.upper()
        
        if altcoin not in self._last_alerts:
            return 0.0
        
        elapsed = time.time() - self._last_alerts[altcoin]
        remaining = max(0, self.cooldown_seconds - elapsed)
        return remaining
    
    def clear_cooldown(self, altcoin: str) -> None:
        """
        Clear cooldown for a specific altcoin.
        
        Args:
            altcoin: The altcoin symbol
        """
        altcoin = altcoin.upper()
        if altcoin in self._last_alerts:
            del self._last_alerts[altcoin]
            logger.debug(f"Cleared cooldown for {altcoin}")
    
    def clear_all(self) -> None:
        """Clear all cooldowns."""
        self._last_alerts.clear()
        logger.debug("Cleared all cooldowns")
    
    def get_status(self) -> Dict[str, float]:
        """
        Get current cooldown status for all altcoins.
        
        Returns:
            Dict mapping altcoin to remaining cooldown seconds
        """
        status = {}
        for altcoin in self._last_alerts:
            remaining = self.get_remaining_cooldown(altcoin)
            if remaining > 0:
                status[altcoin] = remaining
        return status


# Global cooldown manager instance
cooldown_manager = CooldownManager()
