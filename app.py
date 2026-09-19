import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from scanner import analyze_stock
from regime import market_regime
from universe import SECTOR_UNIVERSE, ALL_STARTER, sector_for

st.set_page_config(page_title="NSE/BSE Under ₹100 Sector Swing Scanner", page_icon="🇮🇳", layout="wide")
st.title("🇮🇳 NSE/BSE Under ₹100 — 1-Month Sector Swing Scanner")
st.caption("Sector-wise research engine: one qualifying stock per sector, volatility-aware SL, 2R/3R/4R targets and ₹25k position sizing.")

MAX_PRICE=100
DEFAULT_SYMBOLS=sorted(set(sum(SECTOR_UNIVERSE.values(), [])))

@st.cache_data(ttl=300, show_spinner=False)
def load_data(symbol):
    for suffix in (".NS",".BO"):
        try:
            df=yf.download(symbol+suffix,period="2y",interval="1d",auto_adjust=True,progress=False,threads=False)
            if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
            if not df.empty and {"Open","High","Low","Close","Volume"}.issubset(df.columns):
                return df.dropna(subset=["Close"])
        except Exception:
            pass
    return pd.DataFrame()

@st.cache_data(ttl=300, show_spinner=False)
def load_index(symbol):
    try:
        df=yf.download(symbol,period="2y",interval="1d",auto_adjust=True,progress=False,threads=False)
        if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
        return df.dropna(subset=["Close"]) if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=900, show_spinner=False)
def get_fundamentals(symbol):
    try:
        t=yf.Ticker(symbol+".NS")
        info=t.get_info()
        return {
            "PE": info.get("trailingPE"),
            "PB": info.get("priceToBook"),
            "ROE": info.get("returnOnEquity"),
            "DebtEquity": info.get("debtToEquity"),
            "MarketCapCr": (info.get("marketCap") or 0)/1e7,
            "52WHigh": info.get("fiftyTwoWeekHigh"),
            "52WLow": info.get("fiftyTwoWeekLow")
        }
    except Exception:
        return {"PE":None,"PB":None,"ROE":None,"DebtEquity":None,"MarketCapCr":None,"52WHigh":None,"52WLow":None}

st.sidebar.header("⚙️ Controls")
capital=st.sidebar.number_input("Budget (₹)",min_value=5000,max_value=500000,value=25000,step=1000)
risk_pct=st.sidebar.slider("Max account risk / trade (%)",0.25,1.50,0.75,0.05)
max_price=st.sidebar.number_input("Maximum stock price (₹)",min_value=10,max_value=100,value=100,step=5)
min_score=st.sidebar.slider("Minimum setup score",50,90,62)
only_buy=st.sidebar.checkbox("Show only BUY WATCH / ENTRY",True)
refresh=st.sidebar.button("🔄 Refresh data")
if refresh: st.cache_data.clear()

st.info(f"**Risk design:** at {risk_pct:.2f}% risk, ₹{capital:,.0f} capital gives a maximum planned loss of ₹{capital*risk_pct/100:,.0f} per position. This is monetary risk control—not a guarantee that a stop will fill exactly at the SL.")

nifty=load_index("^NSEI"); bank=load_index("^NSEBANK")
nr=market_regime(nifty); br=market_regime(bank)
bias="RISK-ON" if nr["Regime"]=="RISK-ON" and br["Regime"]!="RISK-OFF" else ("RISK-OFF" if nr["Regime"]=="RISK-OFF" and br["Regime"]=="RISK-OFF" else "NEUTRAL")
a,b,c,d=st.columns(4)
a.metric("NIFTY regime",nr["Regime"]); b.metric("NIFTY ADX",f"{nr['ADX']:.1f}" if pd.notna(nr["ADX"]) else "—")
c.metric("BANKNIFTY regime",br["Regime"]); d.metric("Market bias",bias)
st.caption("Data source: Yahoo Finance/yfinance research feed. It is not a licensed guaranteed-real-time NSE/BSE feed.")

st.subheader("🔎 Scanning all sector candidates under ₹100")
symbols=DEFAULT_SYMBOLS
rows=[]; errors=[]
progress=st.progress(0)
for i,symbol in enumerate(symbols):
    df=load_data(symbol)
    try:
        result=analyze_stock(df,capital=float(capital),risk_pct=float(risk_pct),market_bias=bias,max_price=float(max_price))
        if result:
            result["Symbol"]=symbol
            result["Sector"]=sector_for(symbol)
            rows.append(result)
        else:
            errors.append(symbol)
    except Exception:
        errors.append(symbol)
    progress.progress((i+1)/max(len(symbols),1))
progress.empty()

if not rows:
    st.error("No qualifying data returned. Try refresh or lower the minimum score.")
    st.stop()

