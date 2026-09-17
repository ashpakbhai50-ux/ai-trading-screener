import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="NSE/BSE AI Stock Screener", layout="wide")
st.title("🇮🇳 NSE / BSE Stock Analysis Screener")
st.caption("Technical screening for research — not financial advice.")

DEFAULT_SYMBOLS = "RELIANCE, TCS, HDFCBANK, ICICIBANK, SBIN, INFY, ITC, LT, AXISBANK, MARUTI, TATASTEEL, ADANIENT, BEL, NHPC, IRFC"

@st.cache_data(ttl=300)
def load_data(symbol):
    ticker = yf.Ticker(symbol + ".NS")
    df = ticker.history(period="1y", interval="1d", auto_adjust=True)
    if df.empty:
        ticker = yf.Ticker(symbol + ".BO")
        df = ticker.history(period="1y", interval="1d", auto_adjust=True)
    return df

def analyze(df):
    if len(df) < 60:
        return None
    close, vol = df["Close"], df["Volume"]
    sma20, sma50 = close.rolling(20).mean(), close.rolling(50).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    ema12, ema26 = close.ewm(span=12, adjust=False).mean(), close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    avg_vol = vol.rolling(20).mean()
    latest = close.iloc[-1]
    score = 0
    reasons = []
    if latest > sma20.iloc[-1]: score += 15; reasons.append("Price > SMA20")
    if latest > sma50.iloc[-1]: score += 20; reasons.append("Price > SMA50")
    if sma20.iloc[-1] > sma50.iloc[-1]: score += 20; reasons.append("SMA20 > SMA50")
    if 50 <= rsi.iloc[-1] <= 70: score += 15; reasons.append("RSI bullish zone")
    if macd.iloc[-1] > signal.iloc[-1]: score += 15; reasons.append("MACD bullish")
    if vol.iloc[-1] > avg_vol.iloc[-1] * 1.2: score += 15; reasons.append("Volume expansion")
    atr = (df["High"] - df["Low"]).rolling(14).mean().iloc[-1]
    sl = latest - 1.5 * atr
    t1 = latest + 2 * (latest - sl)
    t2 = latest + 3 * (latest - sl)
    return {"Price": latest, "Score": score, "RSI": rsi.iloc[-1], "SMA20": sma20.iloc[-1], "SMA50": sma50.iloc[-1], "MACD": macd.iloc[-1], "Signal": signal.iloc[-1], "Volume": vol.iloc[-1], "AvgVol": avg_vol.iloc[-1], "SL": sl, "T1": t1, "T2": t2, "Reasons": ", ".join(reasons)}

symbols = st.sidebar.text_area("NSE/BSE symbols", DEFAULT_SYMBOLS).upper().replace(" ", "").split(",")
min_score = st.sidebar.slider("Minimum technical score", 0, 100, 55)
show_all = st.sidebar.checkbox("Show all analyzed stocks", True)

rows = []
for symbol in symbols:
    try:
        result = analyze(load_data(symbol))
        if result:
            result["Symbol"] = symbol
            result["Signal"] = "BUY WATCH" if result["Score"] >= min_score else "WAIT"
            rows.append(result)
    except Exception as e:
        pass

if rows:
    out = pd.DataFrame(rows).sort_values("Score", ascending=False)
    display = out if show_all else out[out.Score >= min_score]
    st.subheader("Market Scan")
    st.dataframe(display[["Symbol","Price","Score","Signal","RSI","SMA20","SMA50","SL","T1","T2","Reasons"]].round(2), use_container_width=True)
    st.info("Score is a rule-based technical score, not a guaranteed prediction. Verify liquidity, news, fundamentals and risk before trading.")
else:
    st.warning("No usable market data returned. Try again during/after market data availability or check symbols.")
