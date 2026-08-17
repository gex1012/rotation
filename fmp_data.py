# -*- coding: utf-8 -*-
"""
Data layer -- pull daily EOD prices from Financial Modeling Prep (stable API)
and cache each ticker to a local CSV so re-runs don't re-hit the network.

Endpoint used (the legacy /api/v3/ path is 403 on this API key's plan):
    https://financialmodelingprep.com/stable/historical-price-eod/full?symbol=SPY&apikey=...

Returns adjusted-ish close ('close' from FMP already reflects splits; FMP's
'adjClose' is on a different endpoint, so we use 'close' consistently across
every ticker -- fine for relative-strength work where only ratios matter).
"""
import os
import time
import datetime
import requests
import pandas as pd

def _load_api_key():
    """Key resolution (never hard-code the key in committed source):
       1. env FMP_API_KEY   2. local gitignored file .fmp_api_key"""
    k = os.environ.get("FMP_API_KEY")
    if k:
        return k.strip()
    path = os.path.join(os.path.dirname(__file__), ".fmp_api_key")
    if os.path.exists(path):
        return open(path, encoding="utf-8").read().strip()
    raise RuntimeError("FMP API key not found: set env FMP_API_KEY or create .fmp_api_key")


API_KEY = _load_api_key()
BASE = "https://financialmodelingprep.com/stable/historical-price-eod/full"
HISTORY_FROM = "2017-01-01"   # fetch back to 2017 so warm-up completes before 2018 (in-sample split)
CACHE_DIR = os.path.join(os.path.dirname(__file__), "data_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# --- Universe ---------------------------------------------------------------
# Granular industry/theme universe (37 ETFs). The 11 broad GICS sectors that
# have liquid sub-industry ETFs are BROKEN DOWN into their children (esp. tech),
# so a top-5 pick is genuinely selective (~13% of the field) instead of ~half.
# Broad sectors with no clean sub-split (staples/utilities/real estate/comm)
# are kept whole as defensive anchors.
SECTORS = {
    # --- 科技/成长 (拆分自 XLK) ---
    "SMH":  "半导体",
    "IGV":  "软件",
    "CIBR": "网络安全",
    "SKYY": "云计算",
    "FDN":  "互联网",
    "FINX": "金融科技",
    "IPAY": "支付科技",
    "AIQ":  "人工智能",
    "BOTZ": "机器人",
    "ARKK": "创新科技",
    # --- 通信 ---
    "XLC":  "通信服务",
    # --- 医疗 (拆分自 XLV) ---
    "XBI":  "生物科技",
    "IHI":  "医疗器械",
    "PPH":  "制药",
    "IHF":  "医疗服务",
    # --- 金融 (拆分自 XLF) ---
    "KRE":  "区域银行",
    "KBE":  "银行",
    "IAI":  "券商",
    "KIE":  "保险",
    # --- 能源 (拆分自 XLE) ---
    "XOP":  "油气勘探",
    "OIH":  "油服设备",
    # --- 材料/金属 (拆分自 XLB) ---
    "GDX":  "黄金矿业",
    "COPX": "铜矿",
    "LIT":  "锂电池",
    "URA":  "铀矿核能",
    "XME":  "金属矿业",
    "MOO":  "农业",
    # --- 工业 (拆分自 XLI) ---
    "ITA":  "航空国防",
    "JETS": "航空公司",
    "PAVE": "基建",
    "IYT":  "运输物流",
    # --- 可选消费 (拆分自 XLY) ---
    "XRT":  "零售",
    "XHB":  "住宅建筑",
    # --- 清洁能源 ---
    "TAN":  "太阳能",
    # --- 防御锚 (broad, un-split) ---
    "XLP":  "必需消费",
    "XLU":  "公用事业",
    "XLRE": "房地产",
}
BENCHMARKS = {"SPY": "标普500", "QQQ": "纳斯达克100"}


def _cache_path(symbol: str) -> str:
    return os.path.join(CACHE_DIR, f"{symbol}.csv")


def fetch_symbol(symbol: str, max_age_hours: float = 12.0) -> pd.DataFrame:
    """Return a date-indexed [open, close] DataFrame for one symbol, using the
    on-disk cache when it is fresh enough. Open is needed for T+1-open execution."""
    path = _cache_path(symbol)
    if os.path.exists(path):
        age_h = (time.time() - os.path.getmtime(path)) / 3600.0
        cached = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
        if age_h < max_age_hours and "open" in cached.columns:
            return cached[["open", "close"]]

    r = requests.get(BASE, params={"symbol": symbol, "from": HISTORY_FROM, "apikey": API_KEY},
                     timeout=60)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"FMP returned no rows for {symbol}: {str(data)[:200]}")
    df = pd.DataFrame(data)[["date", "open", "close"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates("date")
    df.to_csv(path, index=False)
    return df.set_index("date")[["open", "close"]]


def load_prices(symbols, max_age_hours: float = 12.0, field: str = "close") -> pd.DataFrame:
    """Wide price frame (index=date, columns=symbols) for the chosen OHLC field
    ('close' or 'open'), forward-filled up to 3 sessions."""
    cols = {}
    for sym in symbols:
        try:
            cols[sym] = fetch_symbol(sym, max_age_hours=max_age_hours)[field]
        except Exception as e:  # keep going; a single dead ticker shouldn't kill the run
            print(f"[warn] {sym}: {e}")
    df = pd.DataFrame(cols).sort_index()
    df = df.ffill(limit=3)
    return df


def all_symbols():
    return list(SECTORS.keys()) + list(BENCHMARKS.keys())


if __name__ == "__main__":
    px = load_prices(all_symbols(), max_age_hours=0)  # force refresh
    print("shape:", px.shape)
    print("date range:", px.index.min().date(), "->", px.index.max().date())
    print("last row:\n", px.tail(1).T)
