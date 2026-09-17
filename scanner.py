import numpy as np
import pandas as pd


def _rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _adx(df, n=14):
    h,l,c=df.High,df.Low,df.Close
    up=h.diff(); down=-l.diff()
    plus=up.where((up>down)&(up>0),0.0); minus=down.where((down>up)&(down>0),0.0)
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr=tr.ewm(alpha=1/n,adjust=False).mean()
    pdi=100*plus.ewm(alpha=1/n,adjust=False).mean()/atr.replace(0,np.nan)
    mdi=100*minus.ewm(alpha=1/n,adjust=False).mean()/atr.replace(0,np.nan)
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    return dx.ewm(alpha=1/n,adjust=False).mean()


def add_indicators(df):
    x=df.copy(); c=x.Close
    x["SMA20"]=c.rolling(20).mean(); x["SMA50"]=c.rolling(50).mean(); x["SMA200"]=c.rolling(200).mean()
    x["EMA20"]=c.ewm(span=20,adjust=False).mean(); x["EMA50"]=c.ewm(span=50,adjust=False).mean()
    x["RSI"]=_rsi(c)
    e12=c.ewm(span=12,adjust=False).mean(); e26=c.ewm(span=26,adjust=False).mean()
    x["MACD"]=e12-e26; x["MACDSignal"]=x.MACD.ewm(span=9,adjust=False).mean()
    tr=pd.concat([x.High-x.Low,(x.High-x.Close.shift()).abs(),(x.Low-x.Close.shift()).abs()],axis=1).max(axis=1)
    x["ATR14"]=tr.rolling(14).mean(); x["ADX"]=_adx(x)
    x["AvgVol20"]=x.Volume.rolling(20).mean(); x["RVOL"]=x.Volume/x.AvgVol20.replace(0,np.nan)
    x["High20"]=x.High.rolling(20).max().shift(1); x["Low20"]=x.Low.rolling(20).min().shift(1)
    x["AvgValue20"]=(x.Close*x.Volume).rolling(20).mean()
    x["VWAP20"]=(x.Close*x.Volume).rolling(20).sum()/x.Volume.rolling(20).sum().replace(0,np.nan)
    x["RangePct"]=(x.High-x.Low)/x.Close.replace(0,np.nan)*100
    return x


def analyze_stock(df, capital=40000, risk_rupees=400, low_price_risk=200, market_bias="NEUTRAL"):
    if df is None or len(df)<210: return None
    x=add_indicators(df).dropna().copy()
    if x.empty: return None
    r=x.iloc[-1]; p=float(r.Close); atr=max(float(r.ATR14),p*.005)
    reasons=[]; score=0
    checks=[]
    def add(cond, pts, reason):
        nonlocal score
        checks.append(bool(cond))
        if cond: score+=pts; reasons.append(reason)
    add(p>r.SMA20,7,"Price>SMA20"); add(p>r.SMA50,8,"Price>SMA50"); add(p>r.SMA200,8,"Price>SMA200")
    add(r.SMA20>r.SMA50,7,"20DMA>50DMA"); add(r.SMA50>r.SMA200,7,"50DMA>200DMA")
    add(p>r.VWAP20,5,"Price>VWAP20"); add(50<=r.RSI<=72,7,"RSI healthy")
    add(r.MACD>r.MACDSignal,6,"MACD bullish"); add(r.ADX>=18,5,"ADX trend")
    add(r.RVOL>=1.5,9,"RVOL>=1.5x")
    breakout=p>r.High20; near=p>=r.High20*.97
    add(breakout,12,"20D breakout"); add((not breakout) and near,5,"Near breakout")
    add(float(r.RangePct)<12,4,"Volatility controlled")
    low_price=p<50; min_value=2_000_000 if low_price else 5_000_000
    avg_value=float(r.AvgValue20); liquidity_ok=avg_value>=min_value
    add(liquidity_ok,5,"Liquidity passed")
    # Penalty checks for potential pump/whipsaw conditions.
    manipulation=0
    if float(r.RVOL)>=4: manipulation+=25
    if float(r.RangePct)>=10: manipulation+=20
    if p<r.SMA20: manipulation+=15
    if not liquidity_ok: manipulation+=30
    if market_bias=="RISK-OFF": manipulation+=10
    manipulation=min(100,manipulation)
    if manipulation>=50: score=max(0,score-12)

    # Multi-timeframe confirmation: weekly trend should not be sharply bearish.
    weekly=df.resample("W").agg({"Close":"last"}).dropna()
    weekly_ok=True
    if len(weekly)>=30:
        w20=weekly.Close.rolling(20).mean().iloc[-1]
        weekly_ok=float(weekly.Close.iloc[-1])>=float(w20)*.98
        if weekly_ok: score+=5; reasons.append("Weekly trend confirmed")
        else: reasons.append("Weekly trend weak")

    confirmations=sum(checks)
    if score>=78 and liquidity_ok and weekly_ok and manipulation<50: stage="ENTRY"
    elif score>=62 and liquidity_ok: stage="CONFIRMATION"
    else: stage="EARLY ALERT" if score>=50 else "NO SETUP"
    signal="BUY WATCH" if stage in ("ENTRY","CONFIRMATION") else ("EARLY WATCH" if stage=="EARLY ALERT" else "AVOID/WAIT")

    sl=max(p-1.5*atr,0.01); risk_per_share=p-sl
    risk_budget=low_price_risk if low_price else risk_rupees
    qty_risk=int(risk_budget/risk_per_share) if risk_per_share>0 else 0
    qty_cap=int(capital/p) if p>0 else 0; qty=max(0,min(qty_risk,qty_cap))
    t1=p+2*risk_per_share; t2=p+3*risk_per_share; t3=p+4*risk_per_share
    confidence=int(min(95,max(30,score+(5 if weekly_ok else -8)-manipulation*.15)))
    invalidation=f"Daily close below ₹{sl:.2f} or breakout failure"
    return {
      "Price":p,"Score":int(min(100,score)),"Signal":signal,"Stage":stage,"Confidence":confidence,
      "RSI":float(r.RSI),"RVOL":float(r.RVOL),"ADX":float(r.ADX),"ATR":atr,"VWAP20":float(r.VWAP20),
      "SMA20":float(r.SMA20),"SMA50":float(r.SMA50),"SMA200":float(r.SMA200),"WeeklyOK":weekly_ok,
      "MarketBias":market_bias,"ManipulationRisk":int(manipulation),"LiquidityOK":liquidity_ok,
      "Entry":p,"SL":sl,"T1":t1,"T2":t2,"T3":t3,"RR_T1":2.0,"RR_T2":3.0,"RR_T3":4.0,
      "Quantity":qty,"RiskRs":round(qty*risk_per_share,2),"ProfitT1Rs":round(qty*(t1-p),2),
      "ProfitT2Rs":round(qty*(t2-p),2),"ProfitT3Rs":round(qty*(t3-p),2),"ExpectedHold":"7-30 trading days",
      "Invalidation":invalidation,"Reasons":", ".join(reasons),"Confirmations":confirmations
    }
