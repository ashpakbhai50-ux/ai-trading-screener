import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from scanner import analyze_stock
from regime import market_regime
from universe import QUALITY_SWING, PENNY_STARTER

st.set_page_config(page_title="NSE/BSE AI Swing Screener FINAL", page_icon="🇮🇳", layout="wide", initial_sidebar_state="expanded")
st.title("🇮🇳 NSE / BSE AI Swing Screener — FINAL")
st.caption("Multi-filter technical research engine • 1–30 trading-day swing framework • not a guaranteed prediction")

DEFAULT = ",".join(sorted(set(QUALITY_SWING + PENNY_STARTER)))

@st.cache_data(ttl=300, show_spinner=False)
def load_data(symbol, period="2y"):
    for suffix in (".NS", ".BO"):
        try:
            df=yf.download(symbol+suffix, period=period, interval="1d", auto_adjust=True, progress=False, threads=False)
            if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
            if not df.empty and {"Open","High","Low","Close","Volume"}.issubset(df.columns): return df.dropna(subset=["Close"])
        except Exception: pass
    return pd.DataFrame()

@st.cache_data(ttl=300, show_spinner=False)
def load_index(symbol):
    try:
        df=yf.download(symbol,period="2y",interval="1d",auto_adjust=True,progress=False,threads=False)
        if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
        return df.dropna(subset=["Close"]) if not df.empty else pd.DataFrame()
    except Exception: return pd.DataFrame()

st.sidebar.header("⚙️ Scanner Controls")
mode=st.sidebar.selectbox("Universe",["All starter stocks","Quality swing","Penny / low-price","Custom"])
if mode=="Quality swing": default_text=",".join(QUALITY_SWING)
elif mode=="Penny / low-price": default_text=",".join(PENNY_STARTER)
elif mode=="All starter stocks": default_text=DEFAULT
else: default_text="RELIANCE,TCS,HDFCBANK,SBIN,SUZLON,YESBANK,IDEA"
symbols_text=st.sidebar.text_area("NSE/BSE symbols",default_text,height=130)
symbols=[s.strip().upper() for s in symbols_text.split(",") if s.strip()]
capital=st.sidebar.number_input("Capital (₹)",min_value=1000,value=40000,step=1000)
risk_normal=st.sidebar.number_input("Normal risk/trade (₹)",min_value=50,value=400,step=50)
risk_penny=st.sidebar.number_input("Penny risk/trade (₹)",min_value=50,value=200,step=50)
min_score=st.sidebar.slider("Minimum score",0,100,62)
show_only=st.sidebar.checkbox("Show only qualifying setups",False)
refresh=st.sidebar.button("🔄 Refresh market data")
if refresh: st.cache_data.clear()

nifty=load_index("^NSEI"); bank=load_index("^NSEBANK")
nr=market_regime(nifty); br=market_regime(bank)

m1,m2,m3,m4=st.columns(4)
m1.metric("NIFTY Regime",nr["Regime"])
m2.metric("NIFTY ADX",f"{nr['ADX']:.1f}" if pd.notna(nr['ADX']) else "—")
m3.metric("BANKNIFTY Regime",br["Regime"])
m4.metric("BANK ADX",f"{br['ADX']:.1f}" if pd.notna(br['ADX']) else "—")

bias="RISK-ON" if nr["Regime"]=="RISK-ON" and br["Regime"]!="RISK-OFF" else ("RISK-OFF" if nr["Regime"]=="RISK-OFF" and br["Regime"]=="RISK-OFF" else "NEUTRAL")
st.info(f"Market bias: **{bias}** | NIFTY: {nr['Reason']} | BANKNIFTY: {br['Reason']}")
st.caption("Feed status: Yahoo Finance/yfinance research feed; not a licensed guaranteed-live NSE/BSE feed. yfinance supports daily and intraday intervals, with intraday history limits documented by its API. ")

rows=[]; errors=[]
progress=st.progress(0)
for i,symbol in enumerate(symbols):
    df=load_data(symbol)
    try:
        result=analyze_stock(df,capital=float(capital),risk_rupees=float(risk_normal),low_price_risk=float(risk_penny),market_bias=bias)
        if result:
            result["Symbol"]=symbol; result["Type"]="Penny/Low-price" if result["Price"]<50 else "Swing"
            rows.append(result)
        else: errors.append(symbol)
    except Exception: errors.append(symbol)
    progress.progress((i+1)/max(len(symbols),1))
