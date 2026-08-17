# -*- coding: utf-8 -*-
"""
Walk-forward pipeline (the corrected methodology):
  * ALL parameters/holding chosen ON 2018-2021 (in-sample), then applied to
    2022+ (out-of-sample = 'live'). All reported metrics are OOS.
  * Tech: stocks younger than 3 months are never traded (63-day min history;
    RRG warm-up of 6-14 months is even stricter, so this rarely binds).
  * Two models compared: EMA RRG (z-score) and MA RRG (ROC/SMA).
  * Step 1 (per quadrant): pick best model params at holding=20, then pick best
    holding span. Step 2 (adjacent merged): same two-stage selection.
  * Two blocks: 行业 vs SPY, 科技 vs SOXX.

Panels are built once per (params) and reused across quadrants/holdings for speed.
Saves walkforward_results.pkl + PnL charts.
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
import tech_data as td
from rrg_model import RRGParams, build_rrg_panel

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
OUT = os.path.join(os.path.dirname(__file__), "output")

CAP = 100_000
COST = 0.002
TOPK = 5
MIN_HIST = 63                      # 3-month new-stock guard (trading days)
IS_A, IS_B = pd.Timestamp("2018-01-01"), pd.Timestamp("2022-01-01")
OOS_A = pd.Timestamp("2022-01-01")
QUADS = ["Lead", "Impr", "Weak", "Lag"]
QCN = {"Lead": "领先Q1", "Impr": "改善Q2", "Weak": "转弱Q4", "Lag": "落后Q3"}
ADJ = [("Impr", "Lead"), ("Lead", "Weak"), ("Weak", "Lag"), ("Lag", "Impr")]
HOLDS = [5, 10, 15, 20, 25, 30]

EMA_GRID = [RRGParams(model="ema", zwin=z, smooth=8, scale=2.2, mom_lag=m)
            for z in (63, 126) for m in (3, 5, 10)]
MA_GRID = [RRGParams(model="ma", lr=lr, lm=lm, ma_smooth=10)
           for lr in (180, 250) for lm in (40, 80)]


def sharpe(dr):
    dr = dr.dropna()
    if len(dr) < 20 or dr.std() == 0:
        return np.nan
    return (dr.mean() * 252) / (dr.std() * np.sqrt(252))


def perf(dr):
    dr = dr.dropna()
    n = len(dr); eq = (1 + dr).cumprod()
    cagr = eq.iloc[-1] ** (252 / n) - 1 if n else np.nan
    dd = (eq / eq.cummax() - 1).min()
    return dict(final=CAP * (1 + dr).prod(), cagr=cagr, vol=dr.std() * np.sqrt(252),
                sharpe=sharpe(dr), dd=dd)


def yearly(dr):
    return {y: round(((1 + s).prod() - 1) * 100, 1) for y, s in dr.dropna().groupby(dr.dropna().index.year)}


def IS(dr):
    return dr[(dr.index >= IS_A) & (dr.index < IS_B)]


def OOS(dr):
    return dr[dr.index >= OOS_A]


def run_on_panel(panel, opens, first_px_date, dates, quads, reb):
    """T+1-close, top-5 by score from `quads`, cash fill, 20bps, 3-mo guard."""
    cl = {s: panel[s]["price"].reindex(dates).ffill() for s in panel}
    op = {s: opens[s].reindex(dates).ffill() for s in panel if s in opens.columns}
    pos = {d: i for i, d in enumerate(dates)}

    def score(r):
        return (r["ratio"] - 100) + 1.5 * (r["mom"] - 100)

    daily = pd.Series(0.0, index=dates[1:])
    held, pending = {}, None
    for i in range(len(dates) - 1):
        d, dn = dates[i], dates[i + 1]; cost = 0.0
        if pending is not None:
            turn = sum(abs(pending.get(s, 0) - held.get(s, 0)) for s in set(pending) | set(held))
            cost = turn * COST; held = pending; pending = None
        if i % reb == 0:
            snap = {}
            for s, ser in panel.items():
                if d in ser.index:
                    row = ser.loc[d]
                    if (not np.isnan(row["ratio"]) and row["state"] in quads
                            and (i - pos.get(first_px_date.get(s, dates[0]), 0)) >= MIN_HIST):
                        snap[s] = row
            ranked = sorted(snap.items(), key=lambda kv: score(kv[1]), reverse=True)
            picks = [s for s, _ in ranked[:TOPK]]
            w = 1.0 / len(picks) if picks else 0.0
            pending = {s: w for s in picks}
        r = 0.0
        for s, wt in held.items():
            r += wt * (cl[s].loc[dn] / cl[s].loc[d] - 1)
        daily.loc[dn] = r - cost
    return daily


def two_stage(panels, opens, first_px, dates_of, quads):
    """Pick best params @ holding=20 on IS, then best holding at those params (IS)."""
    bestp, bs = None, -9
    for p, panel in panels.items():
        dr = run_on_panel(panel, opens, first_px, dates_of[p], quads, 20)
        s = sharpe(IS(dr))
        if not np.isnan(s) and s > bs:
            bs, bestp = s, p
    besth, bs2 = 20, -9
    for h in HOLDS:
        dr = run_on_panel(panels[bestp], opens, first_px, dates_of[bestp], quads, h)
        s = sharpe(IS(dr))
        if not np.isnan(s) and s > bs2:
            bs2, besth = s, h
    dr_full = run_on_panel(panels[bestp], opens, first_px, dates_of[bestp], quads, besth)
    dr_h20 = run_on_panel(panels[bestp], opens, first_px, dates_of[bestp], quads, 20)
    return bestp, besth, dr_full, dr_h20


def mrow(name, dr_oos, extra):
    m = perf(dr_oos)
    r = {"策略": name, "OOS最终$": f"{m['final']:,.0f}", "OOS年化%": round(m["cagr"] * 100, 2),
         "OOS夏普": round(m["sharpe"], 2), "OOS回撤%": round(m["dd"] * 100, 1),
         "Calmar": round(m["cagr"] / abs(m["dd"]), 2) if m["dd"] < 0 else None}
    r.update(extra); return r


def pnl_chart(curves, bench_oos, title, path):
    fig, ax = plt.subplots(figsize=(12, 6.4))
    for name, dr in curves.items():
        eq = CAP * (1 + OOS(dr)).cumprod()
        ax.plot(eq.index, eq.values, "-", lw=1.9, label=f"{name} → ${eq.iloc[-1]:,.0f}")
    eqb = CAP * (1 + bench_oos).cumprod()
    ax.plot(eqb.index, eqb.values, "--", color="#111", lw=2.4, label=f"买入持有 → ${eqb.iloc[-1]:,.0f}")
    ax.axhline(CAP, color="#aaa", lw=.8, ls=":")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
    ax.set_title(title, fontsize=12); ax.set_ylabel("组合价值 ($100k起, OOS)")
    ax.grid(alpha=.2); ax.legend(fontsize=8.5, loc="upper left")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig); return path


def block(px, op, sectors, bench, tag):
    print(f"\n===== BLOCK {tag} vs {bench} =====")
    first_px = {s: px[s].first_valid_index() for s in sectors if s in px.columns}
    bench_dr = px[bench].pct_change().dropna()
    res = {"tag": tag, "bench": bench, "IS": f"{IS_A.date()}~{IS_B.date()}", "OOS": f"{OOS_A.date()}+"}
    for mtag, grid in [("EMA", EMA_GRID), ("MA", MA_GRID)]:
        panels, dates_of = {}, {}
        for p in grid:
            pn = build_rrg_panel(px, sectors, bench, p)
            panels[p] = pn
            dates_of[p] = pd.DatetimeIndex(sorted(set().union(*[set(s.index) for s in pn.values()]))) if pn else pd.DatetimeIndex([])
        # step1 singles
        s1_rows, s1_curves, s1_year = [], {}, {}
        for q in QUADS:
            bp, bh, dr, _ = two_stage(panels, op, first_px, dates_of, (q,))
            s1_rows.append(mrow(f"{QCN[q]}", OOS(dr),
                                {"最优参数": bp.tag(), "最优holding": f"{bh}d"}))
            s1_curves[QCN[q]] = dr; s1_year[QCN[q]] = yearly(OOS(dr))
        # step2 merged adjacent
        s2_rows, s2_curves, s2_year = [], {}, {}
        for a, b in ADJ:
            bp, bh, dr, _ = two_stage(panels, op, first_px, dates_of, (a, b))
            nm = f"{QCN[a]}+{QCN[b]}"
            s2_rows.append(mrow(nm, OOS(dr), {"最优参数": bp.tag(), "最优holding": f"{bh}d"}))
            s2_curves[nm] = dr; s2_year[nm] = yearly(OOS(dr))
        # charts + yearly matrices
        c1 = pnl_chart(s1_curves, OOS(bench_dr), f"{tag}·{mtag} RRG·Step1 各象限(2022+实盘) vs 买入持有{bench}",
                       os.path.join(OUT, f"wf_{tag}_{mtag}_s1.png"))
        c2 = pnl_chart(s2_curves, OOS(bench_dr), f"{tag}·{mtag} RRG·Step2 相邻合并(2022+实盘) vs 买入持有{bench}",
                       os.path.join(OUT, f"wf_{tag}_{mtag}_s2.png"))
        def ymat(yd, bench_dr):
            yb = yearly(OOS(bench_dr))
            yrs = sorted(set().union(*[set(v) for v in yd.values()], set(yb)))
            rows = [{"策略": k, **{f"{y}{'*' if y == 2026 else ''}": v.get(y) for y in yrs}} for k, v in yd.items()]
            rows.append({"策略": f"买入持有{bench}", **{f"{y}{'*' if y == 2026 else ''}": yb.get(y) for y in yrs}})
            return pd.DataFrame(rows)
        res[mtag] = {"step1": pd.DataFrame(s1_rows), "step2": pd.DataFrame(s2_rows),
                     "s1_year": ymat(s1_year, bench_dr), "s2_year": ymat(s2_year, bench_dr),
                     "charts": {"s1": c1, "s2": c2}}
        bo = perf(OOS(bench_dr))
        res[mtag]["bench_row"] = {"策略": f"买入持有{bench}", "OOS最终$": f"{bo['final']:,.0f}",
                                  "OOS年化%": round(bo["cagr"] * 100, 2), "OOS夏普": round(bo["sharpe"], 2),
                                  "OOS回撤%": round(bo["dd"] * 100, 1)}
        print(f"[{tag}/{mtag}] step1:\n", res[mtag]["step1"].to_string(index=False))
    return res


def main():
    px_i = fd.load_prices(fd.all_symbols()); op_i = fd.load_prices(fd.all_symbols(), field="open")
    spy = block(px_i, op_i, list(fd.SECTORS.keys()), "SPY", "行业")

    tsyms = td.all_tickers() + ["SOXX", "QQQ"]
    px_t = fd.load_prices(tsyms, field="close"); op_t = fd.load_prices(tsyms, field="open")
    stocks = [t for t in td.all_tickers() if t in px_t.columns]
    soxx = block(px_t, op_t, stocks, "SOXX", "科技")

    pickle.dump({"SPY": spy, "SOXX": soxx, "cost_bps": COST * 1e4, "topk": TOPK,
                 "min_hist": MIN_HIST}, open(os.path.join(OUT, "walkforward_results.pkl"), "wb"))
    print("\nsaved walkforward_results.pkl")


if __name__ == "__main__":
    main()
