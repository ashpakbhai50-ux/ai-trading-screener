import numpy as np
import pandas as pd

def _rsi(close, period=14):
    d=close.diff()
    gain=d.clip(lower=0).ewm(alpha=1/period,adjust=False).mean()
    loss=(-d.clip(upper=0)).ewm(alpha=1/period,adjust=False).mean()
    rs=gain/loss.replace(0,np.nan)
    return 100-(100/(1+rs))

def _adx(df,n=14):
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
    x["ATR14"]=tr.rolling(14).mean(); x["ATR_PCT"]=x.ATR14/c*100; x["ADX"]=_adx(x)
    x["AvgVol20"]=x.Volume.rolling(20).mean(); x["RVOL"]=x.Volume/x.AvgVol20.replace(0,np.nan)
    x["High20"]=x.High.rolling(20).max().shift(1); x["Low20"]=x.Low.rolling(20).min().shift(1)
    x["AvgValue20"]=(x.Close*x.Volume).rolling(20).mean()
    x["VWAP20"]=(x.Close*x.Volume).rolling(20).sum()/x.Volume.rolling(20).sum().replace(0,np.nan)
    x["RangePct"]=(x.High-x.Low)/x.Close.replace(0,np.nan)*100
    return x

def analyze_stock(df, capital=25000, risk_pct=0.75, market_bias="NEUTRAL", max_price=100):
    if df is None or len(df)<210: return None
    x=add_indicators(df).dropna().copy()
    if x.empty: return None
    r=x.iloc[-1]; p=float(r.Close)
    if p>max_price: return None
    atr=max(float(r.ATR14),p*0.004)
    reasons=[]; score=0
    def add(cond,pts,reason):
        nonlocal score
        if bool(cond): score+=pts; reasons.append(reason)
    add(p>r.SMA20,6,"Price>SMA20"); add(p>r.SMA50,7,"Price>SMA50"); add(p>r.SMA200,7,"Price>SMA200")
    add(r.SMA20>r.SMA50,6,"20DMA>50DMA"); add(r.SMA50>r.SMA200,6,"50DMA>200DMA")
    add(p>r.VWAP20,4,"Price>VWAP20"); add(48<=r.RSI<=70,6,"RSI healthy")
    add(r.MACD>r.MACDSignal,5,"MACD bullish"); add(r.ADX>=18,4,"ADX trend")
    add(1.0<=r.RVOL<=3.0,6,"RVOL healthy"); add(r.RVOL>1.3,4,"Volume confirmation")
    breakout=p>r.High20; near=p>=r.High20*.97
    add(breakout,10,"20D breakout"); add((not breakout) and near,5,"Near breakout")
    add(float(r.ATR_PCT)<=6,5,"ATR controlled")
    avg_value=float(r.AvgValue20)
    liquidity_ok=avg_value>=3_000_000
    add(liquidity_ok,7,"Liquidity passed")
    # Low-loss filter: reject extreme daily ranges, abnormal volume spikes and weak liquidity.
    risk_flag=0
    if float(r.ATR_PCT)>5: risk_flag+=20
    if float(r.RangePct)>9: risk_flag+=20
    if float(r.RVOL)>4: risk_flag+=20
    if not liquidity_ok: risk_flag+=30
    if market_bias=="RISK-OFF": risk_flag+=10
    risk_flag=min(100,risk_flag)
    if risk_flag>=50: score=max(0,score-15)

    weekly=df.resample("W").agg({"Close":"last"}).dropna()
    weekly_ok=True
    if len(weekly)>=30:
        w20=weekly.Close.rolling(20).mean().iloc[-1]
        weekly_ok=float(weekly.Close.iloc[-1])>=float(w20)*.985
        if weekly_ok: score+=5; reasons.append("Weekly trend confirmed")
        else: reasons.append("Weekly trend weak")

    if score>=75 and liquidity_ok and weekly_ok and risk_flag<50: stage="ENTRY"
    elif score>=62 and liquidity_ok and risk_flag<50: stage="CONFIRMATION"
    elif score>=52 and liquidity_ok: stage="WATCH"
    else: stage="NO SETUP"
    signal="BUY WATCH" if stage in ("ENTRY","CONFIRMATION") else ("WATCH" if stage=="WATCH" else "WAIT")

    # Stop distance is volatility-aware rather than artificially tiny. Monetary risk is kept small by sizing.
    sl=max(p-1.35*atr,0.01)
    risk_per_share=p-sl
    risk_budget=min(capital*risk_pct/100, capital*0.0075)
    qty_risk=int(risk_budget/risk_per_share) if risk_per_share>0 else 0
    qty_cap=int((capital*0.98)/p) if p>0 else 0
    qty=max(0,min(qty_risk,qty_cap))
    t1=p+2*risk_per_share; t2=p+3*risk_per_share; t3=p+4*risk_per_share
    confidence=int(min(95,max(30,score+(5 if weekly_ok else -8)-risk_flag*.2)))
    return {
      "Price":p,"Score":int(min(100,score)),"Signal":signal,"Stage":stage,"Confidence":confidence,
      "RSI":float(r.RSI),"RVOL":float(r.RVOL),"ADX":float(r.ADX),"ATR":atr,"ATR_PCT":float(r.ATR_PCT),
      "VWAP20":float(r.VWAP20),"SMA20":float(r.SMA20),"SMA50":float(r.SMA50),"SMA200":float(r.SMA200),
      "WeeklyOK":weekly_ok,"MarketBias":market_bias,"RiskFlag":int(risk_flag),"LiquidityOK":liquidity_ok,
      "Entry":p,"SL":sl,"T1":t1,"T2":t2,"T3":t3,"RR_T1":2.0,"RR_T2":3.0,"RR_T3":4.0,
      "Quantity":qty,"CapitalUsed":round(qty*p,2),"RiskRs":round(qty*risk_per_share,2),
      "ProfitT1Rs":round(qty*(t1-p),2),"ProfitT2Rs":round(qty*(t2-p),2),"ProfitT3Rs":round(qty*(t3-p),2),
      "ExpectedHold":"5-30 trading days","Invalidation":f"Daily close below ₹{sl:.2f} or failed breakout",
      "Reasons":", ".join(reasons)
    }
