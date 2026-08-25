# -*- coding: utf-8 -*-
"""
Global-Tech universe (US-listed) grouped by sub-sector, benchmarked to QQQ.

Builds, for the panel + backtest:
  * per-stock RRG (RS-Ratio / RS-Momentum / quadrant) vs QQQ
  * per-sub-sector synthetic index (equal-weight rebased) RRG vs QQQ
and dumps tech_rrg.json for the website panel.
"""
import os
import json
import numpy as np
import pandas as pd

import fmp_data as fd
from rrg_model import RRGParams, rrg_series, quad, QUAD_QUADRANT

BENCH = "SOXX"   # 与回测一致 (半导体基准); 面板 RRG 也相对 SOXX
PARAMS = RRGParams(126, 8, 2.2, 3)
OUT = os.path.join(os.path.dirname(__file__), "output")

# sub-sector -> {ticker: cn_name}  (US-listed only; foreign lines from the panel dropped)
TECH = {
    "存储": {"MU": "美光", "SNDK": "SanDisk", "STX": "希捷", "WDC": "西部数据",
             "NTAP": "NetApp", "PSTG": "Pure Storage"},
    "芯片-GPU/加速": {"NVDA": "英伟达", "AMD": "AMD", "AVGO": "博通", "MRVL": "迈威尔"},
    "芯片-代工/IDM": {"TSM": "台积电ADR", "INTC": "英特尔", "STM": "意法半导体", "ON": "安森美"},
    "芯片-模拟/MCU": {"TXN": "德州仪器", "ADI": "亚德诺", "MPWR": "MPS", "NXPI": "恩智浦",
                    "MCHP": "微芯", "QCOM": "高通", "ARM": "ARM"},
    "半导体设备": {"AMAT": "应用材料", "LRCX": "拉姆研究", "ASML": "阿斯麦ADR", "KLAC": "科磊",
               "ONTO": "Onto", "CAMT": "Camtek", "NVMI": "Nova", "TER": "泰瑞达",
               "FORM": "FormFactor", "AEHR": "Aehr"},
    "半导体材料/封装": {"AMKR": "安靠", "ASX": "日月光ADR", "ENTG": "英特格", "MKSI": "MKS",
                  "TTMI": "TTM", "VSH": "Vishay"},
    "EDA/IP": {"CDNS": "Cadence", "SNPS": "新思", "AXTI": "AXT"},
    "AI网络/互连": {"ANET": "Arista", "CIEN": "Ciena", "CSCO": "思科", "ALAB": "Astera",
               "CRDO": "Credo", "MTSI": "MACOM", "TEL": "泰科电子", "APH": "安费诺"},
    "光模块/光通信": {"LITE": "Lumentum", "COHR": "Coherent", "FN": "Fabrinet", "AAOI": "AOI",
                 "GLW": "康宁", "POET": "POET", "LWLG": "Lightwave"},
    "AI服务器/硬件": {"DELL": "戴尔", "HPE": "慧与", "CLS": "Celestica", "JBL": "Jabil",
                 "SMCI": "超微", "GFS": "格芯", "TSEM": "高塔", "SOI": "Soitec"},
    "数据中心电力": {"VRT": "维谛", "ETN": "伊顿", "NVT": "nVent", "MOD": "Modine"},
    "电力/核电": {"GEV": "GE Vernova", "BE": "Bloom", "PWR": "Quanta", "VST": "Vistra",
              "CEG": "Constellation", "OKLO": "Oklo", "SMR": "NuScale", "CCJ": "Cameco", "LEU": "Centrus"},
    "Hyperscaler": {"MSFT": "微软", "GOOGL": "谷歌", "AMZN": "亚马逊", "META": "Meta",
                    "ORCL": "甲骨文", "IBM": "IBM"},
    "Neocloud": {"NBIS": "Nebius", "CRWV": "CoreWeave", "IREN": "IREN", "APLD": "Applied Digital"},
    "网络安全": {"PANW": "Palo Alto", "CRWD": "CrowdStrike", "FTNT": "Fortinet", "ZS": "Zscaler",
             "RBRK": "Rubrik"},
    "软件基础设施": {"DDOG": "Datadog", "SNOW": "Snowflake", "NET": "Cloudflare", "MDB": "MongoDB",
                "GTLB": "GitLab", "AKAM": "Akamai"},
    "企业/AI软件": {"PLTR": "Palantir", "NOW": "ServiceNow", "CRM": "Salesforce", "ADBE": "Adobe",
               "INTU": "Intuit", "WDAY": "Workday", "TEAM": "Atlassian", "TOST": "Toast",
               "APP": "AppLovin", "TEM": "Tempus"},
    "平台/互联网": {"AAPL": "苹果", "NFLX": "奈飞", "SHOP": "Shopify", "UBER": "优步",
               "RDDT": "Reddit", "SPOT": "Spotify"},
    "加密金融": {"COIN": "Coinbase", "MSTR": "Strategy", "HOOD": "Robinhood", "CORZ": "Core Sci"},
    "前沿-自驾/机器人": {"TSLA": "特斯拉", "AUR": "Aurora", "SYM": "Symbotic", "SERV": "Serve"},
    "前沿-量子/航天": {"IONQ": "IonQ", "QBTS": "D-Wave", "RGTI": "Rigetti", "QUBT": "Quantum Corp",
                 "RKLB": "Rocket Lab", "ASTS": "AST", "AVAV": "AeroVironment", "KTOS": "Kratos"},
}


