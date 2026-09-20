# HERO ZERO V3
# NSE-first option-chain scanner; see repository README for usage.

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from datetime import datetime, date
from urllib.request import Request, urlopen
import json

st.set_page_config(page_title="Hero Zero V3", page_icon="🎯", layout="wide")
st.title("🎯 HERO ZERO V3 — NSE Stock Options Expiry Scanner")
st.caption("Stock options only • premium ≤ ₹1 • expiry focus • CE/PE • NSE option-chain fields + technical confirmation")
LOT_FILE="hero_zero_lots.csv"

@st.cache_data(ttl=1800)
def load_lots():
    try:
        x=pd.read_csv(LOT_FILE); x["SYMBOL"]=x.SYMBOL.astype(str).str.upper().str.strip(); x["LOT_SIZE"]=pd.to_numeric(x.LOT_SIZE,errors="coerce")
        return x.dropna(subset=["LOT_SIZE"]).drop_duplicates("SYMBOL")
    except Exception:return pd.DataFrame(columns=["SYMBOL","LOT_SIZE"])

def nse_get(path):
    try:
        req=Request("https://www.nseindia.com"+path,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json,text/plain,*/*","Referer":"https://www.nseindia.com/option-chain"})
        with urlopen(req,timeout=8) as r:return json.loads(r.read().decode("utf-8"))
    except Exception:return None

@st.cache_data(ttl=60,show_spinner=False)
def nse_chain(sym):
    data=nse_get("/api/option-chain-equities?symbol="+sym)
    if not data:return pd.DataFrame()
    rows=[]
    for z in data.get("records",{}).get("data",[]):
        for typ in ("CE","PE"):
            o=z.get(typ)
            if o:
                rows.append({"SYMBOL":sym,"expiry":datetime.strptime(z["expiryDate"],"%d-%b-%Y").strftime("%Y-%m-%d"),"strike":float(z["strikePrice"]),"TYPE":typ,"lastPrice":o.get("lastPrice"),"bid":o.get("bidprice"),"ask":o.get("askPrice"),"volume":o.get("totalTradedVolume",0),"openInterest":o.get("openInterest",0),"changeinOpenInterest":o.get("changeinOpenInterest",0),"impliedVolatility":o.get("impliedVolatility",np.nan)})
    return pd.DataFrame(rows)

@st.cache_data(ttl=120,show_spinner=False)
def candles(sym):
    try:
        x=yf.Ticker(sym+".NS").history(period="60d",interval="15m",auto_adjust=False)
        x=x.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
        return x.dropna(subset=["open","high","low","close"]) if not x.empty else pd.DataFrame()
    except Exception:return pd.DataFrame()

def tech(d):
    if len(d)<100:return None
    x=d.copy(); x["e9"]=x.close.ewm(span=9,adjust=False).mean();x["e21"]=x.close.ewm(span=21,adjust=False).mean();x["e50"]=x.close.ewm(span=50,adjust=False).mean()
    ch=x.close.diff();g=ch.clip(lower=0).ewm(alpha=1/14,adjust=False).mean();l=(-ch.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean();x["rsi"]=100-100/(1+g/l.replace(0,np.nan))
    tr=pd.concat([x.high-x.low,(x.high-x.close.shift()).abs(),(x.low-x.close.shift()).abs()],axis=1).max(axis=1);x["atr"]=tr.ewm(alpha=1/14,adjust=False).mean()
    up,dn=x.high.diff(),-x.low.diff();pdm=pd.Series(np.where((up>dn)&(up>0),up,0),index=x.index);mdm=pd.Series(np.where((dn>up)&(dn>0),dn,0),index=x.index);pdi=100*pdm.ewm(alpha=1/14,adjust=False).mean()/x.atr.replace(0,np.nan);mdi=100*mdm.ewm(alpha=1/14,adjust=False).mean()/x.atr.replace(0,np.nan);x["adx"]=(100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/14,adjust=False).mean()
    tp=(x.high+x.low+x.close)/3;day=pd.Series(x.index.date,index=x.index);x["vwap"]=(tp*x.volume).groupby(day).cumsum()/x.volume.groupby(day).cumsum().replace(0,np.nan);x["rvol"]=x.volume/x.volume.rolling(20).mean().replace(0,np.nan);x["hh20"]=x.high.rolling(20).max().shift(1);x["ll20"]=x.low.rolling(20).min().shift(1);x["body"]=(x.close-x.open).abs()/(x.high-x.low).replace(0,np.nan)
    x=x.dropna();a,p=x.iloc[-1],x.iloc[-2];bull=bear=0;br=[];sr=[]
    if a.e9>a.e21>a.e50:bull+=18;br.append("EMA alignment")
    if a.e9<a.e21<a.e50:bear+=18;sr.append("EMA alignment")
    if a.close>a.vwap:bull+=12;br.append("VWAP")
    else:bear+=12;sr.append("VWAP")
    if a.adx>=22:bull+=7;bear+=7
    if 52<=a.rsi<=70:bull+=10;br.append("RSI")
    if 30<=a.rsi<=48:bear+=10;sr.append("RSI")
    if a.rvol>=1.25:bull+=8;bear+=8
    if a.close>a.hh20 and a.body>=.55:bull+=15;br.append("breakout")
    if a.close<a.ll20 and a.body>=.55:bear+=15;sr.append("breakdown")
    q=x.iloc[-7:-1]
    if a.low<q.low.min() and a.close>q.low.min():bull+=12;br.append("sell-side sweep")
    if a.high>q.high.max() and a.close<q.high.max():bear+=12;sr.append("buy-side sweep")
    if a.close>p.close:bull+=5
    if a.close<p.close:bear+=5
    side="CE" if bull>bear else "PE"
    return {"side":side,"score":max(bull,bear),"close":float(a.close),"rsi":float(a.rsi),"adx":float(a.adx),"rvol":float(a.rvol),"reasons":"; ".join(br if side=="CE" else sr)}

def candidate(o,t,lot,max_prem,min_oi,min_vol,max_spread,min_chg):
    prem=float(o.lastPrice or np.nan);bid=float(o.bid or np.nan);ask=float(o.ask or np.nan);oi=float(o.openInterest or 0);vol=float(o.volume or 0);coi=float(o.changeinOpenInterest or 0)
    if not np.isfinite(prem) or prem<=0 or prem>max_prem or not np.isfinite(bid) or not np.isfinite(ask) or ask<=0:return None
    spread=(ask-bid)/max(prem,.05)*100
    if spread>max_spread or oi<min_oi or vol<min_vol or coi<min_chg or o.TYPE!=t["side"]:return None
    ex=datetime.strptime(o.expiry,"%Y-%m-%d").date();days=(ex-date.today()).days
    if days!=0:return None
    e=round(prem,2);sl=round(max(.05,e*.70),2);t1=round(e*1.5,2);t2=round(e*2,2);t3=round(e*3,2)
    return {"Signal":"BUY "+o.TYPE,"Symbol":o.SYMBOL,"Expiry":o.expiry,"Strike":o.strike,"Entry":e,"SL":sl,"T1":t1,"T2":t2,"T3":t3,"Lot":lot,"Cost/Lot":round(e*lot,2),"Risk/Lot":round((e-sl)*lot,2),"T1 P/L":round((t1-e)*lot,2),"T2 P/L":round((t2-e)*lot,2),"T3 P/L":round((t3-e)*lot,2),"OI":oi,"Chg OI":coi,"Volume":vol,"IV":o.impliedVolatility,"Spread%":round(spread,1),"Score":t["score"],"RSI":round(t["rsi"],1),"ADX":round(t["adx"],1),"RVOL":round(t["rvol"],2),"Underlying":round(t["close"],2),"Reasons":t["reasons"]}

st.sidebar.header("⚙️ V3 Controls");min_lot=st.sidebar.number_input("Minimum lot size",1,30000,1000,100);max_prem=st.sidebar.number_input("Max premium ₹",.05,1.0,1.0,.05);min_score=st.sidebar.slider("Minimum technical score",50,95,72);min_oi=st.sidebar.number_input("Minimum OI",0,10000000,1000,500);min_vol=st.sidebar.number_input("Minimum option volume",0,10000000,250,100);min_chg=st.sidebar.number_input("Minimum +OI change",0,1000000,0,100);max_spread=st.sidebar.slider("Max spread %",5,60,25);budget=st.sidebar.number_input("Budget ₹",500,1000000,5000,500)
if st.sidebar.button("🔄 Fresh V3 scan"):st.cache_data.clear();st.session_state.pop("v3",None)
slots=load_lots();u=slots[slots.LOT_SIZE>=min_lot].copy();st.info(f"Universe: {len(u)} high-lot stocks • NSE option-chain first • premium ≤ ₹{max_prem:.2f} • expiry-day only")
if "v3" not in st.session_state:
    rows=[];bar=st.progress(0)
    for i,(_,r) in enumerate(u.iterrows(),1):
        try:
            t=tech(candles(r.SYMBOL))
            if not t or t["score"]<min_score:bar.progress(i/len(u));continue
            c=nse_chain(r.SYMBOL)
            if c.empty:bar.progress(i/len(u));continue
            ex=min(c.expiry,key=lambda x:datetime.strptime(x,"%Y-%m-%d").date());c=c[c.expiry==ex];s=t["close"]
            for _,o in c.iterrows():
                otm=((o.strike-s)/s*100) if o.TYPE=="CE" else ((s-o.strike)/s*100)
                if -1<=otm<=3:
                    z=candidate(o,t,int(r.LOT_SIZE),max_prem,min_oi,min_vol,max_spread,min_chg)
                    if z:z["OTM%"]=round(otm,2);rows.append(z)
        except Exception:pass
        bar.progress(i/len(u))
    bar.empty();st.session_state.v3=pd.DataFrame(rows)
df=st.session_state.v3.copy()
if df.empty:st.warning("WAIT — no contract passed every V3 filter. Do not force a trade.");st.stop()
df["Rank"]=df.Score+np.minimum(df.RVOL,3)*4+np.minimum(np.log1p(df.OI)/10,5)+np.sign(df["Chg OI"])*3;df=df.sort_values(["Rank","Volume","OI"],ascending=False).reset_index(drop=True)
a,b,c,d=st.columns(4);a.metric("Qualified",len(df));b.metric("Stocks",df.Symbol.nunique());c.metric("BUY CE",sum(df.Signal=="BUY CE"));d.metric("BUY PE",sum(df.Signal=="BUY PE"))
cols=["Signal","Symbol","Expiry","Strike","Entry","SL","T1","T2","T3","Lot","Cost/Lot","Risk/Lot","T1 P/L","T2 P/L","T3 P/L","OI","Chg OI","Volume","IV","Spread%","Score","RSI","ADX","RVOL","Underlying","OTM%","Reasons"];st.subheader("🎯 V3 Trade Candidates");st.dataframe(df[cols].head(50),use_container_width=True,hide_index=True)
ce,pe=st.columns(2)
with ce:st.subheader("🟢 BUY CE");st.dataframe(df[df.Signal=="BUY CE"].head(10)[cols],use_container_width=True,hide_index=True)
with pe:st.subheader("🔴 BUY PE");st.dataframe(df[df.Signal=="BUY PE"].head(10)[cols],use_container_width=True,hide_index=True)
st.subheader("💰 Position calculator");i=st.selectbox("Candidate",df.index,format_func=lambda i:f'{df.loc[i,"Signal"]} {df.loc[i,"Symbol"]} {df.loc[i,"Strike"]} @ ₹{df.loc[i,"Entry"]:.2f}');r=df.loc[i];cost=r.Entry*r.Lot;st.write(f"1 lot cost: ₹{cost:,.2f} • max lots by ₹{budget:,.0f}: {int(budget//cost) if cost else 0} • risk/lot: ₹{r['Risk/Lot']:,.2f}")
st.download_button("⬇️ Download V3 CSV",df.to_csv(index=False).encode(),"hero_zero_v3_scan.csv","text/csv");st.caption("NSE-first research scanner. Verify live contract data with your broker before ordering; no guaranteed-profit claim.")
