import numpy as np
import pandas as pd


def _rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def add_indicators(df):
    x = df.copy()
    close = x["Close"]
    x["SMA20"] = close.rolling(20).mean()
    x["SMA50"] = close.rolling(50).mean()
    x["SMA200"] = close.rolling(200).mean()
    x["RSI"] = _rsi(close)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    x["MACD"] = ema12 - ema26
    x["MACDSignal"] = x["MACD"].ewm(span=9, adjust=False).mean()
    tr = pd.concat([(x.High-x.Low), (x.High-x.Close.shift()).abs(), (x.Low-x.Close.shift()).abs()], axis=1).max(axis=1)
    x["ATR14"] = tr.rolling(14).mean()
    x["AvgVol20"] = x.Volume.rolling(20).mean()
    x["RVOL"] = x.Volume / x.AvgVol20.replace(0, np.nan)
    x["High20"] = x.High.rolling(20).max().shift(1)
    x["Low20"] = x.Low.rolling(20).min().shift(1)
    x["AvgValue20"] = (x.Close * x.Volume).rolling(20).mean()
    return x


def analyze_stock(df, capital=40000, risk_rupees=400, low_price_risk=200):
    if df is None or len(df) < 210:
        return None
    x = add_indicators(df).dropna().copy()
    if x.empty:
        return None
    r = x.iloc[-1]
    p = float(r.Close)
    atr = max(float(r.ATR14), p * 0.005)
    reasons, score = [], 0

    if p > r.SMA20: score += 10; reasons.append("Price>SMA20")
    if p > r.SMA50: score += 10; reasons.append("Price>SMA50")
    if p > r.SMA200: score += 10; reasons.append("Price>SMA200")
    if r.SMA20 > r.SMA50: score += 8; reasons.append("20DMA>50DMA")
    if r.SMA50 > r.SMA200: score += 7; reasons.append("50DMA>200DMA")
    if 50 <= r.RSI <= 68: score += 10; reasons.append("RSI healthy")
    if r.MACD > r.MACDSignal: score += 8; reasons.append("MACD bullish")
    if r.RVOL >= 1.5: score += 10; reasons.append("RVOL>=1.5x")
    if p > r.High20: score += 12; reasons.append("20D breakout")
    elif p >= r.High20 * 0.97: score += 6; reasons.append("Near breakout")
    if p > r.SMA20 and r.Low20 < p: score += 5; reasons.append("Trend structure")

    low_price = p < 50
    min_value = 2_000_000 if low_price else 5_000_000
    liquidity_ok = float(r.AvgValue20) >= min_value
    if liquidity_ok: score += 5; reasons.append("Liquidity filter passed")
    else: reasons.append("Low liquidity caution")

    risk_budget = low_price_risk if low_price else risk_rupees
    sl = max(p - 1.5 * atr, 0.01)
    risk_per_share = p - sl
    qty_by_risk = int(risk_budget / risk_per_share) if risk_per_share > 0 else 0
    qty_by_capital = int(capital / p) if p > 0 else 0
    qty = max(0, min(qty_by_risk, qty_by_capital))
    t1, t2, t3 = p + 1.5*risk_per_share, p + 2.5*risk_per_share, p + 4*risk_per_share

    if score >= 78 and liquidity_ok: signal = "BUY WATCH"
    elif score >= 62 and liquidity_ok: signal = "WATCH"
    else: signal = "AVOID/WAIT"

    confidence = min(95, max(35, score + (5 if liquidity_ok else -10)))
    return {
        "Price": p, "Score": int(score), "Signal": signal, "Confidence": int(confidence),
        "RSI": float(r.RSI), "RVOL": float(r.RVOL), "ATR": atr,
        "SMA20": float(r.SMA20), "SMA50": float(r.SMA50), "SMA200": float(r.SMA200),
        "Entry": p, "SL": sl, "T1": t1, "T2": t2, "T3": t3,
        "RR_T1": 1.5, "RR_T2": 2.5, "RR_T3": 4.0, "Quantity": qty,
        "RiskRs": round(qty*risk_per_share, 2),
        "ProfitT1Rs": round(qty*(t1-p), 2), "ProfitT2Rs": round(qty*(t2-p), 2), "ProfitT3Rs": round(qty*(t3-p), 2),
        "ExpectedHold": "7-30 trading days", "LiquidityOK": liquidity_ok,
        "Reasons": ", ".join(reasons)
    }
