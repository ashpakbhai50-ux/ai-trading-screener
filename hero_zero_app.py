# HERO ZERO V4
# NSE-first expiry stock-options research scanner.
# Research only; no guaranteed-profit claim.

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from datetime import datetime, date, timedelta
from urllib.request import Request, urlopen
import json, math

st.set_page_config(page_title="Hero Zero V4", page_icon="🎯", layout="wide")
st.title("🎯 HERO ZERO V4 — Expiry Stock Options Scanner")
st.caption("NSE stock options only • premium ≤ ₹1 • high-lot focus • BUY CE / BUY PE • multi-factor confirmation")

LOT_FILE = "hero_zero_lots.csv"

@st.cache_data(ttl=1800)
def load_lots():
    try:
        x = pd.read_csv(LOT_FILE)
        x["SYMBOL"] = x.SYMBOL.astype(str).str.upper().str.strip()
        x["LOT_SIZE"] = pd.to_numeric(x.LOT_SIZE, errors="coerce")
        return x.dropna(subset=["LOT_SIZE"]).drop_duplicates("SYMBOL")
    except Exception:
        return pd.DataFrame(columns=["SYMBOL","LOT_SIZE"])

def nse_get(path):
    try:
        req = Request("https://www.nseindia.com" + path, headers={
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
            "Accept":"application/json,text/plain,*/*",
            "Referer":"https://www.nseindia.com/option-chain",
            "Accept-Language":"en-US,en;q=0.9"})
        with urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None

@st.cache_data(ttl=45, show_spinner=False)
def nse_quote(sym):
    data = nse_get("/api/quote-equity?symbol=" + sym)
    if not data: return None
    try:
        p = data["priceInfo"]
        return float(p.get("lastPrice")), float(p.get("open")), float(p.get("dayHigh")), float(p.get("dayLow"))
    except Exception:
        return None

@st.cache_data(ttl=45, show_spinner=False)
def nse_chain(sym):
    data = nse_get("/api/option-chain-equities?symbol=" + sym)
    if not data: return pd.DataFrame()
    rows=[]
    for z in data.get("records",{}).get("data",[]):
        for typ in ("CE","PE"):
            o=z.get(typ)
            if o:
                rows.append({
                    "SYMBOL":sym,
                    "expiry":datetime.strptime(z["expiryDate"],"%d-%b-%Y").strftime("%Y-%m-%d"),
                    "strike":float(z["strikePrice"]),
                    "TYPE":typ,
                    "lastPrice":o.get("lastPrice"),
                    "bid":o.get("bidprice"),
                    "ask":o.get("askPrice"),
                    "volume":o.get("totalTradedVolume",0),
                    "openInterest":o.get("openInterest",0),
                    "changeinOpenInterest":o.get("changeinOpenInterest",0),
                    "impliedVolatility":o.get("impliedVolatility",np.nan)
                })
    return pd.DataFrame(rows)

@st.cache_data(ttl=120, show_spinner=False)
def candles(sym):
    try:
        x=yf.Ticker(sym+".NS").history(period="60d",interval="15m",auto_adjust=False)
        x=x.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
        return x.dropna(subset=["open","high","low","close"]) if not x.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def tech(d):
    if len(d)<120: return None
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
    x["atr_pct"]=x.atr/x.close*100
    x=x.dropna()
    if len(x)<10:return None
    a,p=x.iloc[-1],x.iloc[-2]
    bull=bear=0; br=[]; sr=[]
    if a.e9>a.e21>a.e50: bull+=14;br.append("EMA")
    if a.e9<a.e21<a.e50: bear+=14;sr.append("EMA")
    if a.close>a.vwap: bull+=10;br.append("VWAP")
    else: bear+=10;sr.append("VWAP")
    if a.adx>=22: bull+=6;bear+=6
    if 52<=a.rsi<=70: bull+=8;br.append("RSI")
    if 30<=a.rsi<=48: bear+=8;sr.append("RSI")
    if a.rvol>=1.25: bull+=8;br.append("RVOL");bear+=8;sr.append("RVOL")
    if a.close>a.hh20 and a.body>=.55: bull+=14;br.append("breakout")
    if a.close<a.ll20 and a.body>=.55: bear+=14;sr.append("breakdown")
    q=x.iloc[-8:-1]
    if a.low<q.low.min() and a.close>q.low.min(): bull+=12;br.append("sell-side sweep")
    if a.high>q.high.max() and a.close<q.high.max(): bear+=12;sr.append("buy-side sweep")
    if a.close>p.close: bull+=4
    if a.close<p.close: bear+=4
    side="CE" if bull>bear else "PE"
    score=max(bull,bear)
    return {"side":side,"score":score,"close":float(a.close),"rsi":float(a.rsi),
            "adx":float(a.adx),"rvol":float(a.rvol),"atr":float(a.atr),
            "atr_pct":float(a.atr_pct),"reasons":"; ".join(br if side=="CE" else sr)}

