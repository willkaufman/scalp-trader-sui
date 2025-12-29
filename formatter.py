"""
Alert message formatting.
Creates formatted messages for Telegram and Discord.
"""

from datetime import datetime
from typing import Optional

from strategy.signal_generator import Signal


def format_price(price: float, decimals: int = 4) -> str:
    """Format price with appropriate decimal places."""
    if price >= 1000:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:.4f}"
    else:
        return f"${price:.6f}"


def format_percentage(value: float) -> str:
    """Format percentage with sign."""
    return f"{value:+.2f}%"


def format_telegram_alert(signal: Signal) -> str:
    """
    Format a signal for Telegram (Markdown format).
    
    Args:
        signal: The trading signal
        
    Returns:
        Formatted Markdown string
    """
    # Emoji based on strength
    strength_emoji = "🔥" if signal.is_strong else "🟢"
    
    lines = [
        f"{strength_emoji} *LONG SIGNAL: {signal.altcoin}*",
        "",
        f"*Entry Zone:* {format_price(signal.entry_low)} - {format_price(signal.entry_high)}",
        f"*Current Price:* {format_price(signal.current_price)}",
        "",
        f"*Stop Loss:* {format_price(signal.stop_loss)} (-0.5%)",
        f"*Target 1:* {format_price(signal.target_1)} (+1.0%)",
        f"*Target 2:* {format_price(signal.target_2)} (+1.5%)",
        "",
        f"📊 *Signal Strength:* {signal.get_strength_label()}",
        "",
        "*Metrics:*",
        f"• BTC 1H Change: {format_percentage(signal.btc_status.change_1h)}",
        f"• {signal.altcoin} 1H Change: {format_percentage(signal.underperformance.alt_change_1h)}",
        f"• Underperformance: {format_percentage(signal.underperformance.spread)}",
    ]
    
    # Add RSI if available
    if signal.ratio_analysis.ratio_rsi is not None:
        lines.append(f"• {signal.altcoin}/BTC RSI(14): {signal.ratio_analysis.ratio_rsi:.1f}")
    
    # Add funding rate if available
    if signal.funding_check.rate is not None:
        lines.append(f"• Funding Rate: {signal.funding_check.rate:.4f}%")
    
    # Add warnings
    if signal.warnings:
        lines.append("")
        lines.append("⚠️ *Warnings:*")
        for warning in signal.warnings:
            lines.append(f"• {warning}")
    
    # Add BTC status
    lines.append("")
    lines.append(f"📈 *BTC Status:* {signal.btc_status.message}")
    
    # Timestamp
    lines.append("")
    lines.append(f"⏰ {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    return "\n".join(lines)


def format_discord_alert(signal: Signal) -> dict:
    """
    Format a signal for Discord (embed format).
    
    Args:
        signal: The trading signal
        
    Returns:
        Discord embed object as dict
    """
    # Color based on strength (green variations)
    color = 0x00FF00 if signal.is_strong else 0x32CD32
    
    # Build description
    description_lines = [
        f"**Entry Zone:** {format_price(signal.entry_low)} - {format_price(signal.entry_high)}",
        f"**Current Price:** {format_price(signal.current_price)}",
        "",
        f"**Stop Loss:** {format_price(signal.stop_loss)} (-0.5%)",
        f"**Target 1:** {format_price(signal.target_1)} (+1.0%)",
        f"**Target 2:** {format_price(signal.target_2)} (+1.5%)",
    ]
    
    # Metrics field
    metrics_lines = [
        f"BTC 1H: {format_percentage(signal.btc_status.change_1h)}",
        f"{signal.altcoin} 1H: {format_percentage(signal.underperformance.alt_change_1h)}",
        f"Underperformance: {format_percentage(signal.underperformance.spread)}",
    ]
    
    if signal.ratio_analysis.ratio_rsi is not None:
        metrics_lines.append(f"{signal.altcoin}/BTC RSI: {signal.ratio_analysis.ratio_rsi:.1f}")
    
    if signal.funding_check.rate is not None:
        metrics_lines.append(f"Funding: {signal.funding_check.rate:.4f}%")
    
    # Build embed
    embed = {
        "title": f"{'🔥' if signal.is_strong else '🟢'} LONG SIGNAL: {signal.altcoin}",
        "description": "\n".join(description_lines),
        "color": color,
        "fields": [
            {
                "name": f"📊 Signal Strength",
                "value": signal.get_strength_label(),
                "inline": True
            },
            {
                "name": "📈 Metrics",
                "value": "\n".join(metrics_lines),
                "inline": False
            }
        ],
        "footer": {
            "text": f"BTC: {signal.btc_status.message}"
        },
        "timestamp": signal.timestamp.isoformat()
    }
    
    # Add warnings field if any
    if signal.warnings:
        embed["fields"].append({
            "name": "⚠️ Warnings",
            "value": "\n".join(signal.warnings),
            "inline": False
        })
    
    return embed


def format_error_alert(error: str, context: str = "") -> str:
    """
    Format an error message for alerting.
    
    Args:
        error: The error message
        context: Additional context
        
    Returns:
        Formatted error string
    """
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    
    lines = [
        "🚨 *BTC Lag Scalper Error*",
        "",
        f"*Error:* {error}",
    ]
    
    if context:
        lines.append(f"*Context:* {context}")
    
    lines.append("")
    lines.append(f"⏰ {timestamp} UTC")
    
    return "\n".join(lines)


def format_daily_summary(
    alerts_sent: int,
    uptime_hours: float,
    errors_count: int
) -> str:
    """
    Format daily summary message.
    
    Args:
        alerts_sent: Number of alerts sent today
        uptime_hours: System uptime in hours
        errors_count: Number of errors encountered
        
    Returns:
        Formatted summary string
    """
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    
    lines = [
        "📊 *BTC Lag Scalper Daily Summary*",
        "",
        f"• Alerts Sent: {alerts_sent}",
        f"• Uptime: {uptime_hours:.1f} hours",
        f"• Errors: {errors_count}",
        "",
        f"⏰ {timestamp} UTC"
    ]
    
    return "\n".join(lines)