out=pd.DataFrame(rows)
out=out.sort_values(["Score","Confidence"],ascending=False)

# One best-scoring qualifying candidate per sector, without claiming it is a prediction.
sector_picks=(out.sort_values(["Sector","Score","Confidence"],ascending=[True,False,False])
              .groupby("Sector",as_index=False).first())
if only_buy:
    buy=sector_picks[sector_picks.Signal.isin(["BUY WATCH"])]
    if len(buy)>=1: sector_picks=buy

st.metric("Sectors with qualifying candidates",f"{len(sector_picks)} / {len(SECTOR_UNIVERSE)}")

cols=["Sector","Symbol","Price","Score","Stage","Signal","Confidence","Entry","SL","T1","T2","T3","Quantity","CapitalUsed","RiskRs","ProfitT1Rs","ProfitT2Rs","ProfitT3Rs","ATR_PCT","RVOL","LiquidityOK","Invalidation"]
st.dataframe(sector_picks[cols].round(2),use_container_width=True,hide_index=True)

st.subheader("💰 ₹25,000 Budget Planner")
st.write("The sector table is a **watchlist**, not a recommendation to buy every sector. With ₹25k, the planner limits simultaneous positions so the maximum planned loss stays controlled.")
portfolio=sector_picks[(sector_picks.Stage=="ENTRY") & (sector_picks.Quantity>0)].copy()
portfolio=portfolio.sort_values(["Score","Confidence"],ascending=False).head(5)
if portfolio.empty:
    st.warning("No ENTRY setup currently passes the strict filters. Waiting is an intentional output of the system.")
else:
    st.dataframe(portfolio[["Sector","Symbol","Price","Score","Entry","SL","T1","T2","T3","Quantity","CapitalUsed","RiskRs","ProfitT1Rs","ProfitT2Rs","ProfitT3Rs"]].round(2),use_container_width=True,hide_index=True)
    st.write(f"Planned capital used: **₹{portfolio.CapitalUsed.sum():,.0f}** | Planned maximum stop risk: **₹{portfolio.RiskRs.sum():,.0f}**")

st.subheader("🧾 Fundamental cross-check for sector picks")
fund_rows=[]
for _,r in sector_picks.iterrows():
    f=get_fundamentals(r.Symbol)
    fund_rows.append({"Sector":r.Sector,"Symbol":r.Symbol,**f})
fund=pd.DataFrame(fund_rows)
st.dataframe(fund.round(2),use_container_width=True,hide_index=True)
st.caption("Fundamental fields come from Yahoo Finance company metadata when available and may be missing/stale. They are a cross-check, not a forecast.")

st.subheader("📈 Detailed setup")
selected=st.selectbox("Select stock",sector_picks.Symbol.tolist())
rr=sector_picks[sector_picks.Symbol==selected].iloc[0]
sdf=load_data(selected)
if not sdf.empty:
    chart=sdf.tail(180).copy()
    chart["SMA20"]=chart.Close.rolling(20).mean(); chart["SMA50"]=chart.Close.rolling(50).mean()
    fig=go.Figure()
    fig.add_trace(go.Candlestick(x=chart.index,open=chart.Open,high=chart.High,low=chart.Low,close=chart.Close,name="Price"))
    fig.add_trace(go.Scatter(x=chart.index,y=chart.SMA20,name="SMA20"))
    fig.add_trace(go.Scatter(x=chart.index,y=chart.SMA50,name="SMA50"))
    for col in ["Entry","SL","T1","T2","T3"]:
        fig.add_hline(y=float(rr[col]),annotation_text=f"{col} ₹{float(rr[col]):.2f}")
    fig.update_layout(height=560,xaxis_rangeslider_visible=False,margin=dict(l=10,r=10,t=20,b=10))
    st.plotly_chart(fig,use_container_width=True)
    x1,x2,x3,x4=st.columns(4)
    x1.metric("Score",rr.Score); x2.metric("Confidence",f"{rr.Confidence}%"); x3.metric("SL risk",f"₹{rr.RiskRs:.0f}"); x4.metric("ATR",f"{rr.ATR_PCT:.2f}%")
    st.write(f"**Why it qualified:** {rr.Reasons}")
    st.write(f"**Invalidation:** {rr.Invalidation}")
    st.write(f"**Expected holding window:** {rr.ExpectedHold}")

st.subheader("📥 Export")
st.download_button("⬇️ Download sector scan CSV",sector_picks.to_csv(index=False).encode("utf-8"),"sector_under_100_scan.csv","text/csv")
st.warning("Important: a scanner cannot know the future or guarantee a one-month return. Under-₹100 shares can be volatile and illiquid. Use the SL as a predefined exit level, avoid averaging down, and re-check the latest quote before placing an order.")
