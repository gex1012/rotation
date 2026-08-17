# -*- coding: utf-8 -*-
"""
Out-of-sample validation of the mixed-holding-period idea. ALL strategies top-5.

Part 1: each SINGLE quadrant at its own best holding period (full sample, top5)
        -> full metrics + yearly.
Part 2: walk-forward split
        IS  = 2021-01 .. 2024-01  (pick best period per quadrant here)
        OOS = 2024-01 .. end       (apply those IS-chosen periods, measure)
        -> is the optimal period stable? does the mixed strategy still beat SPY OOS?
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

import fmp_data as fd
from quad_combo import build_panel, combo_backtest, perf, CN

OUT = os.path.join(os.path.dirname(__file__), "output")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

CAP = 100_000
TOPK = 5
REBS = [5, 10, 15, 20, 25, 30]
QUADS = ["Lead", "Impr", "Weak", "Lag"]
IS_A, IS_B = pd.Timestamp("2021-01-01"), pd.Timestamp("2024-01-01")
OOS_A, OOS_B = pd.Timestamp("2024-01-01"), pd.Timestamp("2027-01-01")


def sl(s, a, b):
    return s[(s.index >= a) & (s.index < b)]


def metr(dr):
    if len(dr) < 20:
        return dict(cagr=np.nan, vol=np.nan, sharpe=np.nan, dd=np.nan, final=np.nan)
    cagr, vol, sharpe, dd = perf(dr)
    return dict(cagr=cagr, vol=vol, sharpe=sharpe, dd=dd, final=CAP * (1 + dr).prod())


def yearly(dr):
    return {y: round(((1 + s).prod() - 1) * 100, 1) for y, s in dr.groupby(dr.index.year)}


def main():
    px = fd.load_prices(fd.all_symbols())
    opens = fd.load_prices(fd.all_symbols(), field="open")
    panel = build_panel(px)

    # cache full daily returns for every (quad, reb) once
    cache = {}
    for q in QUADS:
        for r in REBS:
            cache[(q, r)] = combo_backtest(panel, opens, {q}, r, top_k=TOPK)[0]

    def best_period(q, a, b):
        best_r, best_s = None, -9
        for r in REBS:
            m = metr(sl(cache[(q, r)], a, b))
            if not np.isnan(m["sharpe"]) and m["sharpe"] > best_s:
                best_s, best_r = m["sharpe"], r
        return best_r

    # ---------- PART 1: single quadrant at best period (full sample, top5) ----------
    FULL_A = IS_A
    print("===== PART 1: 单象限 top5 · 各自最优持有周期 · 全样本(2021起) =====")
    rows, yrows = [], []
    for q in QUADS:
        br = best_period(q, FULL_A, OOS_B)
        dr = sl(cache[(q, br)], FULL_A, OOS_B)
        m = metr(dr)
        rows.append({"象限": CN[q], "最优周期": f"{br}d", "最终$": f"{m['final']:,.0f}",
                     "总收益%": round((m['final']/CAP-1)*100, 1), "年化%": round(m['cagr']*100, 2),
                     "波动%": round(m['vol']*100, 1), "夏普": round(m['sharpe'], 2),
                     "最大回撤%": round(m['dd']*100, 1), "Calmar": round(m['cagr']/abs(m['dd']), 2)})
        yr = yearly(dr); yr["象限"] = f"{CN[q]}@{br}d"; yrows.append(yr)
    p1 = pd.DataFrame(rows)
    print(p1.to_string(index=False))
    yrs = sorted({y for yr in yrows for y in yr if isinstance(y, int)})
    ydf = pd.DataFrame([{"象限@周期": r["象限"], **{f"{y}{'*' if y==2026 else ''}": r.get(y) for y in yrs}}
                        for r in yrows])
    print("\n单象限逐年收益% (各自最优周期):"); print(ydf.to_string(index=False))

    # ---------- PART 2: walk-forward validation ----------
    print("\n===== PART 2: 样本外验证 (IS=2021-2023 定周期, OOS=2024-2026 检验) =====")
    stab = []
    for q in QUADS:
        is_r = best_period(q, IS_A, IS_B)
        oos_r = best_period(q, OOS_A, OOS_B)
        is_sh = metr(sl(cache[(q, is_r)], IS_A, IS_B))["sharpe"]
        # apply IS-chosen period in OOS:
        oos_sh_applied = metr(sl(cache[(q, is_r)], OOS_A, OOS_B))["sharpe"]
        oos_sh_best = metr(sl(cache[(q, oos_r)], OOS_A, OOS_B))["sharpe"]
        stab.append({"象限": CN[q], "IS最优周期": f"{is_r}d", "IS夏普": round(is_sh, 2),
                     "OOS用IS周期夏普": round(oos_sh_applied, 2),
                     "OOS自身最优周期": f"{oos_r}d", "OOS最优夏普": round(oos_sh_best, 2),
                     "周期稳定?": "稳定" if is_r == oos_r else "漂移"})
    stab_df = pd.DataFrame(stab)
    print("单象限周期稳定性:"); print(stab_df.to_string(index=False))

    # mixed strategy: periods chosen on IS only (Q1/Q4/Q3, drop Q2 as before), applied OOS
    is_periods = {q: best_period(q, IS_A, IS_B) for q in ["Lead", "Weak", "Lag"]}
    print(f"\nIS 选出的混合周期: " + ", ".join(f"{CN[q]}@{r}d" for q, r in is_periods.items()))

    def mix_dr(periods):
        eqs = [(1 + cache[(q, r)]).cumprod() for q, r in periods.items()]
        idx = eqs[0].index
        total = sum(e.reindex(idx).ffill() for e in eqs) / len(eqs)
        return total.pct_change().dropna()

    mix_is_tuned = mix_dr(is_periods)                       # IS-tuned periods
    mix_fixed20 = mix_dr({q: 20 for q in ["Lead", "Weak", "Lag"]})  # naive fixed 20d baseline

    print("\n混合策略 OOS 表现对比 (2024-2026):")
    cmp = []
    for name, dr in [("混合·IS调优周期", sl(mix_is_tuned, OOS_A, OOS_B)),
                     ("混合·固定20d(基线)", sl(mix_fixed20, OOS_A, OOS_B)),
                     ("买入持有SPY", sl(px["SPY"].pct_change().dropna(), OOS_A, OOS_B)),
                     ("买入持有QQQ", sl(px["QQQ"].pct_change().dropna(), OOS_A, OOS_B))]:
        m = metr(dr)
        cmp.append({"策略": name, "OOS最终$": f"{m['final']:,.0f}",
                    "OOS总收益%": round((m['final']/CAP-1)*100, 1), "OOS年化%": round(m['cagr']*100, 2),
                    "OOS夏普": round(m['sharpe'], 2), "OOS最大回撤%": round(m['dd']*100, 1)})
    cmp_df = pd.DataFrame(cmp)
    print(cmp_df.to_string(index=False))

    # also full-sample mixed (IS-tuned) for reference
    print("\n混合·IS调优周期 全样本(2021起):")
    mf = metr(sl(mix_is_tuned, IS_A, OOS_B))
    print(f"  最终${mf['final']:,.0f}  年化{mf['cagr']*100:.2f}%  夏普{mf['sharpe']:.2f}  回撤{mf['dd']*100:.1f}%")

    # ---- OOS equity chart ----
    fig, ax = plt.subplots(figsize=(12, 7))
    for name, dr, c in [("混合·IS调优周期", sl(mix_is_tuned, OOS_A, OOS_B), "#1a9850"),
                        ("混合·固定20d", sl(mix_fixed20, OOS_A, OOS_B), "#f39c12"),
                        ("买入持有SPY", sl(px["SPY"].pct_change().dropna(), OOS_A, OOS_B), "#888"),
                        ("买入持有QQQ", sl(px["QQQ"].pct_change().dropna(), OOS_A, OOS_B), "#111")]:
        eq = CAP * (1 + dr).cumprod()
        ls = "--" if "买入" in name else "-"
        ax.plot(eq.index, eq.values, ls, color=c, lw=2.2, label=f"{name} → ${eq.iloc[-1]:,.0f}")
    ax.axhline(CAP, color="#aaa", lw=0.8, ls=":")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
    ax.set_title("样本外(2024-2026)检验: 混合周期(IS调优) vs 固定20d vs 基准  ·  $100k · top5", fontsize=12)
    ax.set_ylabel("组合价值 (OOS起点 $100,000)"); ax.grid(alpha=0.2); ax.legend(fontsize=9, loc="upper left")
    fig.tight_layout(); pth = os.path.join(OUT, "oos_validation.png")
    fig.savefig(pth, dpi=135); plt.close(fig)
    print("\nsaved:", pth)

    xlsx = os.path.join(OUT, "oos_validation.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        p1.to_excel(xw, sheet_name="单象限_最优周期_全样本", index=False)
        ydf.to_excel(xw, sheet_name="单象限_逐年", index=False)
        stab_df.to_excel(xw, sheet_name="周期稳定性_IS_vs_OOS", index=False)
        cmp_df.to_excel(xw, sheet_name="混合策略_OOS表现", index=False)
    print("saved:", xlsx)
    return p1, ydf, stab_df, cmp_df, pth


if __name__ == "__main__":
    main()
