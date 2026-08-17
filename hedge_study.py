# -*- coding: utf-8 -*-
"""
Downtrend-hedge study (backtest from 2021).

Overlay: when the benchmark (SPY) closes BELOW its 200-day SMA, short the
benchmark with ratio h against the long book -> strips market beta during
downtrends, keeping only the sectors' relative strength (alpha).

No look-ahead: the regime as of close d decides whether the d->d+1 return is
hedged (short held overnight into d+1).

We apply the SAME overlay to 6 long books and compare hedged vs unhedged, both
full-period and per calendar year:
  策略1默认(25d Z63) · 策略2优化(25d Z126) · 领先Q1 · 改善Q2 · 转弱Q4 · 落后Q3
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

START = "2021-01-01"          # report backtest from 2021 (warm-up uses 2019-2020)
SMA_WIN = 200
HEDGE = "SPY"
OPT = RRGParams(126, 8, 2.2, 3)


def perf(dr):
    n = len(dr)
    eq = (1 + dr).cumprod()
    cagr = eq.iloc[-1] ** (252 / n) - 1
    vol = dr.std() * np.sqrt(252)
    sharpe = (dr.mean() * 252) / vol if vol > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    return {"年化%": round(cagr * 100, 2), "夏普": round(sharpe, 2),
            "最大回撤%": round(dd * 100, 1), "Calmar": round(cagr / abs(dd), 2) if dd < 0 else np.nan}


def yearly_ret(dr):
    return {y: round(((1 + s).prod() - 1) * 100, 1) for y, s in dr.groupby(dr.index.year)}


def main():
    px = fd.load_prices(fd.all_symbols())
    opens = fd.load_prices(fd.all_symbols(), field="open")
    sectors = list(fd.SECTORS.keys())

    # --- benchmark 200d SMA regimes ---
    bench = px[HEDGE]
    sma = bench.rolling(SMA_WIN).mean()
    downtrend = (bench < sma)                          # naive: price below 200-SMA
    # refined: price below 200-SMA AND the 200-SMA itself is sloping down (vs 20d ago)
    # -> confirms a genuine downtrend, avoids the 2023-recovery whipsaw
    downtrend_ref = (bench < sma) & (sma < sma.shift(20))

    # --- build the 6 unhedged daily-return books ---
    books = {}
    r1 = run_strategy(px, sectors, StratConfig(HEDGE, 25, params=RRGParams(63, 8, 2.2, 5)), opens)
    r2 = run_strategy(px, sectors, StratConfig(HEDGE, 25, params=OPT), opens)
    books["策略1默认25d"] = r1["daily_ret"]
    books["策略2优化25d"] = r2["daily_ret"]
    q_eq, q_counts, q_spy, q_dates = qp.quadrant_backtest(px, opens, sectors, HEDGE, 20, OPT)
    QN = {"Lead": "领先Q1", "Impr": "改善Q2", "Weak": "转弱Q4", "Lag": "落后Q3"}
    for q in qp.QUADS:
        books[QN[q]] = q_eq[q].pct_change().dropna()

    bench_ret_full = bench.pct_change()

    def overlay(dr, h, regime):
        """hedged return = long return - h*bench_ret on days whose PRIOR close was risk-off."""
        regime_prev = regime.shift(1).reindex(dr.index).fillna(False)
        br = bench_ret_full.reindex(dr.index).fillna(0.0)
        return dr - h * br * regime_prev.astype(float)

    # trim to report window
    def trim(s):
        return s[s.index >= pd.Timestamp(START)]

    rep = trim(books["策略2优化25d"])
    reg_n = downtrend.shift(1).reindex(rep.index).fillna(False)
    reg_r = downtrend_ref.shift(1).reindex(rep.index).fillna(False)
    print(f"回测窗口: {rep.index[0].date()} -> {rep.index[-1].date()}")
    print(f"朴素触发(SPY<200线)  开启占比: {reg_n.mean()*100:.1f}%  ({int(reg_n.sum())}日)")
    print(f"改进触发(SPY<200且200下行) 开启占比: {reg_r.mean()*100:.1f}%  ({int(reg_r.sum())}日)\n")

    # --- full-period summary: unhedged vs naive-hedge vs refined-hedge (h=1.0) ---
    rows = []
    for name, dr in books.items():
        u = trim(dr)
        hn = trim(overlay(dr, 1.0, downtrend))
        hr = trim(overlay(dr, 1.0, downtrend_ref))
        pu, phn, phr = perf(u), perf(hn), perf(hr)
        rows.append({
            "组合": name,
            "年化%_无对冲": pu["年化%"], "年化%_朴素对冲": phn["年化%"], "年化%_改进对冲": phr["年化%"],
            "夏普_无对冲": pu["夏普"], "夏普_朴素": phn["夏普"], "夏普_改进": phr["夏普"],
            "改进夏普Δ": round(phr["夏普"] - pu["夏普"], 2),
            "回撤%_无对冲": pu["最大回撤%"], "回撤%_改进对冲": phr["最大回撤%"],
            "回撤改善": round(phr["最大回撤%"] - pu["最大回撤%"], 1),
        })
    summary = pd.DataFrame(rows)
    print("===== 全期(2021起) 无对冲 vs 朴素对冲 vs 改进对冲 汇总 =====")
    print(summary.to_string(index=False))

    # SPY / QQQ buy&hold unhedged reference
    for b in ["SPY", "QQQ"]:
        bdr = trim(px[b].pct_change().dropna())
        p = perf(bdr)
        print(f"  买入持有 {b}: 年化 {p['年化%']}%  夏普 {p['夏普']}  回撤 {p['最大回撤%']}%")

    # --- per-year: unhedged vs naive vs refined annual return, all books ---
    yrs = sorted(set(trim(books["策略2优化25d"]).index.year))
    mat_u, mat_n, mat_r = {}, {}, {}
    for name, dr in books.items():
        mat_u[name] = yearly_ret(trim(dr))
        mat_n[name] = yearly_ret(trim(overlay(dr, 1.0, downtrend)))
        mat_r[name] = yearly_ret(trim(overlay(dr, 1.0, downtrend_ref)))
    def matdf(mat):
        return pd.DataFrame({"组合": list(mat.keys()),
                             **{f"{y}{'*' if y in (2021,2026) else ''}": [mat[k].get(y, np.nan) for k in mat]
                                for y in yrs}})
    ydf_u, ydf_n, ydf_r = matdf(mat_u), matdf(mat_n), matdf(mat_r)
    print("\n===== 逐年收益% · 无对冲 ====="); print(ydf_u.to_string(index=False))
    print("\n===== 逐年收益% · 朴素对冲(SPY<200线) ====="); print(ydf_n.to_string(index=False))
    print("\n===== 逐年收益% · 改进对冲(SPY<200且200下行) ====="); print(ydf_r.to_string(index=False))

    # ---- chart 1: refined-hedge ΔSharpe by book (differential benefit) ----
    fig, ax = plt.subplots(figsize=(11, 6))
    d = summary.sort_values("改进夏普Δ")
    colors = ["#d73027" if v < 0 else "#1a9850" for v in d["改进夏普Δ"]]
    ax.barh(d["组合"], d["改进夏普Δ"], color=colors)
    for i, v in enumerate(d["改进夏普Δ"]):
        ax.text(v + (0.004 if v >= 0 else -0.004), i, f"{v:+.2f}", va="center",
                ha="left" if v >= 0 else "right", fontsize=9)
    ax.axvline(0, color="#333", lw=0.8)
    ax.set_title("改进对冲对夏普的影响 (改进对冲 − 无对冲)  ·  2021起 · SPY<200且200日线下行\n"
                 "正=对冲有益, 负=对冲有害", fontsize=12)
    ax.set_xlabel("夏普变化 Δ"); ax.grid(alpha=0.2, axis="x")
    fig.tight_layout(); p1 = os.path.join(OUT, "hedge_sharpe_delta.png")
    fig.savefig(p1, dpi=130); plt.close(fig)

    # ---- chart 2: equity unhedged vs naive vs refined for 策略2 & 改善Q2 ----
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
    for ax, name in zip(axes, ["策略2优化25d", "改善Q2"]):
        u = trim(books[name])
        hn = trim(overlay(books[name], 1.0, downtrend))
        hr = trim(overlay(books[name], 1.0, downtrend_ref))
        ax.plot(u.index, (1 + u).cumprod().values, color="#888", lw=1.6, label="无对冲")
        ax.plot(hn.index, (1 + hn).cumprod().values, color="#fdae61", lw=1.5, label="朴素对冲(200线)")
        ax.plot(hr.index, (1 + hr).cumprod().values, color="#1f6feb", lw=1.9, label="改进对冲(200线+下行)")
        reg = downtrend_ref.shift(1).reindex(u.index).fillna(False)
        ax.fill_between(u.index, 0, 1, where=reg, transform=ax.get_xaxis_transform(),
                        color="#d73027", alpha=0.10, label="改进对冲开启区间")
        ax.set_yscale("log"); ax.grid(alpha=0.2)
        ax.set_title(f"{name}: 对冲净值对比 (红色区=改进触发开启)", fontsize=11)
        ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout(); p2 = os.path.join(OUT, "hedge_equity.png")
    fig.savefig(p2, dpi=130); plt.close(fig)

    # ---- Excel ----
    xlsx = os.path.join(OUT, "hedge_study.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="全期汇总", index=False)
        ydf_u.to_excel(xw, sheet_name="逐年_无对冲", index=False)
        ydf_n.to_excel(xw, sheet_name="逐年_朴素对冲", index=False)
        ydf_r.to_excel(xw, sheet_name="逐年_改进对冲", index=False)
    print(f"\nsaved: {p1}\nsaved: {p2}\nsaved: {xlsx}")
    return summary, ydf_u, ydf_n, ydf_r, (p1, p2)


if __name__ == "__main__":
    main()
