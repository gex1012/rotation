# -*- coding: utf-8 -*-
"""
Backtest summary per scoring method (score / mom / dist) for the headline
all-quadrant top-5 rotation (20d, 2021+, 20bps, T+1 close), for industry & tech.
Different scoring -> different picks -> different backtest. Saved to
score_variants.json for the dashboard's scoring-method toggle.
"""
import os
import json
import numpy as np
import pandas as pd

import fmp_data as fd
import industry2 as ind2
import tech_data as td
from rrg_model import RRGParams
from rotation_backtest import StratConfig, run_strategy

OUT = os.path.join(os.path.dirname(__file__), "output")
CAP = 100_000
START = pd.Timestamp("2021-01-01")
P = RRGParams(126, 8, 2.2, 3)
METHODS = ["score", "mom", "dist"]
MLABEL = {"score": "综合score", "mom": "纯动量mom", "dist": "距离dist"}


def summary(px, op, sectors, bench, rank_by):
    cfg = StratConfig(bench, 20, top_k=5, quad_filter=(), fill_mode="cash",
                      execution="t1_close", cost_per_turnover=0.002, params=P, rank_by=rank_by)
    res = run_strategy(px, sectors, cfg, op)
    dr = res["daily_ret"]; dr = dr[dr.index >= START]
    eq = (1 + dr).cumprod()
    n = len(dr)
    cagr = eq.iloc[-1] ** (252 / n) - 1
    vol = dr.std() * np.sqrt(252)
    sharpe = (dr.mean() * 252) / vol if vol > 0 else float("nan")
    dd = (eq / eq.cummax() - 1).min()
    curve = [round(float(v) * CAP) for v in eq.iloc[::5]]  # downsampled equity for a sparkline
    return {"final": round(CAP * float(eq.iloc[-1])), "cagr": round(cagr * 100, 1),
            "sharpe": round(float(sharpe), 2), "dd": round(float(dd) * 100, 1),
            "bench": bench, "holds": res["holdings"][-1]["picks"], "curve": curve}


def bench_final(px, bench):
    dr = px[bench].pct_change().dropna(); dr = dr[dr.index >= START]
    return round(CAP * float((1 + dr).prod()))


def main():
    out = {}
    # industry
    ip = fd.load_prices([ind2.BENCH] + ind2.all_tickers())
    io = fd.load_prices([ind2.BENCH] + ind2.all_tickers(), field="open")
    out["ind"] = {m: summary(ip, io, ind2.all_tickers(), ind2.BENCH, m) for m in METHODS}
    out["ind_bench"] = {"final": bench_final(ip, "SPY"), "name": "买入持有SPY"}
    # tech
    tsyms = td.all_tickers() + ["SOXX", "QQQ"]
    tp = fd.load_prices(tsyms); to = fd.load_prices(tsyms, field="open")
    stocks = [t for t in td.all_tickers() if t in tp.columns]
    out["tech"] = {m: summary(tp, to, stocks, "SOXX", m) for m in METHODS}
    out["tech_bench"] = {"final": bench_final(tp, "SOXX"), "name": "买入持有SOXX"}
    out["labels"] = MLABEL
    json.dump(out, open(os.path.join(OUT, "score_variants.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    for u in ["ind", "tech"]:
        print(u, {m: (out[u][m]["sharpe"], out[u][m]["final"], out[u][m]["holds"]) for m in METHODS})


if __name__ == "__main__":
    main()