progress.empty()

if rows:
    out=pd.DataFrame(rows).sort_values(["Score","Confidence"],ascending=False)
    qualifying=out[out.Score>=min_score].copy()
    display=qualifying if show_only else out

    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Scanned",len(out)); c2.metric("Entry",int((out.Stage=="ENTRY").sum())); c3.metric("Confirmation",int((out.Stage=="CONFIRMATION").sum())); c4.metric("<₹50",int((out.Price<50).sum())); c5.metric("Risk flags",int((out.ManipulationRisk>=50).sum()))

    st.subheader("🎯 3-Stage Opportunity Board")
    cols=["Symbol","Type","Price","Score","Stage","Signal","Confidence","Entry","SL","T1","T2","T3","Quantity","RiskRs","ProfitT1Rs","ProfitT2Rs","ProfitT3Rs","ExpectedHold","ManipulationRisk","LiquidityOK","Invalidation"]
    st.dataframe(display[cols].round(2),use_container_width=True,hide_index=True)

    st.subheader("💰 Penny / Low-Price Leaderboard")
    penny=out[out.Price<50].sort_values(["Score","Confidence"],ascending=False)
    if penny.empty: st.write("No sub-₹50 stock returned enough history for the scanner.")
    else: st.dataframe(penny[["Symbol","Price","Score","Stage","Signal","Confidence","Entry","SL","T1","T2","T3","Quantity","RiskRs","ProfitT1Rs","ProfitT2Rs","ProfitT3Rs","ManipulationRisk","LiquidityOK"]].round(2),use_container_width=True,hide_index=True)

    st.subheader("🔎 Stock Detail + Chart")
    selected=st.selectbox("Select stock",out.Symbol.tolist())
    sdf=load_data(selected)
    if not sdf.empty:
        rr=out[out.Symbol==selected].iloc[0]
        chart=sdf.tail(180).copy()
        chart["SMA20"]=chart.Close.rolling(20).mean(); chart["SMA50"]=chart.Close.rolling(50).mean()
        fig=go.Figure()
        fig.add_trace(go.Candlestick(x=chart.index,open=chart.Open,high=chart.High,low=chart.Low,close=chart.Close,name="Price"))
        fig.add_trace(go.Scatter(x=chart.index,y=chart.SMA20,name="SMA20",mode="lines"))
        fig.add_trace(go.Scatter(x=chart.index,y=chart.SMA50,name="SMA50",mode="lines"))
        for col,name in [("Entry","Entry"),("SL","SL"),("T1","T1"),("T2","T2"),("T3","T3")]:
            fig.add_hline(y=float(rr[col]),annotation_text=f"{name} ₹{float(rr[col]):.2f}")
        fig.update_layout(height=600,xaxis_rangeslider_visible=False,margin=dict(l=10,r=10,t=30,b=10))
        st.plotly_chart(fig,use_container_width=True)
        d1,d2,d3,d4=st.columns(4)
        d1.metric("Stage",rr.Stage); d2.metric("Score",rr.Score); d3.metric("Confidence",f"{rr.Confidence}%"); d4.metric("Manipulation risk",f"{rr.ManipulationRisk}/100")
        st.write(f"**Why:** {rr.Reasons}")
        st.write(f"**Invalidation:** {rr.Invalidation}")
        st.write(f"**Risk:** ₹{rr.RiskRs:.2f} | **T1:** ₹{rr.ProfitT1Rs:.2f} | **T2:** ₹{rr.ProfitT2Rs:.2f} | **T3:** ₹{rr.ProfitT3Rs:.2f}")
        if rr.Signal in ("BUY WATCH","EARLY WATCH"):
            st.success(f"🔔 Alert condition: {selected} is currently {rr.Stage} / {rr.Signal}. Re-check the quote before acting.")

    st.subheader("📥 Export")
    st.download_button("⬇️ Download full scan CSV",out.to_csv(index=False).encode("utf-8"),"nse_bse_final_scan.csv","text/csv")
    st.warning("Research tool only. Signals are rule-based, not guaranteed predictions. Penny stocks can be illiquid or highly volatile; do not average down solely because a scanner shows a setup.")
else:
    st.error("No usable data returned. Check symbols or retry when the feed is available.")

if errors: st.caption("No usable history: "+", ".join(errors))
