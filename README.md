# 🇮🇳 NSE/BSE Under ₹100 Sector Swing Scanner

A Streamlit research dashboard for finding **NSE/BSE stocks trading at or below ₹100**, grouped across broad sectors, with one qualifying candidate per sector.

## What this version does

- Scans a broad multi-sector NSE universe.
- Hard price filter: **₹100 maximum**.
- Technical trend: 20/50/200 DMA, VWAP, RSI, MACD, ADX.
- Volume confirmation: RVOL and 20-day average traded value.
- Volatility control: ATR%.
- Breakout / near-breakout structure.
- Weekly trend confirmation.
- NIFTY + BANKNIFTY market-regime context.
- Liquidity and abnormal-volume risk flags.
- Volatility-aware stop loss.
- Targets at **2R / 3R / 4R**.
- Position sizing for a **₹25,000 default budget**.
- Default planned risk is **0.75% of capital per position** (₹187.50 on ₹25k).
- Sector board returns the highest-scoring qualifying candidate per sector.
- Budget planner limits the number of simultaneous positions.
- Optional Yahoo Finance fundamental cross-check: P/E, P/B, ROE, debt/equity, market cap and 52-week range.
- CSV export and candlestick chart.

## Important interpretation

The tool does **not** predict or guarantee which stock will perform best over the next month. A higher score means more of the defined research conditions are satisfied at the time of the scan.

"Low loss" is implemented as **low planned monetary risk through position sizing**, not by forcing an unrealistically tight stop. A gap, slippage or liquidity event can cause a realized loss larger than the planned SL.

The sector table is a research watchlist. With ₹25k, the budget planner intentionally limits simultaneous positions rather than buying every sector candidate.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Data

The default market feed is Yahoo Finance through yfinance. It is a research feed and should not be treated as a guaranteed real-time/licensed NSE/BSE feed. Fundamental metadata may be missing or stale.

For production live alerts, connect a licensed market-data provider and store credentials in Streamlit secrets.

## Risk

This is a research/education tool, not investment advice. Under-₹100 stocks can have high volatility and lower liquidity. Re-check the current price, corporate actions, liquidity and news before trading.
