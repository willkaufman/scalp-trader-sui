"""
Configuration management for BTC Lag Scalper.
All settings are loaded from environment variables with sensible defaults.
"""

import os
from typing import List


class Config:
    """Central configuration class."""
    
    # Telegram settings
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # Discord settings
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")
    
    # API Keys
    COINGLASS_API_KEY: str = os.getenv("COINGLASS_API_KEY", "")
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Altcoins to monitor (comma-separated)
    ALTCOINS_STR: str = os.getenv("ALTCOINS", "SUI")
    
    @classmethod
    def get_altcoins(cls) -> List[str]:
        """Parse altcoins from environment variable."""
        return [coin.strip().upper() for coin in cls.ALTCOINS_STR.split(",") if coin.strip()]
    
    # Strategy thresholds (configurable via env vars)
    
    # BTC must have dropped at least this much in 1h to trigger
    BTC_MIN_DROP_1H: float = float(os.getenv("BTC_MIN_DROP_1H", "-0.5"))
    
    # Minimum underperformance spread to trigger alert
    UNDERPERFORMANCE_THRESHOLD: float = float(os.getenv("UNDERPERFORMANCE_THRESHOLD", "-1.0"))
    
    # Strong signal threshold
    UNDERPERFORMANCE_STRONG: float = float(os.getenv("UNDERPERFORMANCE_STRONG", "-2.0"))
    
    # RSI threshold for oversold on ALT/BTC ratio
    RATIO_RSI_OVERSOLD: float = float(os.getenv("RATIO_RSI_OVERSOLD", "35"))
    
    # Funding rate filters
    FUNDING_RATE_MIN: float = float(os.getenv("FUNDING_RATE_MIN", "-0.08"))
    FUNDING_RATE_SQUEEZE_LOW: float = float(os.getenv("FUNDING_RATE_SQUEEZE_LOW", "-0.08"))
    FUNDING_RATE_SQUEEZE_HIGH: float = float(os.getenv("FUNDING_RATE_SQUEEZE_HIGH", "-0.03"))
    FUNDING_RATE_CROWDED: float = float(os.getenv("FUNDING_RATE_CROWDED", "0.05"))
    
    # Alert cooldown in seconds (30 minutes default)
    ALERT_COOLDOWN_SECONDS: int = int(os.getenv("ALERT_COOLDOWN_SECONDS", "1800"))
    
    # Data settings
    CANDLES_1M_BUFFER: int = 100  # Number of 1-minute candles to keep
    CANDLES_15M_BUFFER: int = 50  # Number of 15-minute candles to keep
    
    # RSI and SMA periods
    RSI_PERIOD: int = 14
    SMA_PERIOD: int = 20
    
    # Funding rate poll interval (seconds)
    FUNDING_POLL_INTERVAL: int = int(os.getenv("FUNDING_POLL_INTERVAL", "60"))
    
    # Liquidation poll interval (seconds)
    LIQUIDATION_POLL_INTERVAL: int = int(os.getenv("LIQUIDATION_POLL_INTERVAL", "300"))
    
    # Health check port (optional)
    HEALTH_CHECK_PORT: int = int(os.getenv("PORT", os.getenv("HEALTH_CHECK_PORT", "8080")))
    ENABLE_HEALTH_CHECK: bool = os.getenv("ENABLE_HEALTH_CHECK", "true").lower() == "true"
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration."""
        errors = []
        
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is required")
        if not cls.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID is required")
        
        if errors:
            for error in errors:
                print(f"Config Error: {error}")
            return False
        
        return True
    
    @classmethod
    def print_config(cls) -> None:
        """Print current configuration (hiding sensitive values)."""
        print("=" * 50)
        print("BTC Lag Scalper Configuration")
        print("=" * 50)
        print(f"Altcoins: {cls.get_altcoins()}")
        print(f"Log Level: {cls.LOG_LEVEL}")
        print(f"BTC Min Drop (1h): {cls.BTC_MIN_DROP_1H}%")
        print(f"Underperformance Threshold: {cls.UNDERPERFORMANCE_THRESHOLD}%")
        print(f"RSI Oversold: {cls.RATIO_RSI_OVERSOLD}")
        print(f"Alert Cooldown: {cls.ALERT_COOLDOWN_SECONDS}s")
        print(f"Telegram: {'Configured' if cls.TELEGRAM_BOT_TOKEN else 'Not configured'}")
        print(f"Discord: {'Configured' if cls.DISCORD_WEBHOOK_URL else 'Not configured'}")
        print(f"Coinglass: {'Configured' if cls.COINGLASS_API_KEY else 'Using Binance fallback'}")
        print("=" * 50)
