import numpy as np
import pandas as pd
from datetime import datetime, date
import yfinance as yf
import streamlit as st

st.set_page_config(page_title="Hero Zero Stock Options Scanner", page_icon="🎯", layout="wide")
st.title("🎯 HERO ZERO — NSE Stock Options Expiry Scanner")
st.caption("Long stock options only: nearest expiry, premium ≤ ₹1, high-lot underlyings, CE + PE candidates.")

LOT_FILE="hero_zero_lots.csv"

@st.cache_data(ttl=900, show_spinner=False)
def load_lots():
    try:
        d=pd.read_csv(LOT_FILE)
        d["SYMBOL"]=d.SYMBOL.astype(str).str.upper().str.strip()
        d["LOT_SIZE"]=pd.to_numeric(d.LOT_SIZE,errors="coerce")
        return d.dropna(subset=["LOT_SIZE"]).drop_duplicates("SYMBOL")
    except Exception:
        return pd.DataFrame(columns=["SYMBOL","LOT_SIZE"])

@st.cache_data(ttl=300, show_spinner=False)
def intraday(sym):
    try:
        d=yf.Ticker(sym+".NS").history(period="60d",interval="15m",auto_adjust=False)
        if d.empty:return pd.DataFrame()
        d=d.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
        return d.dropna(subset=["open","high","low","close"])
    except Exception:return pd.DataFrame()

@st.cache_data(ttl=120, show_spinner=False)
def chain(sym,expiry):
    try:
        c=yf.Ticker(sym+".NS").option_chain(expiry)
        ce,pe=c.calls.copy(),c.puts.copy()
        ce["TYPE"]="CE";pe["TYPE"]="PE"
        return pd.concat([ce,pe],ignore_index=True)
    except Exception:return pd.DataFrame()

def tech(d):
    if len(d)<80:return None
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
    up=x.high.diff();dn=-x.low.diff()
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
    x["body_ratio"]=(x.close-x.open).abs()/(x.high-x.low).replace(0,np.nan)
    x=x.dropna(subset=["e9","e21","e50","rsi","atr","adx","vwap","rvol"])
    if len(x)<20:return None
    a=x.iloc[-1];p=x.iloc[-2]
    up=dn=0;ru=[];rd=[]
    if a.e9>a.e21>a.e50:up+=20;ru.append("EMA stack")
    if a.e9<a.e21<a.e50:dn+=20;rd.append("EMA stack")
    if a.close>a.vwap:up+=10;ru.append("VWAP")
    if a.close<a.vwap:dn+=10;rd.append("VWAP")
    if a.adx>=20:up+=8;dn+=8
    if a.rsi>=52 and a.rsi<=72:up+=10;ru.append("RSI")
    if a.rsi<=48 and a.rsi>=28:dn+=10;rd.append("RSI")
    if a.rvol>=1.2:up+=10;dn+=10;ru.append("RVOL");rd.append("RVOL")
    if a.close>a.hh20 and a.body_ratio>=.55:up+=18;ru.append("20-bar breakout")
    if a.close<a.ll20 and a.body_ratio>=.55:dn+=18;rd.append("20-bar breakdown")
    q=x.iloc[-6:-1]
    if len(q):
        if a.low<q.low.min() and a.close>q.low.min():up+=12;ru.append("sell-side sweep/reclaim")
        if a.high>q.high.max() and a.close<q.high.max():dn+=12;rd.append("buy-side sweep/rejection")
    if a.close>p.close and a.close>a.e9:up+=7
    if a.close<p.close and a.close<a.e9:dn+=7
    side="CE" if up>dn else "PE"
    return {"side":side,"score":int(min(100,max(up,dn))),"underlying":float(a.close),
            "atr":float(a.atr),"rsi":float(a.rsi),"adx":float(a.adx),"rvol":float(a.rvol),
            "reasons":"; ".join(ru if side=="CE" else rd)}

def expiry(sym):
    try:
        ex=list(yf.Ticker(sym+".NS").options)
        f=[e for e in ex if datetime.strptime(e,"%Y-%m-%d").date()>=date.today()]
        return min(f) if f else None
    except Exception:return None

