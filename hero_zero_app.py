import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from datetime import datetime, date

st.set_page_config(page_title="Hero Zero V2", page_icon="🎯", layout="wide")
st.title("🎯 HERO ZERO V2 — Stock Options Expiry Scanner")
st.caption("Stock options only • expiry focus • premium ≤ ₹1 • CE/PE • multi-factor confirmation")

LOT_FILE="hero_zero_lots.csv"

@st.cache_data(ttl=1800)
def load_lots():
    try:
        x=pd.read_csv(LOT_FILE)
        x["SYMBOL"]=x.SYMBOL.astype(str).str.upper().str.strip()
        x["LOT_SIZE"]=pd.to_numeric(x.LOT_SIZE,errors="coerce")
        return x.dropna(subset=["LOT_SIZE"]).drop_duplicates("SYMBOL")
    except Exception:
        return pd.DataFrame(columns=["SYMBOL","LOT_SIZE"])

@st.cache_data(ttl=120,show_spinner=False)
def candles(sym,interval="15m"):
    try:
        x=yf.Ticker(sym+".NS").history(period="60d",interval=interval,auto_adjust=False)
        if x.empty:return pd.DataFrame()
        x=x.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
        return x.dropna(subset=["open","high","low","close"])
    except Exception:return pd.DataFrame()

@st.cache_data(ttl=60,show_spinner=False)
def option_chain(sym,expiry):
    try:
        c=yf.Ticker(sym+".NS").option_chain(expiry)
        ce,pe=c.calls.copy(),c.puts.copy()
        ce["TYPE"],pe["TYPE"]="CE","PE"
        return pd.concat([ce,pe],ignore_index=True)
    except Exception:return pd.DataFrame()

@st.cache_data(ttl=60,show_spinner=False)
def expiries(sym):
    try:
        return [e for e in yf.Ticker(sym+".NS").options if datetime.strptime(e,"%Y-%m-%d").date()>=date.today()]
    except Exception:return []

