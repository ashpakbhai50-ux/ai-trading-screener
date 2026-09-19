# Broad-sector universe. The scanner dynamically removes stocks trading above the user's price cap.
# Symbols are NSE tickers; Yahoo Finance is used for market data.
SECTOR_UNIVERSE = {
    "Banks & Financials": ["IDFCFIRSTB","UCOBANK","IOB","CENTRALBK","BANKINDIA","YESBANK","CANBK","PNB","UNIONBANK","HUDCO","IRFC"],
    "IT & Technology": ["IDEA","HFCL","HCLTECH","WIPRO","IRCON","BSNL"], 
    "Power & Utilities": ["SUZLON","NHPC","SJVN","RPOWER","NTPC","POWERGRID","JPPOWER","IREDA"],
    "Oil, Gas & Energy": ["IOC","ONGC","GAIL","OIL","MRPL","HINDPETRO"],
    "Metals & Mining": ["SAIL","NMDC","HINDALCO","TATASTEEL","JINDALSTEL","NATIONALUM","VEDL"],
    "Pharma & Healthcare": ["MOREPENLAB","JBCHEPHARM","JPHEALTH","RANBAXY","MARKSANS","GRANULES"],
    "Automobiles & Components": ["TATAMOTORS","ASHOKLEY","MOTHERSON","JAMNAAUTO","GREAVES","SMLISUZU"],
    "Industrials & Engineering": ["IRB","NBCC","RVNL","IRCON","HUDCO","BHEL","NCC","RITES"],
    "Construction & Infrastructure": ["NBCC","IRB","NCC","HUDCO","RITES","JPPOWER","SUZLON"],
    "Telecom": ["IDEA","HFCL","MTNL"],
    "Consumer & FMCG": ["TRIDENT","ITC","VBL","UJJIVANSFB","JAIPURKURT","BOROSIL"],
    "Chemicals": ["RCF","FACT","GNFC","GSFC","DCMNVL","DEEPAKNTR"],
    "Textiles": ["TRIDENT","WELSPUNLIV","JAIPURKURT","HITECHCORP"],
    "Real Estate": ["IREDA","HUDCO","IRB","NBCC","JPPOWER"],
    "Defence & Aerospace": ["BEL","HAL","BEML","MAZDOCK","IDEAFORGE"],
    "Renewables & Clean Energy": ["SUZLON","IREDA","SJVN","NHPC","RPOWER"],
    "Transport & Logistics": ["IRFC","RVNL","IRCTC","CONCOR","GATI"],
}

QUALITY_SWING = sorted(set(sum(SECTOR_UNIVERSE.values(), [])))
PENNY_STARTER = sorted(set([
    "SUZLON","YESBANK","IDEA","JPPOWER","RPOWER","IRFC","NHPC","SJVN",
    "UCOBANK","TRIDENT","IDFCFIRSTB","IOB","CENTRALBK","IRB","NBCC",
    "HFCL","SAIL","IOC","BANKINDIA","HUDCO","RVNL","RITES","NCC","BHEL"
]))
ALL_STARTER = QUALITY_SWING

def sector_for(symbol):
    return next((s for s, symbols in SECTOR_UNIVERSE.items() if symbol in symbols), "Other")