def candidate(o,t,lot,max_prem,min_oi,min_vol,max_spread):
    prem=float(o.get("lastPrice",np.nan));bid=float(o.get("bid",np.nan));ask=float(o.get("ask",np.nan))
    vol=float(o.get("volume",0) or 0);oi=float(o.get("openInterest",0) or 0)
    if not np.isfinite(prem) or prem<=0 or prem>max_prem:return None
    if not np.isfinite(bid) or not np.isfinite(ask) or ask<=0:return None
    sp=(ask-bid)/max(prem,.01)*100
    if sp>max_spread or vol<min_vol or oi<min_oi:return None
    entry=round(prem,2);sl=round(max(.05,entry*.70),2)
    t1=round(entry*1.50,2);t2=round(entry*2,2);t3=round(entry*3,2)
    return {"Symbol":o["SYMBOL"],"Type":o["TYPE"],"Expiry":o["expiry"],"Strike":float(o["strike"]),
            "Premium":entry,"Entry":entry,"SL":sl,"T1":t1,"T2":t2,"T3":t3,"LotSize":lot,
            "Risk/Lot":round((entry-sl)*lot,2),"T1 P/L/Lot":round((t1-entry)*lot,2),
            "T2 P/L/Lot":round((t2-entry)*lot,2),"T3 P/L/Lot":round((t3-entry)*lot,2),
            "Volume":vol,"OI":oi,"SpreadPct":round(sp,1),"Score":t["score"],"RSI":t["rsi"],
            "ADX":t["adx"],"RVOL":t["rvol"],"Underlying":t["underlying"],"Setup":"ALIGNED" if o["TYPE"]==t["side"] else "OPPOSITE",
            "Reasons":t["reasons"]}

lots=load_lots()
st.sidebar.header("⚙️ Controls")
min_lot=st.sidebar.number_input("Minimum lot size",1,30000,500,50)
max_prem=st.sidebar.number_input("Maximum premium ₹",.05,1.00,1.00,.05)
min_score=st.sidebar.slider("Minimum technical score",50,90,68)
min_oi=st.sidebar.number_input("Minimum option OI",0,10000000,500,500)
min_vol=st.sidebar.number_input("Minimum option volume",0,10000000,100,100)
max_spread=st.sidebar.slider("Max bid/ask spread %",5,60,35)
budget=st.sidebar.number_input("Budget ₹",500,1000000,5000,500)
if st.sidebar.button("🔄 Clear & scan"):st.cache_data.clear();st.session_state.pop("hero_zero",None)

if lots.empty:
    st.error("hero_zero_lots.csv is empty. Add current NSE lot sizes.");st.stop()
u=lots[lots.LOT_SIZE>=min_lot].copy()
st.info(f"Universe: {len(u)} stocks with lot size ≥ {min_lot}. Nearest stock-option expiry only; premium ≤ ₹{max_prem:.2f}.")

if "hero_zero" not in st.session_state:
    out=[];bar=st.progress(0)
    for n,(_,rr) in enumerate(u.iterrows(),1):
        sym=rr.SYMBOL;lot=int(rr.LOT_SIZE)
        try:
            d=intraday(sym);t=tech(d)
            if not t or t["score"]<min_score:bar.progress(n/len(u));continue
            ex=expiry(sym)
            if not ex:bar.progress(n/len(u));continue
            c=chain(sym,ex)
            if c.empty:bar.progress(n/len(u));continue
            c["SYMBOL"]=sym;c["expiry"]=ex
            for _,o in c.iterrows():
                strike=float(o.get("strike",0));s=t["underlying"]
                otm=((strike-s)/s*100) if o["TYPE"]=="CE" else ((s-strike)/s*100)
                if otm<-2 or otm>4:continue
                z=candidate(o,t,lot,max_prem,min_oi,min_vol,max_spread)
                if z:z["OTM%"]=round(otm,2);out.append(z)
        except Exception:pass
        bar.progress(n/len(u))
    bar.empty();st.session_state.hero_zero=pd.DataFrame(out)

