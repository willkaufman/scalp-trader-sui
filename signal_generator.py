"""
Signal generator - combines all strategy checks to generate trading signals.
"""

from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from config import Config
from data.cache import cache
from data.liquidations import LiquidationFetcher, LiquidationData
from strategy.btc_stabilization import get_btc_status, BTCStatus
from strategy.underperformance import calculate_underperformance, get_current_price, UnderperformanceResult
from strategy.ratio_analysis import analyze_ratio, RatioAnalysis
from utils.cooldown import cooldown_manager
from utils.logger import logger


@dataclass
class FundingCheck:
    """Result of funding rate check."""
    rate: Optional[float]
    is_valid: bool  # Above minimum threshold
    squeeze_potential: bool
    crowded_longs: bool
    message: str


@dataclass 
class LiquidationCheck:
    """Result of liquidation cluster check."""
    has_cluster_below: bool
    has_cluster_above: bool
    cluster_below_warning: str
    cluster_above_note: str


@dataclass
class Signal:
    """A trading signal with all relevant data."""
    altcoin: str
    timestamp: datetime
    current_price: float
    
    # Signal strength
    is_valid: bool
    is_strong: bool
    
    # Entry/exit levels
    entry_low: float
    entry_high: float
    stop_loss: float
    target_1: float
    target_2: float
    
    # Metrics
    btc_status: BTCStatus
    underperformance: UnderperformanceResult
    ratio_analysis: RatioAnalysis
    funding_check: FundingCheck
    liquidation_check: Optional[LiquidationCheck]
    
    # Warnings
    warnings: List[str] = field(default_factory=list)
    
    def get_strength_label(self) -> str:
        """Get signal strength as string."""
        return "STRONG" if self.is_strong else "MODERATE"