def tech(d):
    if len(d)<100:return None
    x=d.copy()
    x["e9"]=x.close.ewm(span=9,adjust=False).mean()
    x["e21"]=x.close.ewm(span=21,adjust=False).mean()
    x["e50"]=x.close.ewm(span=50,adjust=False).mean()
    ch=x.close.diff()
    g=ch.clip(lower=0).ewm(alpha=1/14,adjust=False).mean()
    l=(-ch.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    x["rsi"]=100-100/(1+g/l.replace(0,np.nan))
    tr=pd.concat([x.high-x.low,(x.high-x.close.shift()).abs(),(x.low-x.close.shift()).abs()],axis=1).max(axis=1)
    x["atr"]=tr.ewm(alpha=1/14,adjust=False).mean()
    up,dn=x.high.diff(),-x.low.diff()
    pdm=pd.Series(np.where((up>dn)&(up>0),up,0),index=x.index)
    mdm=pd.Series(np.where((dn>up)&(dn>0),dn,0),index=x.index)
    pdi=100*pdm.ewm(alpha=1/14,adjust=False).mean()/x.atr.replace(0,np.nan)
    mdi=100*mdm.ewm(alpha=1/14,adjust=False).mean()/x.atr.replace(0,np.nan)
    x["adx"]=(100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/14,adjust=False).mean()
    tp=(x.high+x.low+x.close)/3
    day=pd.Series(x.index.date,index=x.index)
    x["vwap"]=(tp*x.volume).groupby(day).cumsum()/x.volume.groupby(day).cumsum().replace(0,np.nan)
    x["rvol"]=x.volume/x.volume.rolling(20).mean().replace(0,np.nan)
    x["hh20"]=x.high.rolling(20).max().shift(1)
    x["ll20"]=x.low.rolling(20).min().shift(1)
    x["body"]=(x.close-x.open).abs()/(x.high-x.low).replace(0,np.nan)
    x=x.dropna(subset=["e9","e21","e50","rsi","atr","adx","vwap","rvol"])
    if len(x)<30:return None
    a,p=x.iloc[-1],x.iloc[-2]
    bull=bear=0;br=[];sr=[]
    if a.e9>a.e21>a.e50:bull+=18;br.append("EMA9>21>50")
    if a.e9<a.e21<a.e50:bear+=18;sr.append("EMA9<21<50")
    if a.close>a.vwap:bull+=12;br.append("VWAP")
    else:bear+=12;sr.append("below VWAP")
    if a.adx>=22:bull+=7;bear+=7
    if 52<=a.rsi<=70:bull+=10;br.append("RSI")
    if 30<=a.rsi<=48:bear+=10;sr.append("RSI")
    if a.rvol>=1.25:bull+=8;bear+=8;br.append("RVOL")
    if a.close>a.hh20 and a.body>=.55:bull+=15;br.append("20-bar breakout")
    if a.close<a.ll20 and a.body>=.55:bear+=15;sr.append("20-bar breakdown")
    q=x.iloc[-7:-1]
    if len(q):
        if a.low<q.low.min() and a.close>q.low.min():bull+=12;br.append("sell-side sweep/reclaim")
        if a.high>q.high.max() and a.close<q.high.max():bear+=12;sr.append("buy-side sweep/rejection")
    if a.close>p.close:bull+=5
    if a.close<p.close:bear+=5
    side="CE" if bull>bear else "PE"
    return {"side":side,"score":max(bull,bear),"close":float(a.close),"rsi":float(a.rsi),"adx":float(a.adx),"rvol":float(a.rvol),"reasons":"; ".join(br if side=="CE" else sr)}

def candidate(o,t,lot,max_prem,min_oi,min_vol,max_spread,expiry_only):
    prem=float(o.get("lastPrice",np.nan) or np.nan)
    bid=float(o.get("bid",np.nan) or np.nan);ask=float(o.get("ask",np.nan) or np.nan)
    vol=float(o.get("volume",0) or 0);oi=float(o.get("openInterest",0) or 0)
    if not np.isfinite(prem) or prem<=0 or prem>max_prem:return None
    if not np.isfinite(bid) or not np.isfinite(ask) or ask<=0:return None
    spread=(ask-bid)/max(prem,.05)*100
    if spread>max_spread or vol<min_vol or oi<min_oi:return None
    ex=datetime.strptime(o["expiry"],"%Y-%m-%d").date();days=(ex-date.today()).days
    if expiry_only and days!=0:return None
    if o["TYPE"]!=t["side"]:return None
    entry=round(prem,2);sl=round(max(.05,entry*.70),2)
    t1=round(entry*1.5,2);t2=round(entry*2,2);t3=round(entry*3,2)
    return {"Signal":"BUY "+o["TYPE"],"Symbol":o["SYMBOL"],"Expiry":o["expiry"],"Days":days,"Strike":float(o["strike"]),
            "Premium":entry,"Entry":entry,"SL":sl,"T1":t1,"T2":t2,"T3":t3,"Lot":lot,
            "Cost/Lot":round(entry*lot,2),"Risk/Lot":round((entry-sl)*lot,2),
            "T1 P/L":round((t1-entry)*lot,2),"T2 P/L":round((t2-entry)*lot,2),"T3 P/L":round((t3-entry)*lot,2),
            "OI":oi,"Volume":vol,"Spread%":round(spread,1),"Score":int(t["score"]),"RSI":round(t["rsi"],1),
            "ADX":round(t["adx"],1),"RVOL":round(t["rvol"],2),"Underlying":round(t["close"],2),"Reasons":t["reasons"]}

lots=load_lots()
st.sidebar.header("⚙️ V2 Controls")
min_lot=st.sidebar.number_input("Minimum lot size",1,30000,1000,100)
max_prem=st.sidebar.number_input("Max premium ₹",.05,1.00,1.00,.05)
min_score=st.sidebar.slider("Minimum technical score",50,95,72)
min_oi=st.sidebar.number_input("Minimum OI",0,10000000,1000,500)
min_vol=st.sidebar.number_input("Minimum option volume",0,10000000,250,100)
max_spread=st.sidebar.slider("Max spread %",5,60,25)
budget=st.sidebar.number_input("Budget ₹",500,1000000,5000,500)
expiry_only=st.sidebar.checkbox("Expiry-day contracts ONLY",True)
near_otm=st.sidebar.slider("Minimum OTM %",-2.0,2.0,-1.0,.5)
far_otm=st.sidebar.slider("Maximum OTM %",1.0,8.0,3.0,.5)
if st.sidebar.button("🔄 Fresh scan"):
    st.cache_data.clear();st.session_state.pop("hzv2",None)

if lots.empty:st.error("Lot-size file missing/empty.");st.stop()
u=lots[lots.LOT_SIZE>=min_lot].copy()
st.info(f"Universe: {len(u)} high-lot stocks • premium ≤ ₹{max_prem:.2f} • aligned CE/PE only • expiry focus.")

if "hzv2" not in st.session_state:
    rows=[];bar=st.progress(0)
    for i,(_,r) in enumerate(u.iterrows(),1):
        sym=r.SYMBOL;lot=int(r.LOT_SIZE)
        try:
            t=tech(candles(sym,"15m"))
            if not t or t["score"]<min_score:bar.progress(i/len(u));continue
            exs=expiries(sym)
            if not exs:bar.progress(i/len(u));continue
            ex=exs[0];c=option_chain(sym,ex)
            if c.empty:bar.progress(i/len(u));continue
            c["SYMBOL"]=sym;c["expiry"]=ex;s=t["close"]
            for _,o in c.iterrows():
                strike=float(o.get("strike",0))
                otm=((strike-s)/s*100) if o["TYPE"]=="CE" else ((s-strike)/s*100)
                if otm<near_otm or otm>far_otm:continue
                z=candidate(o,t,lot,max_prem,min_oi,min_vol,max_spread,expiry_only)
                if z:z["OTM%"]=round(otm,2);rows.append(z)
        except Exception:pass
        bar.progress(i/len(u))
    bar.empty();st.session_state.hzv2=pd.DataFrame(rows)

df=st.session_state.hzv2.copy()
if df.empty:
    st.warning("WAIT — no contract passed every V2 filter. Do not force a trade.");st.stop()
df["Rank"]=df.Score+np.minimum(df.RVOL,3)*4+np.minimum(np.log1p(df.OI)/10,5)
df=df.sort_values(["Rank","Volume","OI"],ascending=False).reset_index(drop=True)

a,b,c,d=st.columns(4)
a.metric("Qualified",len(df));b.metric("Stocks",df.Symbol.nunique());c.metric("BUY CE",int((df.Signal=="BUY CE").sum()));d.metric("BUY PE",int((df.Signal=="BUY PE").sum()))
st.subheader("🎯 V2 Trade Candidates")
cols=["Signal","Symbol","Expiry","Days","Strike","Premium","Entry","SL","T1","T2","T3","Lot","Cost/Lot","Risk/Lot","T1 P/L","T2 P/L","T3 P/L","OI","Volume","Spread%","Score","RSI","ADX","RVOL","Underlying","OTM%","Reasons"]
st.dataframe(df[cols].head(50),use_container_width=True,hide_index=True)

ce,pe=st.columns(2)
with ce:
    st.subheader("🟢 BUY CE");st.dataframe(df[df.Signal=="BUY CE"].head(10)[cols],use_container_width=True,hide_index=True)
with pe:
    st.subheader("🔴 BUY PE");st.dataframe(df[df.Signal=="BUY PE"].head(10)[cols],use_container_width=True,hide_index=True)

st.subheader("💰 Position calculator")
i=st.selectbox("Candidate",df.index,format_func=lambda i:f'{df.loc[i,"Signal"]} {df.loc[i,"Symbol"]} {df.loc[i,"Strike"]} @ ₹{df.loc[i,"Entry"]:.2f}')
r=df.loc[i];lot_cost=r.Entry*r.Lot;max_lots=int(budget//lot_cost) if lot_cost else 0
a,b,c,d=st.columns(4)
a.metric("Entry",f"₹{r.Entry:.2f}");b.metric("SL",f"₹{r.SL:.2f}");c.metric("T1 / T2 / T3",f"₹{r.T1:.2f} / ₹{r.T2:.2f} / ₹{r.T3:.2f}");d.metric("Lots by budget",max_lots)
st.write(f"1 lot cost: ₹{lot_cost:,.2f} • planned risk/lot: ₹{r['Risk/Lot']:,.2f} • T3 P/L/lot: ₹{r['T3 P/L']:,.2f}")

st.subheader("🧠 V2 confirmation logic")
st.markdown("Underlying: EMA 9/21/50, VWAP, RSI, ADX, RVOL, 20-bar breakout/breakdown and liquidity sweep/reclaim. Option: premium ≤ ₹1, OI, volume, spread, OTM band, nearest expiry and CE/PE alignment. Entry must still be valid at the broker. A ₹1 option can decay rapidly and become illiquid.")
st.download_button("⬇️ Download V2 CSV",df.to_csv(index=False).encode(),"hero_zero_v2_scan.csv","text/csv")
st.caption("Research feed: Yahoo Finance/yfinance. Verify live LTP, expiry, lot size, OI, volume and bid/ask with NSE/broker before ordering.")