df=st.session_state.hero_zero.copy()
if df.empty:
    st.warning("No contract passes every filter. Output = WAIT; the scanner does not force a trade.");st.stop()
df["RankScore"]=df.Score+df.Setup.eq("ALIGNED")*8+np.minimum(df.RVOL,3)*3+np.minimum(np.log1p(df.OI)/10,4)
df=df.sort_values(["RankScore","Volume","OI"],ascending=False).reset_index(drop=True)
cols=["Symbol","Type","Expiry","Strike","Premium","Entry","SL","T1","T2","T3","LotSize","Risk/Lot","T1 P/L/Lot","T2 P/L/Lot","T3 P/L/Lot","Volume","OI","SpreadPct","Score","Setup","OTM%","Reasons"]

a,b,c,d=st.columns(4)
a.metric("Qualified contracts",len(df));b.metric("Stocks",df.Symbol.nunique());c.metric("BUY CE",int((df.Type=="CE").sum()));d.metric("BUY PE",int((df.Type=="PE").sum()))
st.subheader("🎯 Live research candidates — current expiry")
st.dataframe(df[cols].head(50).round(2),use_container_width=True,hide_index=True)

st.subheader("🟢 BUY CE / 🔴 BUY PE")
x,y=st.columns(2)
with x:
    st.markdown("### 🟢 BUY CE")
    st.dataframe(df[df.Type=="CE"].groupby("Symbol",as_index=False).first()[cols].head(10).round(2),use_container_width=True,hide_index=True)
with y:
    st.markdown("### 🔴 BUY PE")
    st.dataframe(df[df.Type=="PE"].groupby("Symbol",as_index=False).first()[cols].head(10).round(2),use_container_width=True,hide_index=True)

st.subheader("💰 Contract calculator")
idx=st.selectbox("Select candidate",df.index.tolist(),format_func=lambda i:f'{df.loc[i,"Symbol"]} {df.loc[i,"Type"]} {df.loc[i,"Strike"]} | ₹{df.loc[i,"Premium"]:.2f}')
r=df.loc[idx];one=r.Premium*r.LotSize;lots_allowed=int(budget//one) if one else 0
m1,m2,m3,m4=st.columns(4)
m1.metric("Entry",f"₹{r.Entry:.2f}");m2.metric("SL",f"₹{r.SL:.2f}");m3.metric("T1/T2/T3",f"₹{r.T1:.2f}/{r.T2:.2f}/{r.T3:.2f}");m4.metric("Lots by budget",lots_allowed)
st.write(f"1 lot outlay: **₹{one:,.2f}** | planned SL risk: **₹{r['Risk/Lot']:,.2f}** | T1/T2/T3 P/L: **₹{r['T1 P/L/Lot']:,.2f} / ₹{r['T2 P/L/Lot']:,.2f} / ₹{r['T3 P/L/Lot']:,.2f}**")
st.write(f"Underlying: **₹{r.Underlying:.2f}** | RSI {r.RSI:.1f} | ADX {r.ADX:.1f} | RVOL {r.RVOL:.2f} | technical score {r.Score}")
st.write(f"Evidence: **{r.Reasons}**")

st.subheader("⚠️ Risk rules")
st.markdown("- Long options only; no naked option selling.\n- Stock options only; nearest expiry.\n- Premium ≤ ₹1 is a filter, not a quality guarantee.\n- High-lot filter is configurable because NSE lot sizes change.\n- OI, volume and spread filters are intended to reduce untradeable contracts.\n- A ₹1 option can lose most/all value quickly; slippage can exceed the planned SL.\n- No guaranteed-success claim: backtest and paper-trade before live use.\n- Verify live LTP, expiry, lot size, OI, volume and bid/ask with your broker/licensed feed before ordering.")
st.download_button("⬇️ Download CSV",df.to_csv(index=False).encode(), "hero_zero_expiry_scan.csv","text/csv")
st.caption("Research feed: yfinance/Yahoo Finance. Live execution should use a broker/licensed market-data feed.")
