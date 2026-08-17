# -*- coding: utf-8 -*-
"""
Fresh restart (no 策略1/2, no shorting/hedge).

A strategy is now defined ONLY by:
  * a set of RRG quadrants to hold  (single or a pair)
  * a holding period (rebalance every N trading days)

Rule: at each rebalance, hold EVERY sector ETF currently in the chosen quadrant(s),
equal-weight, long-only, until the next rebalance. T+1-open execution. If the
combo is momentarily empty, sit in cash for that period (no shorting).

Backtest from 2021 ($100k), RRG vs SPY, optimized params Z126/S8/M3.

Quadrants:  Q1领先 Lead | Q2改善 Impr | Q4转弱 Weak | Q3落后 Lag
"""
import os
import itertools
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

import fmp_data as fd
from rrg_model import RRGParams, build_rrg_panel

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
OUT = os.path.join(os.path.dirname(__file__), "output")

CAP = 100_000
START = "2021-01-01"
OPT = RRGParams(126, 8, 2.2, 3)
CN = {"Lead": "领先Q1", "Impr": "改善Q2", "Weak": "转弱Q4", "Lag": "落后Q3"}


def build_panel(px):
    return build_rrg_panel(px, list(fd.SECTORS.keys()), "SPY", OPT)


def combo_backtest(panel, opens, quads, rebalance, top_k=None):
    """Long-only, hold members whose state ∈ quads, equal weight, T+1 open.
    top_k=None -> hold ALL members of the quadrant(s); top_k=N -> keep the N
    highest-scoring (momentum-tilted) members. Returns (daily_ret, holdings_log)."""
    common = None
    for s in panel.values():
        common = set(s.index) if common is None else (common & set(s.index))
    dates = pd.DatetimeIndex(sorted(common))
    cl = {sym: panel[sym]["price"] for sym in panel}
    op = {sym: opens[sym] for sym in panel}

    def score(row):
        return (row["ratio"] - 100) + 1.5 * (row["mom"] - 100)

    daily = pd.Series(0.0, index=dates[1:])
    held = {}
    log = []
    for i in range(len(dates) - 1):
        d, dn = dates[i], dates[i + 1]
        if i % rebalance == 0:
            members = [sym for sym, s in panel.items() if s.loc[d, "state"] in quads]
            if top_k is not None and len(members) > top_k:
                members = sorted(members, key=lambda sym: score(panel[sym].loc[d]), reverse=True)[:top_k]
            new = {sym: 1.0 / len(members) for sym in members} if members else {}
            r = 0.0
            for sym, w in held.items():
                r += w * (op[sym].loc[dn] / cl[sym].loc[d] - 1)          # old into open
            for sym, w in new.items():
                r += w * (cl[sym].loc[dn] / op[sym].loc[dn] - 1)         # new open->close
            daily.loc[dn] = r
            held = new
            log.append({"date": d.date(), "n": len(members), "members": members})
        else:
            daily.loc[dn] = sum(w * (cl[sym].loc[dn] / cl[sym].loc[d] - 1) for sym, w in held.items())
    return daily, log


def perf(dr):
    n = len(dr); eq = (1 + dr).cumprod()
    cagr = eq.iloc[-1] ** (252 / n) - 1
    vol = dr.std() * np.sqrt(252)
    sharpe = (dr.mean() * 252) / vol if vol > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    return cagr, vol, sharpe, dd


def yearly(dr):
    return {y: round(((1 + s).prod() - 1) * 100, 1) for y, s in dr.groupby(dr.index.year)}


def trim(s):
    return s[s.index >= pd.Timestamp(START)]


def label(quads):
    return "+".join(CN[q] for q in ["Lead", "Impr", "Weak", "Lag"] if q in quads)