def expiry_choice(c, mode):
    ex=sorted(pd.to_datetime(c.expiry).dt.date.unique())
    today=date.today()
    if mode=="Today only":
        return [e for e in ex if e==today]
    if mode=="Nearest expiry":
        return [min(ex,key=lambda e:abs((e-today).days))] if ex else []
    return [e for e in ex if e>=today][:2]

def score_candidate(o,t,lot,max_prem,min_oi,min_vol,max_spread,min_chg,min_score,otm_min,otm_max):
    try:
        prem=float(o.lastPrice);bid=float(o.bid);ask=float(o.ask)
        oi=float(o.openInterest);vol=float(o.volume);coi=float(o.changeinOpenInterest)
    except Exception:return None
    if not all(np.isfinite(v) for v in [prem,bid,ask]) or prem<=0 or prem>max_prem or bid<=0 or ask<=0:return None
    spread=(ask-bid)/max(prem,.05)*100
    if spread>max_spread or oi<min_oi or vol<min_vol or coi<min_chg or o.TYPE!=t["side"]:return None
    ex=datetime.strptime(o.expiry,"%Y-%m-%d").date()
    if ex<date.today():return None
    s=t["close"]
    otm=((o.strike-s)/s*100) if o.TYPE=="CE" else ((s-o.strike)/s*100)
    if not (otm_min<=otm<=otm_max):return None
    # Multi-factor 0-100 score: technical + liquidity + OI + IV/spread + expiry distance + OTM.
    oi_pct=coi/max(oi-coi,1)*100
    volume_oi=vol/max(oi,1)
    iv=float(o.impliedVolatility) if np.isfinite(float(o.impliedVolatility or np.nan)) else np.nan
    technical=min(t["score"],55)/55*55
    liquidity=max(0,10-min(spread/3,10))
    oi_score=max(0,min(12,6+oi_pct/5))
    vol_score=max(0,min(8,volume_oi*8))
    otm_score=max(0,10-abs(otm-1.0)*4)
    expiry_days=max(0,(ex-date.today()).days)
    expiry_score=10 if expiry_days==0 else 7 if expiry_days<=2 else 3
    total=technical+liquidity+oi_score+vol_score+otm_score+expiry_score
    if total<min_score:return None
    e=round(prem,2)
    # Premium-based risk levels are deliberately conservative for sub-₹1 options.
    sl=round(max(.05,e*.65),2);t1=round(e*1.5,2);t2=round(e*2.0,2);t3=round(e*3.0,2)
    return {"Signal":"BUY "+o.TYPE,"Symbol":o.SYMBOL,"Expiry":o.expiry,"Days":expiry_days,
            "Strike":o.strike,"Entry":e,"SL":sl,"T1":t1,"T2":t2,"T3":t3,"Lot":lot,
            "Cost/Lot":round(e*lot,2),"Risk/Lot":round((e-sl)*lot,2),
            "T1 P/L":round((t1-e)*lot,2),"T2 P/L":round((t2-e)*lot,2),"T3 P/L":round((t3-e)*lot,2),
            "OI":oi,"Chg OI":coi,"Chg OI %":round(oi_pct,1),"Volume":vol,"Vol/OI":round(volume_oi,2),
            "IV":round(iv,2) if np.isfinite(iv) else np.nan,"Spread%":round(spread,1),
            "Score":round(total,1),"Tech":t["score"],"RSI":round(t["rsi"],1),"ADX":round(t["adx"],1),
            "RVOL":round(t["rvol"],2),"ATR":round(t["atr"],2),"Underlying":round(s,2),
            "OTM%":round(otm,2),"Reasons":t["reasons"]}

st.sidebar.header("⚙️ V4 Controls")
min_lot=st.sidebar.number_input("Minimum lot size",1,30000,1000,100)
max_prem=st.sidebar.number_input("Max premium ₹",.05,1.0,1.0,.05)
min_score=st.sidebar.slider("Minimum Hero Zero score",50,95,70)
min_oi=st.sidebar.number_input("Minimum OI",0,10000000,1000,500)
min_vol=st.sidebar.number_input("Minimum option volume",0,10000000,250,100)
min_chg=st.sidebar.number_input("Minimum +OI change",0,1000000,0,100)
max_spread=st.sidebar.slider("Max bid/ask spread %",5,60,25)
otm_min=st.sidebar.slider("OTM minimum %",-5.0,5.0,-1.0,.5)
otm_max=st.sidebar.slider("OTM maximum %",1.0,10.0,3.0,.5)
expiry_mode=st.sidebar.selectbox("Expiry mode",["Today only","Nearest expiry","Next 2 expiries"],index=0)
budget=st.sidebar.number_input("Budget ₹",500,1000000,5000,500)
if st.sidebar.button("🔄 Fresh V4 scan"):
    st.cache_data.clear(); st.session_state.pop("v4",None)

