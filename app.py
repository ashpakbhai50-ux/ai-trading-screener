import streamlit as st
import pandas as pd
import yfinance as yf
from scanner import analyze_stock
from universe import QUALITY_SWING, PENNY_STARTER

st.set_page_config(page_title="NSE/BSE AI Swing Screener V2", page_icon="🇮🇳", layout="wide")
st.title("🇮🇳 NSE / BSE AI Swing Screener V2")
st.caption("Technical research engine • NSE/BSE symbols • 7–30 trading-day swing framework • signals are not guaranteed")

DEFAULT = ",".join(sorted(set(QUALITY_SWING + PENNY_STARTER)))

@st.cache_data(ttl=300, show_spinner=False)
def load_data(symbol, period="1y"):
    for suffix in (".NS", ".BO"):
        try:
            df = yf.download(symbol + suffix, period=period, interval="1d", auto_adjust=True, progress=False, threads=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if not df.empty and {"Open","High","Low","Close","Volume"}.issubset(df.columns):
                return df.dropna(subset=["Close"])
        except Exception:
            continue
    return pd.DataFrame()

st.sidebar.header("Scanner")
mode = st.sidebar.selectbox("Universe", ["All starter stocks", "Quality swing", "Penny / low-price", "Custom"])
if mode == "Quality swing":
    default_text = ",".join(QUALITY_SWING)
elif mode == "Penny / low-price":
    default_text = ",".join(PENNY_STARTER)
elif mode == "All starter stocks":
    default_text = DEFAULT
else:
    default_text = "RELIANCE,TCS,HDFCBANK,SBIN,SUZLON,YESBANK,IDEA"

symbols_text = st.sidebar.text_area("NSE/BSE symbols", default_text, height=120)
symbols = [s.strip().upper() for s in symbols_text.split(",") if s.strip()]
capital = st.sidebar.number_input("Capital (₹)", min_value=1000, value=40000, step=1000)
risk_normal = st.sidebar.number_input("Normal risk/trade (₹)", min_value=50, value=400, step=50)
risk_penny = st.sidebar.number_input("Low-price risk/trade (₹)", min_value=50, value=200, step=50)
min_score = st.sidebar.slider("Minimum score", 0, 100, 62)
refresh = st.sidebar.button("🔄 Refresh data")
if refresh:
    st.cache_data.clear()

st.info("Data source: Yahoo Finance via yfinance. Treat it as a research feed, not guaranteed real-time NSE/BSE market data.")

rows, errors = [], []
progress = st.progress(0)
for i, symbol in enumerate(symbols):
    df = load_data(symbol)
    try:
        result = analyze_stock(df, capital=float(capital), risk_rupees=float(risk_normal), low_price_risk=float(risk_penny))
        if result:
            result["Symbol"] = symbol
            result["Type"] = "Penny/Low-price" if result["Price"] < 50 else "Swing"
            rows.append(result)
        else:
            errors.append(symbol)
    except Exception:
        errors.append(symbol)
    progress.progress((i + 1) / max(len(symbols), 1))
progress.empty()

if rows:
    out = pd.DataFrame(rows).sort_values(["Score","Confidence"], ascending=False)
    watch = out[out.Score >= min_score].copy()

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Scanned", len(out))
    c2.metric("BUY WATCH", int((out.Signal == "BUY WATCH").sum()))
    c3.metric("Penny / <₹50", int((out.Price < 50).sum()))
    c4.metric("Breakout/Watch", int((out.Score >= min_score).sum()))

    st.subheader("🎯 Top Swing Setups")
    cols = ["Symbol","Type","Price","Score","Signal","Confidence","Entry","SL","T1","T2","T3","Quantity","RiskRs","ProfitT1Rs","ProfitT2Rs","ProfitT3Rs","ExpectedHold","Reasons"]
    st.dataframe(watch[cols].round(2), use_container_width=True, hide_index=True)

    st.subheader("💰 Penny / Low-Price Leaderboard")
    penny = out[out.Price < 50].sort_values("Score", ascending=False)
    if penny.empty:
        st.write("No sub-₹50 stocks in the selected universe passed the data/indicator requirements.")
    else:
        st.dataframe(penny[["Symbol","Price","Score","Signal","Confidence","Entry","SL","T1","T2","T3","Quantity","RiskRs","ProfitT1Rs","ProfitT2Rs","ProfitT3Rs","LiquidityOK"]].round(2), use_container_width=True, hide_index=True)

    st.subheader("📊 Full Scanner")
    st.dataframe(out[["Symbol","Type","Price","Score","Signal","Confidence","RSI","RVOL","SMA20","SMA50","SMA200","Entry","SL","T1","T2","T3","Quantity","RiskRs","ProfitT1Rs","ProfitT2Rs","ProfitT3Rs","LiquidityOK"]].round(2), use_container_width=True, hide_index=True)

    csv = out.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download full scan CSV", csv, "nse_bse_v2_scan.csv", "text/csv")

    st.warning("This is a rule-based technical scoring system, not an AI guarantee or investment recommendation. Penny stocks can have low liquidity and sharp price moves. Check current quotes, spreads, news, corporate actions and fundamentals before trading.")
else:
    st.error("No usable data returned. Check symbols or retry when the data feed is available.")

if errors:
    st.caption("No usable history: " + ", ".join(errors))
