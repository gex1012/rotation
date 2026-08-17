# -*- coding: utf-8 -*-
"""
Per-calendar-year breakdown for the two headline strategies:
  策略1 = 默认参数 Z63/S8/M5 · SPY · 25d · T+1 open
  策略2 = 优化参数 Z126/S8/M3 · SPY · 25d · T+1 open
Plus SPY / QQQ buy&hold as yearly reference.

For each year we list the "backtest parameters" (i.e. the realised annual stats):
  年度收益% · 波动% · 夏普 · 最大回撤%(年内) · 周期胜率% · 平均换手 · 换仓次数 · 超额(vsSPY)%
The RRG parameters themselves (ZWIN/SMOOTH/MOM_LAG) are fixed across all years and
are printed once per strategy in the header.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import fmp_data as fd
from rrg_model import RRGParams
from rotation_backtest import StratConfig, run_strategy
import quadrant_pnl as qp

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
OUT = os.path.join(os.path.dirname(__file__), "output")

STRATS = {
    "策略1·默认Z63/S8/M5": RRGParams(63, 8, 2.2, 5),
    "策略2·优化Z126/S8/M3": RRGParams(126, 8, 2.2, 3),
}
BENCH, REB = "SPY", 25


def year_stats(daily_ret, holdings, rebalance, bench_year_ret):
    """daily_ret: Series; holdings: log w/ 'date','turnover'; returns per-year DataFrame."""
    dr = daily_ret
    # rebalance-period returns bucketed by the year they START in (for win rate)
    period_years, period_r = [], []
    for k in range(0, len(dr), rebalance):
        seg = dr.iloc[k:k + rebalance]
        if len(seg):
            period_years.append(seg.index[0].year)
            period_r.append((1 + seg).prod() - 1)
    period_years = np.array(period_years); period_r = np.array(period_r)
    turn_by_year = {}
    for h in holdings:
        turn_by_year.setdefault(h["date"].year, []).append(h["turnover"])

    rows = []
    for y, s in dr.groupby(dr.index.year):
        ann = (1 + s).prod() - 1
        vol = s.std() * np.sqrt(252)
        sharpe = (s.mean() * 252) / vol if vol > 0 else np.nan
        eq = (1 + s).cumprod()
        dd = (eq / eq.cummax() - 1).min()
        pr = period_r[period_years == y]
        win = (pr > 0).mean() * 100 if len(pr) else np.nan
        turns = turn_by_year.get(y, [])
        rows.append({
            "年份": y, "交易日": len(s),
            "年度收益%": round(ann * 100, 2),
            "波动%": round(vol * 100, 1),
            "夏普": round(sharpe, 2),
            "最大回撤%": round(dd * 100, 1),
            "周期胜率%": round(win, 1) if not np.isnan(win) else None,
            "平均换手": round(np.mean(turns), 2) if turns else None,
            "换仓次数": len(turns),
            "超额vsSPY%": round((ann - bench_year_ret.get(y, np.nan)) * 100, 2),
        })
    return pd.DataFrame(rows)


def bench_yearly(prices, sym, dates):
    p = prices[sym].reindex(dates).ffill()
    dr = p.pct_change().dropna()
    return {y: (1 + s).prod() - 1 for y, s in dr.groupby(dr.index.year)}


def yearly_from_dr(dr, spy_year):
    """Per-year stats from a daily-return series (no turnover/win-rate).
    Used for the quadrant strategies, which are built from equity curves."""
    rows = []
    for y, s in dr.groupby(dr.index.year):
        ann = (1 + s).prod() - 1
        vol = s.std() * np.sqrt(252)
        sharpe = (s.mean() * 252) / vol if vol > 0 else np.nan
        eq = (1 + s).cumprod()
        dd = (eq / eq.cummax() - 1).min()
        rows.append({"年份": y, "交易日": len(s), "年度收益%": round(ann * 100, 2),
                     "波动%": round(vol * 100, 1), "夏普": round(sharpe, 2),
                     "最大回撤%": round(dd * 100, 1),
                     "超额vsSPY%": round((ann - spy_year.get(y, np.nan)) * 100, 2)})
    return pd.DataFrame(rows)


def ann_ret_by_year(dr):
    return {y: (1 + s).prod() - 1 for y, s in dr.groupby(dr.index.year)}


def main():
    px = fd.load_prices(fd.all_symbols())
    opens = fd.load_prices(fd.all_symbols(), field="open")
    sectors = list(fd.SECTORS.keys())

    # run both strategies first, then align them to a COMMON start date so every
    # calendar year covers the same period for both (fair year-by-year comparison).
    raw = {}
    for name, params in STRATS.items():
        cfg = StratConfig(BENCH, REB, top_k=5, params=params)
        raw[name] = (cfg, run_strategy(px, sectors, cfg, opens))
    common_start = max(res["daily_ret"].index[0] for _, res in raw.values())
    print(f"对齐起始日 (两策略共同起点): {common_start.date()}")

    # benchmark yearly on the common calendar
    common_dates = [d for d in list(raw.values())[0][1]["dates"] if d >= common_start]
    common_dates = pd.DatetimeIndex(common_dates)
    spy_year = bench_yearly(px, "SPY", common_dates)
    qqq_year = bench_yearly(px, "QQQ", common_dates)

    tables = {}
    for name, (cfg, res) in raw.items():
        dr = res["daily_ret"][res["daily_ret"].index >= common_start]
        hold = [h for h in res["holdings"]
                if pd.Timestamp(h["date"]) >= common_start]
        df = year_stats(dr, hold, REB, spy_year)
        tables[name] = df
        print(f"\n===== {name}  ({cfg.label()}) =====")
        print(df.to_string(index=False))

    # ---- quadrant strategies (T+1 open, 20d, optimized params) -> per-year ----
    q_eq, q_counts, q_spy_curve, q_dates = qp.quadrant_backtest(
        px, opens, sectors, "SPY", 20, RRGParams(126, 8, 2.2, 3))
    QNAME = {"Lead": "领先Q1", "Impr": "改善Q2", "Weak": "转弱Q4", "Lag": "落后Q3"}
    quad_tables = {}
    for q in qp.QUADS:
        dr = q_eq[q].pct_change().dropna()
        dr = dr[dr.index >= common_start]
        qtab = yearly_from_dr(dr, spy_year)
        quad_tables[QNAME[q]] = qtab
        print(f"\n===== 象限策略 {QNAME[q]}·{qp.QUAD_CN[q]} (20d, Z126/S8/M3, T+1开盘) =====")
        print(qtab.to_string(index=False))

    # benchmark yearly reference table
    yrs = sorted(set(spy_year) | set(qqq_year))
    bench_df = pd.DataFrame({
        "年份": yrs,
        "SPY买入持有%": [round(spy_year.get(y, np.nan) * 100, 2) for y in yrs],
        "QQQ买入持有%": [round(qqq_year.get(y, np.nan) * 100, 2) for y in yrs],
    })
    print("\n===== 基准逐年买入持有 =====")
    print(bench_df.to_string(index=False))

    # ---- MASTER annual-return matrix: every strategy + quadrants + benchmarks ----
    def dr_of(name):
        cfg, res = raw[name]
        d = res["daily_ret"][res["daily_ret"].index >= common_start]
        return ann_ret_by_year(d)
    yrs2 = yrs
    ann = {}
    for name in STRATS:
        ann[name] = dr_of(name)
    for q in qp.QUADS:
        dr = q_eq[q].pct_change().dropna(); dr = dr[dr.index >= common_start]
        ann[QNAME[q] + "·象限"] = ann_ret_by_year(dr)
    ann["买入持有SPY"] = spy_year
    ann["买入持有QQQ"] = qqq_year
    matrix = pd.DataFrame({
        "策略": list(ann.keys()),
        **{f"{y}{'*' if y in (2022, 2026) else ''}": [round(ann[k].get(y, np.nan) * 100, 1) for k in ann]
           for y in yrs2},
    })
    print("\n===== 年度收益率总表 (%)  所有策略 + 象限 + 基准 =====")
    print(matrix.to_string(index=False))

    # ---- combined bar chart: 4 quadrants + SPY + QQQ ----
    quad_series = {QNAME[q]: [round(ann[QNAME[q] + "·象限"].get(y, np.nan) * 100, 1) for y in yrs2]
                   for q in qp.QUADS}
    quad_series["买入持有SPY"] = [round(spy_year.get(y, np.nan) * 100, 1) for y in yrs2]
    quad_series["买入持有QQQ"] = [round(qqq_year.get(y, np.nan) * 100, 1) for y in yrs2]
    fig, ax = plt.subplots(figsize=(13, 6.8))
    x = np.arange(len(yrs2)); w = 0.13
    qcolors = ["#1a9850", "#4575b4", "#fdae61", "#d73027", "#9aa5b1", "#111"]
    for i, (lab, vals) in enumerate(quad_series.items()):
        bars = ax.bar(x + (i - 2.5) * w, vals, w, label=lab, color=qcolors[i])
        for b, v in zip(bars, vals):
            if not np.isnan(v):
                ax.text(b.get_x() + b.get_width() / 2, v + (0.4 if v >= 0 else -1.6),
                        f"{v:.0f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=6)
    ax.axhline(0, color="#666", lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels([f"{y}{'*' if y in (2022, 2026) else ''}" for y in yrs2])
    ax.set_ylabel("年度收益 %"); ax.grid(alpha=0.2, axis="y")
    ax.set_title("四象限策略逐年收益率 vs 基准买入持有  ·  SPY基准 · 20日换仓 · T+1开盘\n"
                 "(* 2022/2026 为部分年度)", fontsize=12)
    ax.legend(fontsize=8, ncol=3)
    fig.tight_layout()
    qpath = os.path.join(OUT, "yearly_quadrants.png")
    fig.savefig(qpath, dpi=130); plt.close(fig)
    print("saved:", qpath)

    # ---- two-strategy bar chart (kept) ----
    names = list(STRATS.keys())
    def col(df, y):
        r = df[df["年份"] == y]
        return float(r["年度收益%"].iloc[0]) if len(r) else np.nan
    series = {
        names[0]: [col(tables[names[0]], y) for y in yrs2],
        names[1]: [col(tables[names[1]], y) for y in yrs2],
        "买入持有SPY": [round(spy_year.get(y, np.nan) * 100, 2) for y in yrs2],
        "买入持有QQQ": [round(qqq_year.get(y, np.nan) * 100, 2) for y in yrs2],
    }
    fig, ax = plt.subplots(figsize=(12, 6.5))
    x = np.arange(len(yrs2)); w = 0.2
    colors = ["#7fb3d5", "#1f6feb", "#9aa5b1", "#111"]
    for i, (lab, vals) in enumerate(series.items()):
        bars = ax.bar(x + (i - 1.5) * w, vals, w, label=lab, color=colors[i])
        for b, v in zip(bars, vals):
            if not np.isnan(v):
                ax.text(b.get_x() + b.get_width() / 2, v + (0.5 if v >= 0 else -1.5),
                        f"{v:.0f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=7)
    ax.axhline(0, color="#666", lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels([f"{y}{'*' if y in (2022, 2026) else ''}" for y in yrs2])
    ax.set_ylabel("年度收益 %"); ax.grid(alpha=0.2, axis="y")
    ax.set_title("两个主策略逐年收益率 vs 基准买入持有  ·  SPY基准 · 25日换仓 · T+1开盘\n"
                 "(* 2022/2026 为部分年度)", fontsize=12)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    path = os.path.join(OUT, "yearly_returns.png")
    fig.savefig(path, dpi=130); plt.close(fig)
    print("saved:", path)

    # ---- Excel ----
    xlsx = os.path.join(OUT, "yearly_returns.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        matrix.to_excel(xw, sheet_name="年度收益总表", index=False)
        for name, df in tables.items():
            df.to_excel(xw, sheet_name=name[:31].replace("/", "_"), index=False)
        for name, df in quad_tables.items():
            df.to_excel(xw, sheet_name=("象限_" + name)[:31], index=False)
        bench_df.to_excel(xw, sheet_name="基准逐年", index=False)
    print("saved:", xlsx)
    return tables, quad_tables, matrix, bench_df, (path, qpath)


if __name__ == "__main__":
    main()
