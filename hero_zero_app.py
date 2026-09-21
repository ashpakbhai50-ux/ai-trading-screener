# HERO ZERO V5
# Live auto-refresh + BUY/WAIT confirmation + Telegram alerts.
# NSE-first stock-options research scanner. No guaranteed-profit claim.

import os, time, math, json
from datetime import datetime, date
from urllib.request import Request, urlopen
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Hero Zero V5", page_icon="🎯", layout="wide")
st.title("🎯 HERO ZERO V5 — LIVE Expiry Stock Options Scanner")
st.caption("NSE stock options • premium ≤ ₹1 • high-lot focus • live refresh • BUY/WAIT • Telegram alerts")

LOT_FILE = "hero_zero_lots.csv"

def nse_get(path):
    try:
        req=Request("https://www.nseindia.com"+path,headers={
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
            "Accept":"application/json,text/plain,*/*",
            "Referer":"https://www.nseindia.com/option-chain",
            "Accept-Language":"en-US,en;q=0.9"})
        with urlopen(req,timeout=8) as r:return json.loads(r.read().decode("utf-8"))
    except Exception:return None

@st.cache_data(ttl=1800)
def load_lots():
    try:
        x=pd.read_csv(LOT_FILE);x["SYMBOL"]=x.SYMBOL.astype(str).str.upper().str.strip();x["LOT_SIZE"]=pd.to_numeric(x.LOT_SIZE,errors="coerce")
        return x.dropna(subset=["LOT_SIZE"]).drop_duplicates("SYMBOL")
    except Exception:return pd.DataFrame(columns=["SYMBOL","LOT_SIZE"])

@st.cache_data(ttl=35,show_spinner=False)
def nse_chain(sym):
    d=nse_get("/api/option-chain-equities?symbol="+sym)
    if not d:return pd.DataFrame()
    rows=[]
    for z in d.get("records",{}).get("data",[]):
        for typ in ("CE","PE"):
            o=z.get(typ)
            if o:
                rows.append({"SYMBOL":sym,"expiry":datetime.strptime(z["expiryDate"],"%d-%b-%Y").strftime("%Y-%m-%d"),
                             "strike":float(z["strikePrice"]),"TYPE":typ,"lastPrice":o.get("lastPrice"),"bid":o.get("bidprice"),
                             "ask":o.get("askPrice"),"volume":o.get("totalTradedVolume",0),"openInterest":o.get("openInterest",0),
                             "changeinOpenInterest":o.get("changeinOpenInterest",0),"impliedVolatility":o.get("impliedVolatility",np.nan)})
    return pd.DataFrame(rows)

@st.cache_data(ttl=90,show_spinner=False)
def candles(sym):
    try:
        x=yf.Ticker(sym+".NS").history(period="60d",interval="15m",auto_adjust=False)
        x=x.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
        return x.dropna(subset=["open","high","low","close"]) if not x.empty else pd.DataFrame()
    except Exception:return pd.DataFrame()

