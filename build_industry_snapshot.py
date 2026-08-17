# -*- coding: utf-8 -*-
"""Industry RRG snapshot (37 sector ETFs vs SPY) -> industry_rrg.json for the dashboard."""
import os
import json
import pandas as pd
import fmp_data as fd
from rrg_model import RRGParams, rrg_series, QUAD_QUADRANT

OUT = os.path.join(os.path.dirname(__file__), "output")
PARAMS = RRGParams(126, 8, 2.2, 3)
BENCH = "SPY"

GROUPS = {
    "科技成长": ["SMH", "IGV", "CIBR", "SKYY", "FDN", "FINX", "IPAY", "AIQ", "BOTZ", "ARKK"],
    "通信": ["XLC"],
    "医疗": ["XBI", "IHI", "PPH", "IHF"],
    "金融": ["KRE", "KBE", "IAI", "KIE"],
    "能源": ["XOP", "OIH"],
    "材料金属": ["GDX", "COPX", "LIT", "URA", "XME", "MOO"],
    "工业": ["ITA", "JETS", "PAVE", "IYT"],
    "消费": ["XRT", "XHB"],
    "清洁能源": ["TAN"],
    "防御": ["XLP", "XLU", "XLRE"],
}
G_OF = {t: g for g, ts in GROUPS.items() for t in ts}


def main():
    px = fd.load_prices(fd.all_symbols())
    bench = px[BENCH].dropna()
    stocks = []
    for t, name in fd.SECTORS.items():
        if t not in px.columns:
            continue
        s = rrg_series(px[t].dropna(), bench, PARAMS)
        if s is None:
            continue
        last = s.iloc[-1]
        stocks.append({"ticker": t, "name": name, "sub": G_OF.get(t, "其他"),
                       "ratio": round(float(last["ratio"]), 2), "mom": round(float(last["mom"]), 2),
                       "state": last["state"], "quadrant": QUAD_QUADRANT[last["state"]],
                       "dMom5": round(float(last["dMom5"]), 2), "days": int(last["days"]),
                       "ret20": round(float(px[t].iloc[-1] / px[t].iloc[-21] - 1) * 100, 1),
                       "strengthening": bool(last["mom"] >= 100 and last["dMom5"] > 0)})
    subs = []
    for g, ts in GROUPS.items():
        avail = [t for t in ts if t in px.columns]
        if len(avail) < 2:
            base = px[avail].bfill().iloc[0]
            synth = (px[avail] / base * 100).mean(axis=1) if avail else None
        else:
            base = px[avail].bfill().iloc[0]
            synth = (px[avail] / base * 100).mean(axis=1)
        if synth is None:
            continue
        s = rrg_series(synth.dropna(), bench, PARAMS)
        if s is None:
            continue
        last = s.iloc[-1]
        subs.append({"sub": g, "n": len(avail), "ratio": round(float(last["ratio"]), 2),
                     "mom": round(float(last["mom"]), 2), "state": last["state"],
                     "quadrant": QUAD_QUADRANT[last["state"]],
                     "strengthening": bool(last["mom"] >= 100 and last["dMom5"] > 0)})
    out = {"asof": str(px.index[-1].date()), "bench": BENCH, "params": PARAMS.__dict__,
           "stocks": stocks, "subs": subs, "groups": list(GROUPS.keys())}
    json.dump(out, open(os.path.join(OUT, "industry_rrg.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"industry snapshot: {len(stocks)} sectors, {len(subs)} groups, asof {out['asof']}")


if __name__ == "__main__":
    main()
