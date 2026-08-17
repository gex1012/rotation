# -*- coding: utf-8 -*-
"""Industry RRG snapshot (new 70-ETF universe vs SPY) -> industry_rrg.json for the dashboard."""
import os
import json
import fmp_data as fd
import industry2 as ind2
from rrg_model import RRGParams, rrg_series, QUAD_QUADRANT

OUT = os.path.join(os.path.dirname(__file__), "output")
PARAMS = RRGParams(126, 8, 2.2, 3)
BENCH = ind2.BENCH
GROUPS = ind2.GROUPS
G_OF = ind2.G_OF


def main():
    px = fd.load_prices([BENCH] + ind2.all_tickers())
    bench = px[BENCH].dropna()
    stocks = []
    for t, name in ind2.SECTORS.items():
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
            continue
        base = px[avail].bfill().iloc[0]
        synth = (px[avail] / base * 100).mean(axis=1)
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
    print(f"industry snapshot: {len(stocks)} ETFs, {len(subs)} groups, asof {out['asof']}")


if __name__ == "__main__":
    main()
