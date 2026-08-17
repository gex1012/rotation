# -*- coding: utf-8 -*-
"""
Two train/test splits on the NEW 70-ETF industry universe (vs SPY):
  A: IS 2018-2021 -> OOS 2022+      (earlier split)
  B: IS 2021-2023 -> OOS 2024+      (the requested split)
Both models (EMA/MA), Step1 (per quadrant) + Step2 (adjacent), all params/holding
chosen on each split's IS then applied to its OOS. Panels & per-config daily
returns are cached so both splits reuse the same backtests.
"""
import os
import pickle
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

import fmp_data as fd
import industry2 as ind2
from rrg_model import build_rrg_panel
import walkforward as wf

OUT = os.path.join(os.path.dirname(__file__), "output")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
CAP = wf.CAP

CONFIGS = [  # (name, IS_start, IS_end, OOS_start)
    ("A·2018→22", "2018-01-01", "2022-01-01", "2022-01-01"),
    ("B·2021-23→24", "2021-01-01", "2024-01-01", "2024-01-01"),
]


def perf_win(dr, a, b=None):
    d = dr[dr.index >= pd.Timestamp(a)]
    if b:
        d = d[d.index < pd.Timestamp(b)]
    return wf.perf(d)


def yearly_win(dr, a):
    d = dr[dr.index >= pd.Timestamp(a)]
    return wf.yearly(d)