def main():
    px = fd.load_prices(fd.all_symbols())
    opens = fd.load_prices(fd.all_symbols(), field="open")
    panel = build_panel(px)

    singles = [("Lead",), ("Impr",), ("Weak",), ("Lag",)]
    pairs = [tuple(c) for c in itertools.combinations(["Lead", "Impr", "Weak", "Lag"], 2)]

    # ---- STEP 1: singles + pairs at 20d ----
    rows, books, yr = [], {}, {}
    for quads in singles + pairs:
        dr = trim(combo_backtest(panel, opens, set(quads), 20)[0])
        books[label(quads)] = dr
        cagr, vol, sharpe, dd = perf(dr)
        final = CAP * (1 + dr).prod()
        yr[label(quads)] = yearly(dr)
        rows.append({"组合": label(quads), "类型": "单象限" if len(quads) == 1 else "两象限",
                     "最终$": f"{final:,.0f}", "总收益%": round((final/CAP-1)*100, 1),
                     "年化%": round(cagr*100, 2), "波动%": round(vol*100, 1), "夏普": round(sharpe, 2),
                     "最大回撤%": round(dd*100, 1), "Calmar": round(cagr/abs(dd), 2)})
    for b in ["SPY", "QQQ"]:
        dr = trim(px[b].pct_change().dropna())
        cagr, vol, sharpe, dd = perf(dr)
        final = CAP * (1 + dr).prod()
        yr[f"买入持有{b}"] = yearly(dr)
        rows.append({"组合": f"买入持有{b}", "类型": "基准", "最终$": f"{final:,.0f}",
                     "总收益%": round((final/CAP-1)*100, 1), "年化%": round(cagr*100, 2),
                     "波动%": round(vol*100, 1), "夏普": round(sharpe, 2),
                     "最大回撤%": round(dd*100, 1), "Calmar": round(cagr/abs(dd), 2)})
    summary = pd.DataFrame(rows).sort_values("夏普", ascending=False)
    print(f"本金 ${CAP:,}  {trim(books[list(books)[0]]).index[0].date()} -> {trim(books[list(books)[0]]).index[-1].date()}  (20日换仓)")
    print(summary.to_string(index=False))

    yrs = sorted(set(books[list(books)[0]].index.year))
    ymat = pd.DataFrame({"组合": list(yr.keys()),
                         **{f"{y}{'*' if y in (2026,) else ''}": [yr[k].get(y, np.nan) for k in yr]
                            for y in yrs}})
    print("\n===== 逐年收益% (含基准) ====="); print(ymat.to_string(index=False))

    # ---- current holdings per quadrant ----
    asof = panel[list(panel)[0]].index[-1].date()
    cur = {q: [] for q in ["Lead", "Impr", "Weak", "Lag"]}
    for sym, s in panel.items():
        cur[s.iloc[-1]["state"]].append(f"{fd.SECTORS[sym]}{sym}")
    print(f"\n===== 当前各象限持仓 (截至 {asof}, vs SPY) =====")
    for q in ["Lead", "Impr", "Weak", "Lag"]:
        print(f"{CN[q]} ({len(cur[q])}个): {', '.join(cur[q]) if cur[q] else '—'}")

    # ---- $100k PnL chart: best pairs + singles + benchmarks ----
    plot_names = ["改善Q2+转弱Q4", "领先Q1+转弱Q4", "领先Q1+改善Q2", "转弱Q4", "改善Q2"]
    fig, ax = plt.subplots(figsize=(13, 7.5))
    palette = ["#1a9850", "#f39c12", "#d73027", "#9b59b6", "#4575b4"]
    for name, c in zip(plot_names, palette):
        if name in books:
            eq = CAP * (1 + books[name]).cumprod()
            ax.plot(eq.index, eq.values, color=c, lw=2.2, label=f"{name} → ${eq.iloc[-1]:,.0f}")
    for b, c in [("SPY", "#888"), ("QQQ", "#111")]:
        eq = CAP * (1 + trim(px[b].pct_change().dropna())).cumprod()
        ax.plot(eq.index, eq.values, "--", color=c, lw=2.0, label=f"买入持有{b} → ${eq.iloc[-1]:,.0f}")
    ax.axhline(CAP, color="#aaa", lw=0.8, ls=":")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
    ax.set_ylabel("组合价值 (本金 $100,000)")
    ax.set_title("两象限组合策略 PnL  ·  $100k · 2021起 · 20日换仓 · T+1开盘 · 无对冲", fontsize=12)
    ax.grid(alpha=0.2); ax.legend(fontsize=9, loc="upper left")
    fig.tight_layout(); p1 = os.path.join(OUT, "quad_combo_pnl.png")
    fig.savefig(p1, dpi=135); plt.close(fig)
    print("\nsaved:", p1)

    # ---- STEP 2: holding-period sweep for singles + all pairs ----
    print("\n===== 持有周期敏感性: 各组合在不同换仓周期下的 夏普 (年化%) =====")
    REBS = [5, 10, 15, 20, 25, 30]
    combos = singles + pairs
    hp_rows, sh_mat = [], np.full((len(combos), len(REBS)), np.nan)
    for i, quads in enumerate(combos):
        row = {"组合": label(quads)}
        best_sh, best_n = -9, None
        for j, n in enumerate(REBS):
            dr = trim(combo_backtest(panel, opens, set(quads), n)[0])
            cagr, vol, sharpe, dd = perf(dr)
            row[f"{n}d"] = f"{sharpe:.2f}({cagr*100:.0f}%)"
            sh_mat[i, j] = sharpe
            if sharpe > best_sh:
                best_sh, best_n = sharpe, n
        row["最佳周期"] = f"{best_n}d"
        hp_rows.append(row)
    hp = pd.DataFrame(hp_rows)
    print(hp.to_string(index=False))

    # ---- heatmap of Sharpe (combo × holding period) ----
    labels = [label(q) for q in combos]
    fig, ax = plt.subplots(figsize=(9, 8))
    im = ax.imshow(sh_mat, cmap="RdYlGn", aspect="auto", vmin=0.3, vmax=0.8)
    ax.set_xticks(range(len(REBS))); ax.set_xticklabels([f"{n}d" for n in REBS])
    ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels)
    for i in range(len(labels)):
        jbest = int(np.nanargmax(sh_mat[i]))
        for j in range(len(REBS)):
            txt = f"{sh_mat[i, j]:.2f}"
            ax.text(j, i, txt, ha="center", va="center", fontsize=8.5,
                    fontweight="bold" if j == jbest else "normal",
                    color="black")
            if j == jbest:
                ax.add_patch(plt.Rectangle((j-.5, i-.5), 1, 1, fill=False, edgecolor="#111", lw=2.2))
    ax.set_xlabel("持有周期 (换仓间隔)"); ax.set_title("各象限组合 × 持有周期 的夏普比率\n(黑框=该组合最佳周期)", fontsize=12)
    fig.colorbar(im, ax=ax, shrink=0.7, label="夏普")
    fig.tight_layout(); p2 = os.path.join(OUT, "quad_combo_holdperiod.png")
    fig.savefig(p2, dpi=135); plt.close(fig)
    print("saved:", p2)

    # ---- Excel ----
    xlsx = os.path.join(OUT, "quad_combo.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="全期汇总_20d", index=False)
        ymat.to_excel(xw, sheet_name="逐年收益", index=False)
        hp.to_excel(xw, sheet_name="持有周期敏感性", index=False)
        pd.DataFrame([{"象限": CN[q], "个数": len(cur[q]), "成分": ", ".join(cur[q])}
                      for q in ["Lead", "Impr", "Weak", "Lag"]]).to_excel(
            xw, sheet_name="当前持仓", index=False)
    print("saved:", xlsx)
    return summary, ymat, hp, cur, p1


if __name__ == "__main__":
    main()
