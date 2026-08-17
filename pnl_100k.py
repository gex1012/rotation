# -*- coding: utf-8 -*-
"""$100,000 dollar-PnL curves for the key strategies, from 2021."""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

import fmp_data as fd
from rrg_model import RRGParams
from rotation_backtest import StratConfig, run_strategy
import quadrant_pnl as qp
from hedge_fastexit import fast_exit_regime

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
OUT = os.path.join(os.path.dirname(__file__), "output")

CAP = 100_000
START = "2021-01-01"
OPT = RRGParams(126, 8, 2.2, 3)


def main():
    px = fd.load_prices(fd.all_symbols())
    opens = fd.load_prices(fd.all_symbols(), field="open")
    sectors = list(fd.SECTORS.keys())
    bench = px["SPY"]
    fast = fast_exit_regime(bench)
    bret = bench.pct_change()

    def trim(s):
        return s[s.index >= pd.Timestamp(START)]

    # build daily-return books
    dr = {}
    dr["策略2优化25d(无对冲)"] = run_strategy(px, sectors, StratConfig("SPY", 25, params=OPT), opens)["daily_ret"]
    s2 = dr["策略2优化25d(无对冲)"]
    reg = fast.shift(1).reindex(s2.index).fillna(False)
    dr["策略2+快出半对冲"] = s2 - 0.5 * bret.reindex(s2.index).fillna(0) * reg.astype(float)
    q_eq, _, _, _ = qp.quadrant_backtest(px, opens, sectors, "SPY", 20, OPT)
    QN = {"Lead": "领先Q1象限", "Impr": "改善Q2象限", "Weak": "转弱Q4象限", "Lag": "落后Q3象限"}
    for q in qp.QUADS:
        dr[QN[q]] = q_eq[q].pct_change().dropna()
    dr["买入持有SPY"] = px["SPY"].pct_change().dropna()
    dr["买入持有QQQ"] = px["QQQ"].pct_change().dropna()

    # dollar curves ($100k start on the common 2021 start)
    curves, finals = {}, {}
    for name, d in dr.items():
        d = trim(d)
        eq = CAP * (1 + d).cumprod()
        eq.loc[eq.index[0] - pd.Timedelta(days=1)] = CAP  # anchor at 100k
        eq = eq.sort_index()
        curves[name] = eq
        finals[name] = eq.iloc[-1]

    order = ["策略2+快出半对冲", "策略2优化25d(无对冲)", "改善Q2象限", "转弱Q4象限",
             "落后Q3象限", "领先Q1象限", "买入持有SPY", "买入持有QQQ"]
    colors = {"策略2+快出半对冲": "#1a9850", "策略2优化25d(无对冲)": "#1f6feb",
              "改善Q2象限": "#4575b4", "转弱Q4象限": "#f39c12", "落后Q3象限": "#e74c3c",
              "领先Q1象限": "#16a085", "买入持有SPY": "#888", "买入持有QQQ": "#111"}

    # summary table
    print(f"本金 ${CAP:,}  ·  {trim(dr['买入持有SPY']).index[0].date()} -> {curves['买入持有SPY'].index[-1].date()}")
    rows = []
    for name in order:
        eq = curves[name]
        tot = eq.iloc[-1] / CAP - 1
        yrs = (eq.index[-1] - eq.index[0]).days / 365.25
        cagr = (eq.iloc[-1] / CAP) ** (1 / yrs) - 1
        mdd = (eq / eq.cummax() - 1).min()
        rows.append({"策略": name, "最终金额$": f"{eq.iloc[-1]:,.0f}", "总收益%": round(tot * 100, 1),
                     "年化%": round(cagr * 100, 2), "最大回撤%": round(mdd * 100, 1)})
    tab = pd.DataFrame(rows)
    print(tab.to_string(index=False))

    # chart
    fig, ax = plt.subplots(figsize=(13, 7.5))
    for name in order:
        eq = curves[name]
        lw = 2.6 if "对冲" in name else (2.2 if "买入持有" in name else 1.7)
        ls = "--" if "买入持有" in name else "-"
        ax.plot(eq.index, eq.values, ls, color=colors[name], lw=lw,
                label=f"{name}  →  ${eq.iloc[-1]:,.0f}")
        ax.scatter([eq.index[-1]], [eq.iloc[-1]], color=colors[name], s=28, zorder=5)
    ax.axhline(CAP, color="#aaa", lw=0.8, ls=":")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
    ax.set_ylabel("组合价值 (本金 $100,000)")
    ax.set_title("$100,000 本金下各策略 PnL 曲线  ·  2021起 · SPY基准 · T+1开盘\n"
                 "(策略2/象限=Z126/S8/M3; 快出半对冲=200开/50关,h0.5)", fontsize=13)
    ax.grid(alpha=0.2); ax.legend(fontsize=9, loc="upper left")
    fig.tight_layout()
    path = os.path.join(OUT, "pnl_100k.png")
    fig.savefig(path, dpi=135); plt.close(fig)
    print("saved:", path)
    tab.to_csv(os.path.join(OUT, "pnl_100k.csv"), index=False)
    return tab, path


if __name__ == "__main__":
    main()