def main():
    px = fd.load_prices([ind2.BENCH] + ind2.all_tickers())
    op = fd.load_prices([ind2.BENCH] + ind2.all_tickers(), field="open")
    sectors = ind2.all_tickers()
    first_px = {s: px[s].first_valid_index() for s in sectors if s in px.columns}
    bench_dr = px[ind2.BENCH].pct_change().dropna()

    # build panels once per param, cache daily returns per (param, quads, reb)
    panels, dates_of = {}, {}
    for p in wf.EMA_GRID + wf.MA_GRID:
        pn = build_rrg_panel(px, sectors, ind2.BENCH, p)
        panels[p] = pn
        dates_of[p] = pd.DatetimeIndex(sorted(set().union(*[set(s.index) for s in pn.values()]))) if pn else pd.DatetimeIndex([])
    cache = {}

    def dr(p, quads, reb):
        k = (p, quads, reb)
        if k not in cache:
            cache[k] = wf.run_on_panel(panels[p], op, first_px, dates_of[p], quads, reb)
        return cache[k]

    def two_stage(grid, quads, IS_a, IS_b):
        bp, bs = grid[0], -9
        for p in grid:
            s = wf.sharpe(dr(p, quads, 20)[(dr(p, quads, 20).index >= pd.Timestamp(IS_a)) &
                                           (dr(p, quads, 20).index < pd.Timestamp(IS_b))])
            if not np.isnan(s) and s > bs:
                bs, bp = s, p
        bh, bs2 = 20, -9
        for h in wf.HOLDS:
            d = dr(bp, quads, h)
            s = wf.sharpe(d[(d.index >= pd.Timestamp(IS_a)) & (d.index < pd.Timestamp(IS_b))])
            if not np.isnan(s) and s > bs2:
                bs2, bh = s, h
        return bp, bh, dr(bp, quads, bh)

    def mrow(name, series, OOS_a, extra):
        m = perf_win(series, OOS_a)
        r = {"策略": name, "OOS最终$": f"{m['final']:,.0f}", "OOS年化%": round(m["cagr"] * 100, 2),
             "OOS夏普": round(m["sharpe"], 2), "OOS回撤%": round(m["dd"] * 100, 1)}
        r.update(extra); return r

    def pnl(curves_series, OOS_a, title, path):
        fig, ax = plt.subplots(figsize=(12, 6.3))
        for name, series in curves_series.items():
            d = series[series.index >= pd.Timestamp(OOS_a)]
            eq = CAP * (1 + d).cumprod()
            ax.plot(eq.index, eq.values, "-", lw=1.9, label=f"{name} → ${eq.iloc[-1]:,.0f}")
        db = bench_dr[bench_dr.index >= pd.Timestamp(OOS_a)]
        eqb = CAP * (1 + db).cumprod()
        ax.plot(eqb.index, eqb.values, "--", color="#111", lw=2.4, label=f"买入持有SPY → ${eqb.iloc[-1]:,.0f}")
        ax.axhline(CAP, color="#aaa", lw=.8, ls=":")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
        ax.set_title(title, fontsize=12); ax.set_ylabel("组合价值 ($100k起, OOS)")
        ax.grid(alpha=.2); ax.legend(fontsize=8.5, loc="upper left")
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig); return path

    results = {"configs": [c[0] for c in CONFIGS]}
    for cname, isa, isb, oosa in CONFIGS:
        cfg_res = {"IS": f"{isa}~{isb}", "OOS": f"{oosa}+"}
        for mtag, grid in [("EMA", wf.EMA_GRID), ("MA", wf.MA_GRID)]:
            s1, s1c = [], {}
            for q in wf.QUADS:
                bp, bh, ser = two_stage(grid, (q,), isa, isb)
                s1.append(mrow(wf.QCN[q], ser, oosa, {"参数": bp.tag().replace(mtag + "_", ""), "holding": f"{bh}d"}))
                s1c[wf.QCN[q]] = ser
            s2, s2c = [], {}
            for a, b in wf.ADJ:
                bp, bh, ser = two_stage(grid, (a, b), isa, isb)
                nm = f"{wf.QCN[a]}+{wf.QCN[b]}"
                s2.append(mrow(nm, ser, oosa, {"参数": bp.tag().replace(mtag + "_", ""), "holding": f"{bh}d"}))
                s2c[nm] = ser
            c1 = pnl(s1c, oosa, f"{cname}·{mtag}·Step1 各象限 OOS vs SPY", os.path.join(OUT, f"ts_{cname[0]}_{mtag}_s1.png"))
            c2 = pnl(s2c, oosa, f"{cname}·{mtag}·Step2 相邻合并 OOS vs SPY", os.path.join(OUT, f"ts_{cname[0]}_{mtag}_s2.png"))
            yb = yearly_win(bench_dr, oosa)
            def ymat(cser):
                yd = {k: yearly_win(v, oosa) for k, v in cser.items()}
                yrs = sorted(set().union(*[set(v) for v in yd.values()], set(yb)))
                rows = [{"策略": k, **{f"{y}{'*' if y == 2026 else ''}": v.get(y) for y in yrs}} for k, v in yd.items()]
                rows.append({"策略": "买入持有SPY", **{f"{y}{'*' if y == 2026 else ''}": yb.get(y) for y in yrs}})
                return pd.DataFrame(rows)
            bo = perf_win(bench_dr, oosa)
            cfg_res[mtag] = {"step1": pd.DataFrame(s1), "step2": pd.DataFrame(s2),
                             "s1_year": ymat(s1c), "s2_year": ymat(s2c),
                             "charts": {"s1": c1, "s2": c2},
                             "bench": {"OOS最终$": f"{CAP*(1+bench_dr[bench_dr.index>=pd.Timestamp(oosa)]).prod():,.0f}",
                                       "OOS夏普": round(bo["sharpe"], 2), "OOS年化%": round(bo["cagr"] * 100, 2),
                                       "OOS回撤%": round(bo["dd"] * 100, 1)}}
            print(f"\n[{cname}/{mtag}] Step1:\n", cfg_res[mtag]["step1"].to_string(index=False),
                  f"\n  基准SPY OOS 夏普 {cfg_res[mtag]['bench']['OOS夏普']}")
        results[cname] = cfg_res
    pickle.dump(results, open(os.path.join(OUT, "twosplit_results.pkl"), "wb"))
    print("\nsaved twosplit_results.pkl")


if __name__ == "__main__":
    main()