def tech(d):
    if len(d)<120:return None
    x=d.copy()
    x["e9"]=x.close.ewm(span=9,adjust=False).mean();x["e21"]=x.close.ewm(span=21,adjust=False).mean();x["e50"]=x.close.ewm(span=50,adjust=False).mean()
    ch=x.close.diff();g=ch.clip(lower=0).ewm(alpha=1/14,adjust=False).mean();l=(-ch.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    x["rsi"]=100-100/(1+g/l.replace(0,np.nan))
    tr=pd.concat([x.high-x.low,(x.high-x.close.shift()).abs(),(x.low-x.close.shift()).abs()],axis=1).max(axis=1);x["atr"]=tr.ewm(alpha=1/14,adjust=False).mean()
    up,dn=x.high.diff(),-x.low.diff();pdm=pd.Series(np.where((up>dn)&(up>0),up,0),index=x.index);mdm=pd.Series(np.where((dn>up)&(dn>0),dn,0),index=x.index)
    pdi=100*pdm.ewm(alpha=1/14,adjust=False).mean()/x.atr.replace(0,np.nan);mdi=100*mdm.ewm(alpha=1/14,adjust=False).mean()/x.atr.replace(0,np.nan)
    x["adx"]=(100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/14,adjust=False).mean()
    tp=(x.high+x.low+x.close)/3;day=pd.Series(x.index.date,index=x.index);x["vwap"]=(tp*x.volume).groupby(day).cumsum()/x.volume.groupby(day).cumsum().replace(0,np.nan)
    x["rvol"]=x.volume/x.volume.rolling(20).mean().replace(0,np.nan);x["hh20"]=x.high.rolling(20).max().shift(1);x["ll20"]=x.low.rolling(20).min().shift(1)
    x["body"]=(x.close-x.open).abs()/(x.high-x.low).replace(0,np.nan);x=x.dropna()
    if len(x)<10:return None
    a,p=x.iloc[-1],x.iloc[-2];bull=bear=0;br=[];sr=[]
    if a.e9>a.e21>a.e50:bull+=14;br.append("EMA")
    if a.e9<a.e21<a.e50:bear+=14;sr.append("EMA")
    if a.close>a.vwap:bull+=10;br.append("VWAP")
    else:bear+=10;sr.append("VWAP")
    if a.adx>=22:bull+=6;bear+=6
    if 52<=a.rsi<=70:bull+=8;br.append("RSI")
    if 30<=a.rsi<=48:bear+=8;sr.append("RSI")
    if a.rvol>=1.25:bull+=8;br.append("RVOL");bear+=8;sr.append("RVOL")
    if a.close>a.hh20 and a.body>=.55:bull+=14;br.append("breakout")
    if a.close<a.ll20 and a.body>=.55:bear+=14;sr.append("breakdown")
    q=x.iloc[-8:-1]
    if a.low<q.low.min() and a.close>q.low.min():bull+=12;br.append("sell-side sweep")
    if a.high>q.high.max() and a.close<q.high.max():bear+=12;sr.append("buy-side sweep")
    if a.close>p.close:bull+=4
    if a.close<p.close:bear+=4
    return {"side":"CE" if bull>bear else "PE","score":max(bull,bear),"close":float(a.close),"rsi":float(a.rsi),"adx":float(a.adx),"rvol":float(a.rvol),"reasons":"; ".join(br if bull>bear else sr)}

def expiries(c,mode):
    ex=sorted(pd.to_datetime(c.expiry).dt.date.unique());today=date.today()
    if mode=="Today only":return [e for e in ex if e==today]
    if mode=="Nearest":return [min(ex,key=lambda e:abs((e-today).days))] if ex else []
    return [e for e in ex if e>=today][:2]

def make_candidate(o,t,lot,max_prem,min_oi,min_vol,min_chg,max_spread,otm_min,otm_max):
    try:prem=float(o.lastPrice);bid=float(o.bid);ask=float(o.ask);oi=float(o.openInterest);vol=float(o.volume);coi=float(o.changeinOpenInterest)
    except Exception:return None
    if not np.isfinite(prem) or not np.isfinite(bid) or not np.isfinite(ask) or prem<=0 or prem>max_prem or bid<=0 or ask<=0:return None
    spread=(ask-bid)/max(prem,.05)*100
    if spread>max_spread or oi<min_oi or vol<min_vol or coi<min_chg or o.TYPE!=t["side"]:return None
    ex=datetime.strptime(o.expiry,"%Y-%m-%d").date()
    if ex<date.today():return None
    s=t["close"];otm=((o.strike-s)/s*100) if o.TYPE=="CE" else ((s-o.strike)/s*100)
    if not otm_min<=otm<=otm_max:return None
    oi_pct=coi/max(oi-coi,1)*100;vol_oi=vol/max(oi,1);iv=float(o.impliedVolatility) if pd.notna(o.impliedVolatility) else np.nan
    liquidity=max(0,10-min(spread/3,10));oi_score=max(0,min(12,6+oi_pct/5));vol_score=max(0,min(8,vol_oi*8));otm_score=max(0,10-abs(otm-1)*4)
    days=(ex-date.today()).days;expiry_score=10 if days==0 else 7 if days<=2 else 3
    total=min(t["score"],55)+liquidity+oi_score+vol_score+otm_score+expiry_score
    e=round(prem,2);sl=round(max(.05,e*.65),2);t1=round(e*1.5,2);t2=round(e*2,2);t3=round(e*3,2)
    return {"Signal":"BUY "+o.TYPE,"Symbol":o.SYMBOL,"Expiry":o.expiry,"Days":days,"Strike":o.strike,"Entry":e,"SL":sl,"T1":t1,"T2":t2,"T3":t3,"Lot":lot,
            "Cost/Lot":round(e*lot,2),"Risk/Lot":round((e-sl)*lot,2),"OI":oi,"Chg OI":coi,"Chg OI %":round(oi_pct,1),"Volume":vol,"Vol/OI":round(vol_oi,2),
            "IV":round(iv,2) if np.isfinite(iv) else np.nan,"Spread%":round(spread,1),"Score":round(total,1),"Tech":t["score"],"RSI":round(t["rsi"],1),
            "ADX":round(t["adx"],1),"RVOL":round(t["rvol"],2),"Underlying":round(s,2),"OTM%":round(otm,2),"Reasons":t["reasons"]}

def scan(universe,mode,settings):
    rows=[];bar=st.progress(0)
    for i,(_,r) in enumerate(universe.iterrows(),1):
        try:
            t=tech(candles(r.SYMBOL))
            if not t or t["score"]<settings["tech_min"]:bar.progress(i/len(universe));continue
            c=nse_chain(r.SYMBOL)
            if not c.empty:
                for ex in expiries(c,mode):
                    for _,o in c[c.expiry==ex.strftime("%Y-%m-%d")].iterrows():
                        z=make_candidate(o,t,int(r.LOT_SIZE),**settings["filters"])
                        if z:rows.append(z)
        except Exception:pass
        bar.progress(i/len(universe))
    bar.empty()
    if not rows:return pd.DataFrame()
    d=pd.DataFrame(rows).sort_values(["Score","Chg OI %","Volume"],ascending=False).reset_index(drop=True)
    return d.drop_duplicates(["Symbol","Signal"]).head(3)

def confirmation(df,threshold):
    if df.empty:return "WAIT"
    top=float(df.iloc[0]["Score"])
    return "BUY" if top>=threshold else "WAIT"

def telegram_send(message):
    token=os.getenv("TELEGRAM_BOT_TOKEN","");chat=os.getenv("TELEGRAM_CHAT_ID","")
    if not token or not chat:return False,"Telegram secrets missing"
    try:
        payload=json.dumps({"chat_id":chat,"text":message}).encode()
        req=Request("https://api.telegram.org/bot"+token+"/sendMessage",data=payload,headers={"Content-Type":"application/json"})
        with urlopen(req,timeout=8) as r:return bool(json.loads(r.read().decode()).get("ok")), "sent"
    except Exception as e:return False,str(e)

st.sidebar.header("⚙️ V5 Live Controls")
min_lot=st.sidebar.number_input("Minimum lot size",1,30000,1000,100)
max_prem=st.sidebar.number_input("Max premium ₹",.05,1.0,1.0,.05)
buy_threshold=st.sidebar.slider("BUY confirmation score",60,95,72)
tech_min=st.sidebar.slider("Minimum technical score",40,55,45)
min_oi=st.sidebar.number_input("Minimum OI",0,10000000,1000,500)
min_vol=st.sidebar.number_input("Minimum option volume",0,10000000,250,100)
min_chg=st.sidebar.number_input("Minimum +OI change",0,1000000,0,100)
max_spread=st.sidebar.slider("Max spread %",5,60,25)
otm_min=st.sidebar.slider("OTM minimum %",-5.0,5.0,-1.0,.5);otm_max=st.sidebar.slider("OTM maximum %",1.0,10.0,3.0,.5)
expiry_mode=st.sidebar.selectbox("Expiry mode",["Today only","Nearest","Next 2 expiries"])
budget=st.sidebar.number_input("Budget ₹",500,1000000,5000,500)
auto=st.sidebar.toggle("🔴 LIVE auto-refresh",value=False)
refresh=st.sidebar.slider("Refresh seconds",30,300,60,10)
telegram=st.sidebar.toggle("📲 Telegram alerts",value=False)
alert_wait=st.sidebar.toggle("Alert only on BUY",value=True)
if st.sidebar.button("🔄 Scan NOW"):st.session_state.pop("v5",None)

lots=load_lots();u=lots[lots.LOT_SIZE>=min_lot].copy()
settings={"tech_min":tech_min,"filters":{"max_prem":max_prem,"min_oi":min_oi,"min_vol":min_vol,"min_chg":min_chg,"max_spread":max_spread,"otm_min":otm_min,"otm_max":otm_max}}
st.info(f"Live universe: {len(u)} high-lot stocks • premium ≤ ₹{max_prem:.2f} • {expiry_mode} • NSE option-chain first")

if "v5" not in st.session_state:
    st.session_state.v5=scan(u,expiry_mode,settings)
df=st.session_state.v5
status=confirmation(df,buy_threshold)

if auto:
    st.markdown(f"**LIVE:** refresh every {refresh}s • last scan: {datetime.now().strftime('%H:%M:%S')}")
    time.sleep(refresh)
    st.session_state.pop("v5",None)
    st.rerun()

c1,c2,c3=st.columns(3)
c1.metric("CONFIRMATION",status)
c2.metric("TOP SETUPS",len(df))
c3.metric("LAST UPDATE",datetime.now().strftime("%H:%M:%S"))

if status=="BUY":
    st.success("🟢 BUY confirmation: top setup crossed your score threshold. Verify the live premium, spread and broker contract before ordering.")
else:
    st.warning("🟡 WAIT: no setup currently meets the BUY confirmation threshold. Do not force a trade.")

if df.empty:
    st.stop()

st.subheader("🏆 TOP 1–3 LIVE SETUPS")
for n,(_,r) in enumerate(df.head(3).iterrows(),1):
    with st.container(border=True):
        cols=st.columns(10)
        vals=[f"#{n} {r.Signal}",r.Symbol,str(r.Strike),f"₹{r.Entry:.2f}",f"₹{r.SL:.2f}",f"₹{r.T1:.2f}",f"₹{r.T2:.2f}",f"₹{r.T3:.2f}",f"{r.Score:.0f}/100",f"{r.Days}d"]
        labels=["SIGNAL","SYMBOL","STRIKE","ENTRY","SL","T1","T2","T3","SCORE","EXPIRY"]
        for box,label,val in zip(cols,labels,vals):box.metric(label,val)
        st.caption(f"OI {r.OI:,.0f} • +OI {r['Chg OI']:,.0f} ({r['Chg OI %']:.1f}%) • Vol {r.Volume:,.0f} • Spread {r['Spread%']:.1f}% • RVOL {r.RVOL:.2f} • Reasons: {r.Reasons}")

st.subheader("📋 TOP 3 TABLE")
show=["Signal","Symbol","Expiry","Days","Strike","Entry","SL","T1","T2","T3","Lot","Cost/Lot","Risk/Lot","OI","Chg OI","Chg OI %","Volume","Vol/OI","IV","Spread%","Score","Tech","RSI","ADX","RVOL","Underlying","OTM%","Reasons"]
st.dataframe(df[show],use_container_width=True,hide_index=True)

st.subheader("💰 Position calculator")
idx=st.selectbox("Candidate",df.index,format_func=lambda i:f'{df.loc[i,"Signal"]} {df.loc[i,"Symbol"]} {df.loc[i,"Strike"]} @ ₹{df.loc[i,"Entry"]:.2f}')
r=df.loc[idx];cost=r.Entry*r.Lot
st.write(f"1 lot cost: ₹{cost:,.2f} • max lots by ₹{budget:,.0f}: {int(budget//cost) if cost else 0} • risk/lot: ₹{r['Risk/Lot']:,.2f}")

if telegram:
    if "tg_last" not in st.session_state:st.session_state.tg_last=""
    if not (alert_wait and status!="BUY"):
        if not df.empty:
            r=df.iloc[0];msg=(f"🎯 HERO ZERO V5\n{status} | {r.Signal}\n{r.Symbol} {r.Strike}\nEntry ₹{r.Entry:.2f} | SL ₹{r.SL:.2f}\nT1 ₹{r.T1:.2f} | T2 ₹{r.T2:.2f} | T3 ₹{r.T3:.2f}\nScore {r.Score:.0f}/100 | OI {r.OI:.0f} | +OI {r['Chg OI']:.0f} | Vol {r.Volume:.0f}')
            key=f'{status}|{r.Symbol}|{r.Strike}|{r.Entry}'
            if key!=st.session_state.tg_last:
                ok,info=telegram_send(msg)
                st.session_state.tg_last=key if ok else st.session_state.tg_last
                st.caption("Telegram: "+("alert sent" if ok else info))
    else: st.caption("Telegram alert is set to BUY-only; current status is WAIT.")

st.download_button("⬇️ Download TOP 3 CSV",df.to_csv(index=False).encode(),"hero_zero_v5_top3.csv","text/csv")
st.caption("Research scanner only. Verify live NSE/broker contract, lot size, liquidity and execution before trading. Sub-₹1 expiry options can move/decay very quickly. No guaranteed-profit claim.")
