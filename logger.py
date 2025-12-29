"""
Logging configuration for BTC Lag Scalper.
"""

import logging
import sys
from datetime import datetime
from config import Config


def setup_logger(name: str = "btc_lag_scalper") -> logging.Logger:
    """
    Set up and return a configured logger.
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Set log level from config
    level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger


# Create default logger instance
logger = setup_logger()


def log_signal_check(altcoin: str, passed: bool, reason: str) -> None:
    """Log signal check results."""
    status = "✓ PASSED" if passed else "✗ FAILED"
    logger.debug(f"Signal Check [{altcoin}] {status}: {reason}")


def log_alert_sent(altcoin: str, price: float) -> None:
    """Log when an alert is sent."""
    logger.info(f"🔔 ALERT SENT: {altcoin} at ${price:.4f}")


def log_websocket_event(event: str, details: str = "") -> None:
    """Log WebSocket events."""
    logger.info(f"WebSocket {event}: {details}")


def log_error(context: str, error: Exception) -> None:
    """Log errors with context."""
    logger.error(f"Error in {context}: {str(error)}", exc_info=True)


def log_data_update(source: str, details: str) -> None:
    """Log data updates (at DEBUG level to avoid spam)."""
    logger.debug(f"Data Update [{source}]: {details}")
