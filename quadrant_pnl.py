# -*- coding: utf-8 -*-
"""
Quadrant PnL study -- the paper's core claim, tested directly.

For each of the four RRG quadrants (领先/改善/转弱/落后), build a portfolio that,
at every rebalance, holds EVERY sector ETF currently sitting in that quadrant,
equal-weight, until the next rebalance. Four equity curves + SPY buy&hold.

Also plots how many ETFs occupy each quadrant over time (the rotation itself).

Empty-quadrant handling: if a quadrant has no members on a rebalance day, that
book sits in cash (0% return) for the period -- this is exactly the "not enough
names to fill" situation, handled by holding cash rather than forcing picks.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import fmp_data as fd
from rrg_model import RRGParams, build_rrg_panel

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

OUT = os.path.join(os.path.dirname(__file__), "output")
QUADS = ["Lead", "Impr", "Weak", "Lag"]
QUAD_CN = {"Lead": "第一象限·领先", "Impr": "第二象限·改善",
           "Weak": "第四象限·转弱", "Lag": "第三象限·落后"}
QUAD_COLOR = {"Lead": "#1a9850", "Impr": "#4575b4", "Weak": "#fdae61", "Lag": "#d73027"}

PARAMS = RRGParams(zwin=126, smooth=8, mom_lag=3)   # recommended config
BENCH = "SPY"
REBALANCE = 20


def quadrant_backtest(px, opens, sectors, bench, rebalance, params):
    """T+1-open execution: quadrant membership is read from close of day d, the
    new equal-weight basket is bought at the OPEN of day d+1. On the switch day the
    return splits into (old basket close_d->open_{d+1}) + (new basket open_{d+1}->close_{d+1})."""
    panel = build_rrg_panel(px, sectors, bench, params)
    common = None
    for s in panel.values():
        common = set(s.index) if common is None else (common & set(s.index))
    dates = pd.DatetimeIndex(sorted(common))
    cl = {sym: panel[sym]["price"] for sym in panel}     # close
    op = {sym: opens[sym] for sym in panel}              # open

    eq = {q: pd.Series(1.0, index=dates) for q in QUADS}
    counts = {q: pd.Series(0, index=dates) for q in QUADS}
    held = {q: {} for q in QUADS}   # sym -> weight, currently held

    for i in range(len(dates) - 1):
        d, dn = dates[i], dates[i + 1]
        if i % rebalance == 0:
            members = {q: [] for q in QUADS}
            for sym, s in panel.items():
                members[s.loc[d, "state"]].append(sym)
            new_held = {q: {sym: 1.0 / len(members[q]) for sym in members[q]} if members[q] else {}
                        for q in QUADS}
            for q in QUADS:
                r = 0.0
                for sym, w in held[q].items():                 # old basket held into the open
                    r += w * (op[sym].loc[dn] / cl[sym].loc[d] - 1)
                for sym, w in new_held[q].items():             # new basket from open to close
                    r += w * (cl[sym].loc[dn] / op[sym].loc[dn] - 1)
                eq[q].loc[dn] = eq[q].loc[d] * (1 + r)          # cash (r=0) when both empty
                counts[q].loc[d] = len(new_held[q])
            held = new_held
        else:
            for q in QUADS:
                r = sum(w * (cl[sym].loc[dn] / cl[sym].loc[d] - 1) for sym, w in held[q].items())
                eq[q].loc[dn] = eq[q].loc[d] * (1 + r)
                counts[q].loc[d] = len(held[q])
    for q in QUADS:
        counts[q].loc[dates[-1]] = counts[q].loc[dates[-2]]

    bpx = px[bench].reindex(dates).ffill()
    spy = bpx / bpx.iloc[0]
    return eq, counts, spy, dates


def metrics(curve):
    dr = curve.pct_change().dropna()
    n = len(dr)
    cagr = curve.iloc[-1] ** (252 / n) - 1
    vol = dr.std() * np.sqrt(252)
    sharpe = (dr.mean() * 252) / vol if vol > 0 else np.nan
    dd = (curve / curve.cummax() - 1).min()
    calmar = cagr / abs(dd) if dd < 0 else np.nan
    return {"总收益%": round((curve.iloc[-1] - 1) * 100, 1), "年化%": round(cagr * 100, 2),
            "波动%": round(vol * 100, 1), "夏普": round(sharpe, 2),
            "最大回撤%": round(dd * 100, 1), "Calmar": round(calmar, 2)}


def main():
    px = fd.load_prices(fd.all_symbols())
    opens = fd.load_prices(fd.all_symbols(), field="open")
    sectors = list(fd.SECTORS.keys())
    eq, counts, spy, dates = quadrant_backtest(px, opens, sectors, BENCH, REBALANCE, PARAMS)

    # ---- metrics table ----
    rows = []
    for q in QUADS:
        m = metrics(eq[q])
        rows.append({"象限": QUAD_CN[q], **m, "平均持仓数": round(counts[q].mean(), 1)})
    rows.append({"象限": f"买入持有 {BENCH}", **metrics(spy), "平均持仓数": 1})
    mdf = pd.DataFrame(rows)
    print(mdf.to_string(index=False))

    # ---- figure: two stacked panels ----
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), height_ratios=[2.4, 1],
                                   sharex=True)
    for q in QUADS:
        ax1.plot(eq[q].index, eq[q].values, color=QUAD_COLOR[q], lw=2,
                 label=f"{QUAD_CN[q]}  (年化 {metrics(eq[q])['年化%']}%, 夏普 {metrics(eq[q])['夏普']})")
    ax1.plot(spy.index, spy.values, "--", color="#333", lw=2.4,
             label=f"买入持有 SPY  (年化 {metrics(spy)['年化%']}%)")
    ax1.set_yscale("log")
    ax1.set_title(f"各象限组合滚动回测净值 (PnL)  ·  每象限内 ETF 等权 · {REBALANCE}日换仓 · T+1开盘成交\n"
                  f"基准 {BENCH} · 参数 Z{PARAMS.zwin}/S{PARAMS.smooth}/M{PARAMS.mom_lag} · "
                  f"{dates[0].date()} 至 {dates[-1].date()}", fontsize=12)
    ax1.set_ylabel("净值 (起点=1, 对数轴)")
    ax1.grid(alpha=0.2); ax1.legend(fontsize=9, loc="upper left")

    cdf = pd.DataFrame({q: counts[q] for q in QUADS})
    ax2.stackplot(cdf.index, [cdf[q] for q in QUADS],
                  colors=[QUAD_COLOR[q] for q in QUADS],
                  labels=[QUAD_CN[q] for q in QUADS], alpha=0.85)
    ax2.set_ylabel("各象限 ETF 数量")
    ax2.set_title("象限占用数量随时间变化（板块轮动的过程）", fontsize=11)
    ax2.grid(alpha=0.2); ax2.legend(fontsize=8, loc="upper left", ncol=4)
    fig.tight_layout()
    path = os.path.join(OUT, "quadrant_pnl.png")
    fig.savefig(path, dpi=130); plt.close(fig)
    print("saved:", path)

    # save curves + metrics to excel-friendly csv
    allcurves = pd.DataFrame({QUAD_CN[q]: eq[q] for q in QUADS})
    allcurves["买入持有SPY"] = spy
    allcurves.to_csv(os.path.join(OUT, "quadrant_pnl_curves.csv"))
    mdf.to_csv(os.path.join(OUT, "quadrant_pnl_metrics.csv"), index=False)
    return mdf, path


if __name__ == "__main__":
    main()