class SignalGenerator:
    """
    Generates trading signals based on all strategy conditions.
    """
    
    def __init__(self, liquidation_fetcher: Optional[LiquidationFetcher] = None):
        """
        Initialize signal generator.
        
        Args:
            liquidation_fetcher: Optional liquidation fetcher for additional checks
        """
        self.liquidation_fetcher = liquidation_fetcher
    
    def check_funding_rate(self, altcoin: str) -> FundingCheck:
        """
        Check funding rate conditions.
        
        Args:
            altcoin: The altcoin symbol
            
        Returns:
            FundingCheck result
        """
        symbol = f"{altcoin.upper()}USDT"
        rate = cache.get_funding_rate(symbol)
        
        if rate is None:
            return FundingCheck(
                rate=None,
                is_valid=True,  # Don't block signal if no data
                squeeze_potential=False,
                crowded_longs=False,
                message="Funding rate data unavailable"
            )
        
        # Check if above minimum (not too negative)
        is_valid = rate > Config.FUNDING_RATE_MIN
        
        # Check for squeeze potential (negative but not extreme)
        squeeze = (
            Config.FUNDING_RATE_SQUEEZE_HIGH >= rate >= Config.FUNDING_RATE_SQUEEZE_LOW
        )
        
        # Check for crowded longs
        crowded = rate > Config.FUNDING_RATE_CROWDED
        
        # Generate message
        if not is_valid:
            message = f"⚠️ Funding too negative: {rate:.4f}%"
        elif squeeze:
            message = f"🔥 Squeeze potential: {rate:.4f}%"
        elif crowded:
            message = f"⚠️ Crowded longs: {rate:.4f}%"
        else:
            message = f"Funding: {rate:.4f}%"
        
        return FundingCheck(
            rate=rate,
            is_valid=is_valid,
            squeeze_potential=squeeze,
            crowded_longs=crowded,
            message=message
        )
    
    def check_liquidations(self, altcoin: str) -> Optional[LiquidationCheck]:
        """
        Check liquidation clusters near current price.
        
        Args:
            altcoin: The altcoin symbol
            
        Returns:
            LiquidationCheck or None if data unavailable
        """
        if self.liquidation_fetcher is None or not self.liquidation_fetcher.is_enabled():
            return None
        
        liq_data = self.liquidation_fetcher.get_cached_data(altcoin)
        
        if liq_data is None:
            return None
        
        # Check for clusters within thresholds
        cluster_below = liq_data.get_nearest_below(within_percent=1.5)
        cluster_above = liq_data.get_nearest_above(within_percent=2.0)
        
        below_warning = ""
        above_note = ""
        
        if cluster_below:
            value_m = cluster_below.total_value_usd / 1_000_000
            below_warning = (
                f"⚠️ ${value_m:.1f}M liq cluster {cluster_below.distance_percent:.1f}% below - "
                f"may hunt before bouncing"
            )
        
        if cluster_above:
            value_m = cluster_above.total_value_usd / 1_000_000
            above_note = (
                f"📈 ${value_m:.1f}M short liq {cluster_above.distance_percent:.1f}% above - "
                f"squeeze target"
            )
        
        return LiquidationCheck(
            has_cluster_below=cluster_below is not None,
            has_cluster_above=cluster_above is not None,
            cluster_below_warning=below_warning,
            cluster_above_note=above_note
        )
    
    def calculate_levels(self, current_price: float) -> dict:
        """
        Calculate entry zone, stop loss, and targets.
        
        Args:
            current_price: Current asset price
            
        Returns:
            Dict with entry_low, entry_high, stop_loss, target_1, target_2
        """
        # Entry zone: current price to 0.3% below
        entry_high = current_price
        entry_low = current_price * 0.997
        
        # Stop loss: 0.5% below entry low
        stop_loss = entry_low * 0.995
        
        # Targets
        target_1 = current_price * 1.01  # +1%
        target_2 = current_price * 1.015  # +1.5%
        
        return {
            'entry_low': entry_low,
            'entry_high': entry_high,
            'stop_loss': stop_loss,
            'target_1': target_1,
            'target_2': target_2
        }
    
    def check_signal(self, altcoin: str) -> Optional[Signal]:
        """
        Check all conditions for a trading signal.
        
        Args:
            altcoin: The altcoin symbol to check
            
        Returns:
            Signal if all conditions met, None otherwise
        """
        altcoin = altcoin.upper()
        
        # Check cooldown first
        if not cooldown_manager.can_send_alert(altcoin):
            logger.debug(f"[{altcoin}] Skipping - in cooldown")
            return None
        
        # 1. Check BTC stabilization
        btc_status = get_btc_status()
        
        if not btc_status.has_sufficient_dip:
            logger.debug(f"[{altcoin}] No signal - {btc_status.message}")
            return None
        
        if not btc_status.is_stabilizing:
            logger.debug(f"[{altcoin}] No signal - BTC not stabilizing")
            return None
        
        # 2. Check underperformance
        underperf = calculate_underperformance(altcoin, btc_status.change_1h)
        
        if not underperf.is_underperforming:
            logger.debug(f"[{altcoin}] No signal - {underperf.message}")
            return None
        
        # 3. Check ratio analysis
        ratio = analyze_ratio(altcoin)
        
        if not ratio.is_oversold and not ratio.near_24h_low:
            logger.debug(f"[{altcoin}] No signal - {ratio.message}")
            return None
        
        # 4. Check funding rate
        funding = self.check_funding_rate(altcoin)
        
        if not funding.is_valid:
            logger.debug(f"[{altcoin}] No signal - {funding.message}")
            return None
        
        # 5. Check liquidations (optional)
        liq_check = self.check_liquidations(altcoin)
        
        # All conditions met - generate signal
        current_price = get_current_price(altcoin)
        
        if current_price is None:
            logger.warning(f"[{altcoin}] Cannot get current price")
            return None
        
        levels = self.calculate_levels(current_price)
        
        # Collect warnings
        warnings = []
        
        if funding.crowded_longs:
            warnings.append("Crowded longs - be cautious")
        
        if liq_check:
            if liq_check.cluster_below_warning:
                warnings.append(liq_check.cluster_below_warning)
            if liq_check.cluster_above_note:
                warnings.append(liq_check.cluster_above_note)
        
        # Determine signal strength
        is_strong = (
            underperf.is_strong_signal and
            ratio.is_oversold and
            funding.squeeze_potential
        )
        
        signal = Signal(
            altcoin=altcoin,
            timestamp=datetime.utcnow(),
            current_price=current_price,
            is_valid=True,
            is_strong=is_strong,
            entry_low=levels['entry_low'],
            entry_high=levels['entry_high'],
            stop_loss=levels['stop_loss'],
            target_1=levels['target_1'],
            target_2=levels['target_2'],
            btc_status=btc_status,
            underperformance=underperf,
            ratio_analysis=ratio,
            funding_check=funding,
            liquidation_check=liq_check,
            warnings=warnings
        )
        
        logger.info(
            f"🟢 SIGNAL GENERATED: {altcoin} @ ${current_price:.4f} "
            f"[{signal.get_strength_label()}]"
        )
        
        return signal
    
    def check_all_altcoins(self, altcoins: Optional[List[str]] = None) -> List[Signal]:
        """
        Check signals for all configured altcoins.
        
        Args:
            altcoins: List of altcoins to check (default from config)
            
        Returns:
            List of valid signals
        """
        altcoins = altcoins or Config.get_altcoins()
        signals = []
        
        for altcoin in altcoins:
            try:
                signal = self.check_signal(altcoin)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Error checking {altcoin}: {e}")
        
        return signals