lots=load_lots()
u=lots[lots.LOT_SIZE>=min_lot].copy()
st.info(f"Universe: {len(u)} high-lot stocks • premium ≤ ₹{max_prem:.2f} • {expiry_mode} • NSE option-chain first")

if "v4" not in st.session_state:
    rows=[];bar=st.progress(0)
    for i,(_,r) in enumerate(u.iterrows(),1):
        try:
            t=tech(candles(r.SYMBOL))
            if not t or t["score"]<min(55,min_score):bar.progress(i/len(u));continue
            c=nse_chain(r.SYMBOL)
            if c.empty:bar.progress(i/len(u));continue
            for ex in expiry_choice(c,expiry_mode):
                cc=c[c.expiry==ex.strftime("%Y-%m-%d")]
                for _,o in cc.iterrows():
                    z=score_candidate(o,t,int(r.LOT_SIZE),max_prem,min_oi,min_vol,max_spread,min_chg,min_score,otm_min,otm_max)
                    if z:rows.append(z)
        except Exception:pass
        bar.progress(i/len(u))
    bar.empty()
    st.session_state.v4=pd.DataFrame(rows)

df=st.session_state.v4.copy()
if df.empty:
    st.warning("WAIT — no contract passed all V4 filters. Do not force a trade.")
    st.stop()

df=df.sort_values(["Score","Chg OI %","Volume"],ascending=False).reset_index(drop=True)
top=df.iloc[0]
st.subheader("🏆 TOP SETUP")
m=st.columns(8)
for box,label,val in zip(m,["Signal","Symbol","Strike","Entry","SL","T1","T2","Score"],
                         [top.Signal,top.Symbol,top.Strike,f"₹{top.Entry:.2f}",f"₹{top.SL:.2f}",f"₹{top.T1:.2f}",f"₹{top.T3:.2f}",f"{top.Score:.0f}/100"]):
    box.metric(label,str(val))
a,b,c,d=st.columns(4)
a.metric("Qualified",len(df));b.metric("Stocks",df.Symbol.nunique());c.metric("BUY CE",int((df.Signal=="BUY CE").sum()));d.metric("BUY PE",int((df.Signal=="BUY PE").sum()))

cols=["Signal","Symbol","Expiry","Days","Strike","Entry","SL","T1","T2","T3","Lot","Cost/Lot","Risk/Lot","T1 P/L","T2 P/L","T3 P/L","OI","Chg OI","Chg OI %","Volume","Vol/OI","IV","Spread%","Score","Tech","RSI","ADX","RVOL","ATR","Underlying","OTM%","Reasons"]
st.subheader("🎯 V4 Trade Candidates")
st.dataframe(df[cols].head(50),use_container_width=True,hide_index=True)

ce,pe=st.columns(2)
with ce:
    st.subheader("🟢 BUY CE")
    st.dataframe(df[df.Signal=="BUY CE"].head(10)[cols],use_container_width=True,hide_index=True)
with pe:
    st.subheader("🔴 BUY PE")
    st.dataframe(df[df.Signal=="BUY PE"].head(10)[cols],use_container_width=True,hide_index=True)

st.subheader("💰 Position calculator")
idx=st.selectbox("Candidate",df.index,format_func=lambda i:f'{df.loc[i,"Signal"]} {df.loc[i,"Symbol"]} {df.loc[i,"Strike"]} @ ₹{df.loc[i,"Entry"]:.2f}')
r=df.loc[idx];cost=r.Entry*r.Lot
st.write(f"1 lot cost: ₹{cost:,.2f} • max lots by ₹{budget:,.0f}: {int(budget//cost) if cost else 0} • risk/lot: ₹{r['Risk/Lot']:,.2f}")

st.download_button("⬇️ Download V4 CSV",df.to_csv(index=False).encode(),"hero_zero_v4_scan.csv","text/csv")
st.caption("Research scanner only. NSE/broker live contract availability, lot size and execution must be verified before trading. Sub-₹1 expiry options can be highly volatile, illiquid and decay rapidly; no guaranteed-profit claim.")
