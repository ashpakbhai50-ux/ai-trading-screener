import pandas as pd
import numpy as np


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def adx(df, n=14):
    h, l, c = df.High, df.Low, df.Close
    up = h.diff(); down = -l.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/n, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1/n, adjust=False).mean() / atr.replace(0,np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1/n, adjust=False).mean() / atr.replace(0,np.nan)
    dx = 100 * (plus_di-minus_di).abs() / (plus_di+minus_di).replace(0,np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean()


def market_regime(index_df):
    if index_df is None or len(index_df) < 210:
        return {"Regime":"UNKNOWN", "Score":0, "ADX":np.nan, "Reason":"Insufficient index history"}
    x=index_df.copy(); c=x.Close
    s20=c.rolling(20).mean(); s50=c.rolling(50).mean(); s200=c.rolling(200).mean(); a=adx(x)
    p=float(c.iloc[-1]); ad=float(a.iloc[-1])
    score=0
    if p>s20.iloc[-1]: score+=1
    if p>s50.iloc[-1]: score+=1
    if p>s200.iloc[-1]: score+=2
    if s20.iloc[-1]>s50.iloc[-1]: score+=1
    if ad>=20: score+=1
    regime="RISK-ON" if score>=5 else ("NEUTRAL" if score>=3 else "RISK-OFF")
    return {"Regime":regime,"Score":score,"ADX":ad,"Reason":f"Price vs 20/50/200 DMA + ADX {ad:.1f}"}
