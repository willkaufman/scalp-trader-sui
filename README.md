# BTC Lag Scalper

A cloud-based trading alert system that monitors BTC and altcoins in real-time, detecting mean-reversion opportunities when altcoins dump significantly harder than BTC.

**⚠️ This is NOT a trading bot - it only sends alerts. You manually decide whether to trade.**

## 🎯 Strategy Overview

The system identifies opportunities when:
1. **BTC has dipped** (at least -0.5% in the last hour)
2. **BTC is stabilizing** (not making new lows)
3. **Altcoin has underperformed** (dumped at least 1% more than BTC)
4. **ALT/BTC ratio is oversold** (RSI < 35 or near 24h low)
5. **Funding rate is acceptable** (not too negative)

When all conditions align, you receive an alert with entry zone, stop loss, and targets.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Telegram Bot (for alerts)
- Optional: Discord webhook, Coinglass API key

### 1. Clone/Download the Code

```bash
git clone <your-repo>
cd btc-lag-scalper
```

### 2. Set Up Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Save the bot token (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
4. Message your new bot (just say "hi")
5. Get your chat ID:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
   Look for `"chat":{"id":123456789}` in the response

### 3. Configure Environment Variables

Copy the example file:
```bash
cp .env.example .env
```

Edit `.env` with your values:
```env
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
ALTCOINS=SUI
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run Locally (for testing)

```bash
python main.py
```

## ☁️ Deploy to Railway

### 1. Create Railway Account
- Go to [railway.app](https://railway.app)
- Sign up with GitHub

### 2. Create New Project
- Click "New Project"
- Select "Deploy from GitHub repo"
- Connect your repository

### 3. Add Environment Variables
In Railway dashboard:
- Go to your project → Variables
- Add each variable from your `.env` file

### 4. Deploy
Railway will automatically deploy when you push to your repo.

### 5. Verify
- Check the "Deployments" tab for logs
- You should receive a startup message on Telegram

## ⚙️ Configuration

### Required Variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token |
| `TELEGRAM_CHAT_ID` | Chat ID to send alerts to |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_WEBHOOK_URL` | - | Discord webhook for alerts |
| `COINGLASS_API_KEY` | - | Coinglass API for funding/liquidation data |
| `ALTCOINS` | `SUI` | Comma-separated list of altcoins |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ALERT_COOLDOWN_SECONDS` | `1800` | Cooldown between alerts (30 min) |

### Strategy Thresholds

| Variable | Default | Description |
|----------|---------|-------------|
| `BTC_MIN_DROP_1H` | `-0.5` | Min BTC 1h drop to trigger |
| `UNDERPERFORMANCE_THRESHOLD` | `-1.0` | Min spread to trigger |
| `UNDERPERFORMANCE_STRONG` | `-2.0` | Strong signal threshold |
| `RATIO_RSI_OVERSOLD` | `35` | RSI threshold for oversold |

## 📱 Adding New Altcoins

Simply update the `ALTCOINS` environment variable:

```env
ALTCOINS=SUI,SOL,AVAX,MATIC
```

Restart the service for changes to take effect.

## 🔔 Alert Format

```
🟢 LONG SIGNAL: SUI

Entry Zone: $2.1450 - $2.1515
Current Price: $2.1515

Stop Loss: $2.1343 (-0.5%)
Target 1: $2.1730 (+1.0%)
Target 2: $2.1838 (+1.5%)

📊 Signal Strength: STRONG

Metrics:
• BTC 1H Change: -1.52%
• SUI 1H Change: -3.84%
• Underperformance: -2.32%
• SUI/BTC RSI(14): 28.5
• Funding Rate: -0.0234%

⚠️ Warnings:
• $2.1M liq cluster 1.2% below - may hunt before bouncing

📈 BTC Status: Stabilizing at $94,523 after -1.52% dip

⏰ 2024-01-15 14:32:45 UTC
```

## 🔧 Troubleshooting

### No Alerts Receiving

1. **Check Telegram connection**: Look for "Telegram connected: @YourBotName" in logs
2. **Verify chat ID**: Make sure you messaged the bot before getting the ID
3. **Check logs**: Look for "Signal Check" entries to see why signals aren't triggering

### WebSocket Disconnections

Normal behavior - the system automatically reconnects. Binance disconnects every 24 hours.

### "Insufficient data" Messages

Normal during startup. Wait 1-2 minutes for historical data to load.

### Rate Limiting

If you see rate limit errors:
- Coinglass: May require paid plan for some endpoints
- Binance: Should not occur with normal usage

### Common Log Messages

| Message | Meaning |
|---------|---------|
| `Cache initialization complete` | Historical data loaded, ready |
| `Signal Check PASSED` | A condition passed |
| `Signal Check FAILED` | A condition not met (normal) |
| `SIGNAL GENERATED` | All conditions met! |
| `Cooldown active` | Alert already sent recently |

## 📁 Project Structure

```
btc-lag-scalper/
├── main.py                 # Entry point
├── config.py               # Configuration management
├── requirements.txt        # Dependencies
├── Procfile               # Railway deployment
│
├── data/
│   ├── price_feed.py      # WebSocket price data
│   ├── funding_rates.py   # Funding rate fetcher
│   ├── liquidations.py    # Liquidation data
│   └── cache.py           # In-memory data cache
│
├── strategy/
│   ├── btc_stabilization.py   # BTC dip detection
│   ├── underperformance.py    # ALT vs BTC comparison
│   ├── ratio_analysis.py      # ALT/BTC RSI calculation
│   └── signal_generator.py    # Main signal logic
│
├── alerts/
│   ├── telegram.py        # Telegram integration
│   ├── discord.py         # Discord integration
│   └── formatter.py       # Alert message formatting
│
└── utils/
    ├── indicators.py      # RSI, SMA calculations
    ├── logger.py          # Logging setup
    └── cooldown.py        # Alert rate limiting
```

## 🛡️ Disclaimer

This software is for educational purposes only. Trading cryptocurrency involves substantial risk of loss. Never trade with money you cannot afford to lose. The authors are not responsible for any financial losses incurred from using this software.

## 📄 License

MIT License - feel free to modify and use as you wish.
