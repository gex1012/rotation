# -*- coding: utf-8 -*-
"""Compare 策略2's quadrant-selection rules: ALL vs Q1+Q2 vs Q2+Q4.

Motivation: the quadrant-PnL study showed Q1(Lead) was the WORST quadrant and
Q4(Weak) was among the best, so filtering to Q1+Q2 (pure momentum) buys the weak
Q1 and excludes the strong Q4. Test a contrarian Q2+Q4 tilt instead.

All variants: optimized params Z126/S8/M3, 25d rebalance, T+1 open, benchmark
fill, $100k, from 2021. Q2+Q4 tested with both score-rank and distance-rank.
"""
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

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
OUT = os.path.join(os.path.dirname(__file__), "output")
CAP = 100_000
START = "2021-01-01"
OPT = RRGParams(126, 8, 2.2, 3)


def perf(dr):
    n = len(dr); eq = (1 + dr).cumprod()
    cagr = eq.iloc[-1] ** (252 / n) - 1
    vol = dr.std() * np.sqrt(252)
    sharpe = (dr.mean() * 252) / vol if vol > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    return cagr, vol, sharpe, dd


def yearly(dr):
    return {y: round(((1 + s).prod() - 1) * 100, 1) for y, s in dr.groupby(dr.index.year)}


def main():
    px = fd.load_prices(fd.all_symbols())
    opens = fd.load_prices(fd.all_symbols(), field="open")
    sectors = list(fd.SECTORS.keys())

    variants = {
        "ALL(现状·动量选前5)": StratConfig("SPY", 25, params=OPT),
        "Q1+Q2(领先+改善)": StratConfig("SPY", 25, params=OPT, quad_filter=("Lead", "Impr")),
        "Q2+Q4(改善+转弱·动量排序)": StratConfig("SPY", 25, params=OPT, quad_filter=("Impr", "Weak")),
        "Q2+Q4(改善+转弱·距离排序)": StratConfig("SPY", 25, params=OPT, quad_filter=("Impr", "Weak"), rank_by="dist"),
    }

    def trim(s):
        return s[s.index >= pd.Timestamp(START)]

    books, rows, yr = {}, [], {}
    for name, cfg in variants.items():
        res = run_strategy(px, sectors, cfg, opens)
        dr = trim(res["daily_ret"])
        books[name] = dr
        cagr, vol, sharpe, dd = perf(dr)
        eq_final = CAP * (1 + dr).prod()
        yr[name] = yearly(dr)
        rows.append({"选法": name, "最终$": f"{eq_final:,.0f}", "总收益%": round((eq_final/CAP-1)*100, 1),
                     "年化%": round(cagr*100, 2), "波动%": round(vol*100, 1), "夏普": round(sharpe, 2),
                     "最大回撤%": round(dd*100, 1), "Calmar": round(cagr/abs(dd), 2)})
    # benchmarks
    for b in ["SPY", "QQQ"]:
        dr = trim(px[b].pct_change().dropna())
        cagr, vol, sharpe, dd = perf(dr)
        yr[f"买入持有{b}"] = yearly(dr)
        rows.append({"选法": f"买入持有{b}", "最终$": f"{CAP*(1+dr).prod():,.0f}",
                     "总收益%": round(((1+dr).prod()-1)*100, 1), "年化%": round(cagr*100, 2),
                     "波动%": round(vol*100, 1), "夏普": round(sharpe, 2),
                     "最大回撤%": round(dd*100, 1), "Calmar": round(cagr/abs(dd), 2)})
    summary = pd.DataFrame(rows)
    print(f"本金 ${CAP:,}  {trim(books[list(books)[0]]).index[0].date()} -> {trim(books[list(books)[0]]).index[-1].date()}")
    print(summary.to_string(index=False))

    yrs = sorted(set(books[list(books)[0]].index.year))
    ymat = pd.DataFrame({"选法/基准": list(yr.keys()),
                         **{f"{y}{'*' if y in (2026,) else ''}": [yr[k].get(y, np.nan) for k in yr]
                            for y in yrs}})
    print("\n===== 逐年收益% (含基准) =====")
    print(ymat.to_string(index=False))

    # ---- $100k PnL chart ----
    colors = {"ALL(现状·动量选前5)": "#1f6feb", "Q1+Q2(领先+改善)": "#d73027",
              "Q2+Q4(改善+转弱·动量排序)": "#1a9850", "Q2+Q4(改善+转弱·距离排序)": "#f39c12"}
    fig, ax = plt.subplots(figsize=(13, 7.5))
    for name, dr in books.items():
        eq = CAP * (1 + dr).cumprod()
        ax.plot(eq.index, eq.values, color=colors[name], lw=2.2, label=f"{name} → ${eq.iloc[-1]:,.0f}")
    for b, c in [("SPY", "#888"), ("QQQ", "#111")]:
        eq = CAP * (1 + trim(px[b].pct_change().dropna())).cumprod()
        ax.plot(eq.index, eq.values, "--", color=c, lw=2.0, label=f"买入持有{b} → ${eq.iloc[-1]:,.0f}")
    ax.axhline(CAP, color="#aaa", lw=0.8, ls=":")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
    ax.set_ylabel("组合价值 (本金 $100,000)")
    ax.set_title("策略2 象限选法对比: ALL vs Q1+Q2 vs Q2+Q4  ·  $100k · 2021起 · 25d · T+1开盘", fontsize=12)
    ax.grid(alpha=0.2); ax.legend(fontsize=9, loc="upper left")
    fig.tight_layout(); path = os.path.join(OUT, "q_filter_compare.png")
    fig.savefig(path, dpi=135); plt.close(fig)
    print("saved:", path)

    xlsx = os.path.join(OUT, "q_filter_compare.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="全期汇总", index=False)
        ymat.to_excel(xw, sheet_name="逐年收益", index=False)
    print("saved:", xlsx)
    return summary, ymat, path


if __name__ == "__main__":
    main()
