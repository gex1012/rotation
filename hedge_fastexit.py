# -*- coding: utf-8 -*-
"""
Fast-exit hedge (asymmetric hysteresis) applied at half ratio to STRONG long books.

Regime state machine on SPY:
  * turn hedge ON  when SPY closes below its 200-day SMA  (slow, only real breaks)
  * turn hedge OFF when SPY reclaims its  50-day SMA      (fast, exits early on the bounce)
  -> keeps 2022's protection but gives far less back in the 2023/2025 recoveries.

Hedge ratio h = 0.5 (half market-neutral), recommended only for the STRONG books
(the two top-5 momentum strategies + 领先Q1 + 改善Q2). Weak quadrants (Q3/Q4) are
computed too but flagged "不建议对冲".

Benchmark (SPY / QQQ buy&hold) annual returns are shown alongside for comparison.
Backtest reported from 2021 (warm-up uses 2019-2020).
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

START = "2021-01-01"
OPT = RRGParams(126, 8, 2.2, 3)
STRONG = {"策略1默认25d", "策略2优化25d", "领先Q1", "改善Q2"}
HALF = 0.5


def perf(dr):
    n = len(dr); eq = (1 + dr).cumprod()
    cagr = eq.iloc[-1] ** (252 / n) - 1
    vol = dr.std() * np.sqrt(252)
    sharpe = (dr.mean() * 252) / vol if vol > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    return {"年化%": round(cagr * 100, 2), "夏普": round(sharpe, 2),
            "最大回撤%": round(dd * 100, 1), "Calmar": round(cagr / abs(dd), 2) if dd < 0 else np.nan}


def yearly_ret(dr):
    return {y: round(((1 + s).prod() - 1) * 100, 1) for y, s in dr.groupby(dr.index.year)}


def fast_exit_regime(bench):
    """Stateful hedge flag: ON below 200-SMA, OFF once back above 50-SMA."""
    sma50 = bench.rolling(50).mean()
    sma200 = bench.rolling(200).mean()
    state = False
    out = []
    for p, s50, s200 in zip(bench, sma50, sma200):
        if np.isnan(s200) or np.isnan(s50):
            out.append(False); continue
        if not state and p < s200:
            state = True
        elif state and p > s50:
            state = False
        out.append(state)
    return pd.Series(out, index=bench.index)


def main():
    px = fd.load_prices(fd.all_symbols())
    opens = fd.load_prices(fd.all_symbols(), field="open")
    sectors = list(fd.SECTORS.keys())
    bench = px["SPY"]

    naive = (bench < bench.rolling(200).mean())          # old naive regime (ref)
    fast = fast_exit_regime(bench)                       # new fast-exit regime
    bench_ret_full = bench.pct_change()

    # --- 6 long books ---
    books = {}
    books["策略1默认25d"] = run_strategy(px, sectors, StratConfig("SPY", 25, params=RRGParams(63, 8, 2.2, 5)), opens)["daily_ret"]
    books["策略2优化25d"] = run_strategy(px, sectors, StratConfig("SPY", 25, params=OPT), opens)["daily_ret"]
    q_eq, _, _, _ = qp.quadrant_backtest(px, opens, sectors, "SPY", 20, OPT)
    QN = {"Lead": "领先Q1", "Impr": "改善Q2", "Weak": "转弱Q4", "Lag": "落后Q3"}
    for q in qp.QUADS:
        books[QN[q]] = q_eq[q].pct_change().dropna()

    def overlay(dr, h, regime):
        regime_prev = regime.shift(1).reindex(dr.index).fillna(False)
        br = bench_ret_full.reindex(dr.index).fillna(0.0)
        return dr - h * br * regime_prev.astype(float)

    def trim(s):
        return s[s.index >= pd.Timestamp(START)]

    rep = trim(books["策略2优化25d"])
    print(f"回测窗口: {rep.index[0].date()} -> {rep.index[-1].date()}")
    print(f"朴素对冲(<200线) 开启占比: {trim(naive).mean()*100:.1f}%")
    print(f"快出对冲(<200开/>50关) 开启占比: {trim(fast).mean()*100:.1f}%\n")

    # --- full-period summary: unhedged / full-200-h1(naive) / fast-exit-h0.5 ---
    rows = []
    for name, dr in books.items():
        u = trim(dr)
        old = trim(overlay(dr, 1.0, naive))
        fx = trim(overlay(dr, HALF, fast))
        pu, po, pf = perf(u), perf(old), perf(fx)
        rows.append({
            "组合": name, "建议对冲": "宜(强势多头)" if name in STRONG else "不宜(弱势)",
            "年化%_无对冲": pu["年化%"], "年化%_旧全对冲": po["年化%"], "年化%_快出半对冲": pf["年化%"],
            "夏普_无": pu["夏普"], "夏普_旧全": po["夏普"], "夏普_快出半": pf["夏普"],
            "夏普Δ_快出": round(pf["夏普"] - pu["夏普"], 2),
            "回撤%_无": pu["最大回撤%"], "回撤%_快出半": pf["最大回撤%"],
            "回撤改善_快出": round(pf["最大回撤%"] - pu["最大回撤%"], 1),
        })
    # benchmark rows
    for b in ["SPY", "QQQ"]:
        p = perf(trim(px[b].pct_change().dropna()))
        rows.append({"组合": f"买入持有{b}", "建议对冲": "基准",
                     "年化%_无对冲": p["年化%"], "年化%_旧全对冲": None, "年化%_快出半对冲": None,
                     "夏普_无": p["夏普"], "夏普_旧全": None, "夏普_快出半": None, "夏普Δ_快出": None,
                     "回撤%_无": p["最大回撤%"], "回撤%_快出半": None, "回撤改善_快出": None})
    summary = pd.DataFrame(rows)
    print("===== 全期(2021起) 无对冲 / 旧全对冲 / 快出半对冲  汇总 =====")
    print(summary.to_string(index=False))

    # --- per-year matrix: unhedged vs fast-exit-h0.5, + benchmark rows ---
    yrs = sorted(set(rep.index.year))
    spy_y = yearly_ret(trim(px["SPY"].pct_change().dropna()))
    qqq_y = yearly_ret(trim(px["QQQ"].pct_change().dropna()))
    rows_u, rows_f = {}, {}
    for name, dr in books.items():
        rows_u[name] = yearly_ret(trim(dr))
        rows_f[name] = yearly_ret(trim(overlay(dr, HALF, fast)))
    def matdf(mat, add_bench):
        d = {"组合": list(mat.keys()), **{f"{y}{'*' if y in (2026,) else ''}":
             [mat[k].get(y, np.nan) for k in mat] for y in yrs}}
        df = pd.DataFrame(d)
        if add_bench:
            for lab, yv in [("买入持有SPY", spy_y), ("买入持有QQQ", qqq_y)]:
                df.loc[len(df)] = [lab] + [yv.get(y, np.nan) for y in yrs]
        return df
    ydf_u = matdf(rows_u, True)
    ydf_f = matdf(rows_f, True)
    print("\n===== 逐年收益% · 无对冲 (含基准) ====="); print(ydf_u.to_string(index=False))
    print("\n===== 逐年收益% · 快出半对冲h0.5 (含基准) ====="); print(ydf_f.to_string(index=False))

    # ---- chart 1: equity of 策略2 & 领先Q1: unhedged / old-full / fast-half ----
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
    for ax, name in zip(axes, ["策略2优化25d", "领先Q1"]):
        u = trim(books[name]); old = trim(overlay(books[name], 1.0, naive)); fx = trim(overlay(books[name], HALF, fast))
        ax.plot(u.index, (1 + u).cumprod().values, color="#888", lw=1.6, label="无对冲")
        ax.plot(old.index, (1 + old).cumprod().values, color="#fdae61", lw=1.4, label="旧: 全对冲(200线)")
        ax.plot(fx.index, (1 + fx).cumprod().values, color="#1a9850", lw=2.0, label="新: 快出半对冲(200开/50关,h0.5)")
        reg = fast.shift(1).reindex(u.index).fillna(False)
        ax.fill_between(u.index, 0, 1, where=reg, transform=ax.get_xaxis_transform(),
                        color="#d73027", alpha=0.10, label="快出对冲开启区间")
        ax.set_yscale("log"); ax.grid(alpha=0.2)
        ax.set_title(f"{name}: 快出半对冲 vs 旧全对冲 vs 无对冲", fontsize=11)
        ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout(); p1 = os.path.join(OUT, "hedge_fastexit_equity.png")
    fig.savefig(p1, dpi=130); plt.close(fig)

    # ---- chart 2: per-year bars, strong books unhedged vs fast-half + benchmarks ----
    show = ["策略2优化25d", "领先Q1", "改善Q2"]
    series = {}
    for name in show:
        series[name + "·无"] = [rows_u[name].get(y, np.nan) for y in yrs]
        series[name + "·快出对冲"] = [rows_f[name].get(y, np.nan) for y in yrs]
    series["SPY"] = [spy_y.get(y, np.nan) for y in yrs]
    series["QQQ"] = [qqq_y.get(y, np.nan) for y in yrs]
    fig, ax = plt.subplots(figsize=(14, 6.8))
    x = np.arange(len(yrs)); w = 0.1
    cmap = ["#7fb3d5", "#1f6feb", "#a6d96a", "#1a9850", "#f5b7b1", "#e74c3c", "#bbb", "#111"]
    for i, (lab, vals) in enumerate(series.items()):
        ax.bar(x + (i - len(series)/2 + 0.5) * w, vals, w, label=lab, color=cmap[i % len(cmap)])
    ax.axhline(0, color="#333", lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels([f"{y}{'*' if y in (2026,) else ''}" for y in yrs])
    ax.set_ylabel("年度收益 %"); ax.grid(alpha=0.2, axis="y")
    ax.set_title("强势多头: 快出半对冲 vs 无对冲 vs 基准  逐年收益  ·  2021起", fontsize=12)
    ax.legend(fontsize=7, ncol=4)
    fig.tight_layout(); p2 = os.path.join(OUT, "hedge_fastexit_yearly.png")
    fig.savefig(p2, dpi=130); plt.close(fig)

    xlsx = os.path.join(OUT, "hedge_fastexit.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="全期汇总", index=False)
        ydf_u.to_excel(xw, sheet_name="逐年_无对冲_含基准", index=False)
        ydf_f.to_excel(xw, sheet_name="逐年_快出半对冲_含基准", index=False)
    print(f"\nsaved: {p1}\nsaved: {p2}\nsaved: {xlsx}")
    return summary, ydf_u, ydf_f, (p1, p2)


if __name__ == "__main__":
    main()