def all_tickers():
    return sorted({t for grp in TECH.values() for t in grp})


def ticker_meta():
    m = {}
    for sub, grp in TECH.items():
        for t, nm in grp.items():
            m[t] = {"sub": sub, "name": nm}
    return m


def load(px_field="close", max_age_hours=12):
    return fd.load_prices(all_tickers() + [BENCH], max_age_hours=max_age_hours, field=px_field)


def synthetic_subsector(px, tickers):
    """Equal-weight rebased-to-100 synthetic index for a sub-sector."""
    avail = [t for t in tickers if t in px.columns and px[t].dropna().shape[0] > 200]
    if len(avail) < 2:
        return None
    sub = px[avail].dropna(how="all")
    rebased = sub / sub.bfill().iloc[0] * 100
    return rebased.mean(axis=1).dropna()


def build_snapshot():
    px = load("close")
    if BENCH not in px.columns:
        raise RuntimeError(f"基准 {BENCH} 未取到(可能 FMP 取数失败/限流)。云端请改用仓库里已构建的数据，勿在 Cloud 上重跑取数。")
    bench = px[BENCH].dropna()
    meta = ticker_meta()

    stocks = []
    for t in all_tickers():
        if t not in px.columns:
            continue
        s = rrg_series(px[t].dropna(), bench, PARAMS)
        if s is None:
            continue
        last = s.iloc[-1]
        stocks.append({
            "ticker": t, "name": meta[t]["name"], "sub": meta[t]["sub"],
            "ratio": round(float(last["ratio"]), 2), "mom": round(float(last["mom"]), 2),
            "state": last["state"], "quadrant": QUAD_QUADRANT[last["state"]],
            "dMom5": round(float(last["dMom5"]), 2), "days": int(last["days"]),
            "ret20": round(float(px[t].iloc[-1] / px[t].iloc[-21] - 1) * 100, 1) if len(px[t].dropna()) > 21 else None,
            "strengthening": bool(last["mom"] >= 100 and last["dMom5"] > 0),
        })

    subs = []
    for sub, grp in TECH.items():
        synth = synthetic_subsector(px, list(grp))
        if synth is None:
            continue
        s = rrg_series(synth, bench, PARAMS)
        if s is None:
            continue
        last = s.iloc[-1]
        subs.append({
            "sub": sub, "n": len([t for t in grp if t in px.columns]),
            "ratio": round(float(last["ratio"]), 2), "mom": round(float(last["mom"]), 2),
            "state": last["state"], "quadrant": QUAD_QUADRANT[last["state"]],
            "dMom5": round(float(last["dMom5"]), 2), "days": int(last["days"]),
            "strengthening": bool(last["mom"] >= 100 and last["dMom5"] > 0),
        })

    asof = str(px.index[-1].date())
    out = {"asof": asof, "bench": BENCH, "params": PARAMS.__dict__,
           "stocks": stocks, "subs": subs,
           "groups": list(TECH.keys())}
    with open(os.path.join(OUT, "tech_rrg.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"as of {asof} · {len(stocks)} stocks · {len(subs)} sub-sectors vs {BENCH}")
    # quick quadrant tally
    from collections import Counter
    c = Counter(s["state"] for s in stocks)
    print("个股象限分布:", dict(c))
    print("走强(金边)个股:", sum(1 for s in stocks if s["strengthening"]))
    return out


if __name__ == "__main__":
    build_snapshot()
