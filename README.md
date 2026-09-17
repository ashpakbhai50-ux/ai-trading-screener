# 🇮🇳 NSE/BSE AI Swing Screener — FINAL

A Streamlit research dashboard for NSE/BSE swing-stock screening, including a dedicated ₹5–₹50 low-price/penny workflow.

## Features
- NSE/BSE symbol scanning through yfinance
- Market regime using NIFTY 50 and BANK NIFTY
- 20/50/200 DMA, EMA, VWAP, RSI, MACD, ADX, ATR and RVOL
- 20-day breakout / near-breakout detection
- Weekly trend confirmation
- Liquidity filter and manipulation-risk score
- Three-stage workflow: Early Alert → Confirmation → Entry
- Entry, SL, T1, T2, T3 and 2R/3R/4R framework
- Position sizing from capital and ₹ risk/trade
- ₹ risk and target P&L estimates
- Separate penny/low-price leaderboard
- Interactive candlestick chart with levels
- CSV export and refresh control
- Mobile-friendly Streamlit dashboard

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Data note
The default feed is Yahoo Finance through yfinance. It is a research feed and should not be represented as a guaranteed real-time/licensed NSE/BSE feed. For production live alerts, connect a licensed market-data provider and add its credentials through Streamlit secrets.

## Risk note
Scores and signals are rule-based research outputs, not guaranteed predictions or investment advice. Low-priced stocks can have materially higher liquidity and volatility risks.
