# -*- coding: utf-8 -*-
"""
Mixed-holding-period strategy: run each quadrant sleeve at ITS OWN optimal
rebalance period, then combine (equal capital per sleeve, let them drift).

From the holding-period heatmap:
  领先Q1 -> 5d   |  改善Q2 -> 20d  |  转弱Q4 -> 30d  |  落后Q3 -> 30d

Variants:
  Mix3  = Q1@5d + Q4@30d + Q3@30d              (user's spec, drops Q2)
  Mix4  = Q1@5d + Q2@20d + Q4@30d + Q3@30d     (all four at optimal)
Each in two holding modes: 持有全部成分 (top_k=None) / 每象限top-5 (top_k=5).

$100k, 2021 start, T+1 open, long-only (no shorting).
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

import fmp_data as fd
from quad_combo import build_panel, combo_backtest, perf, yearly, trim, CAP, START, CN

OUT = os.path.join(os.path.dirname(__file__), "output")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# sleeve = (quadrant state, optimal rebalance)
SLEEVES3 = [("Lead", 5), ("Weak", 30), ("Lag", 30)]
SLEEVES4 = [("Lead", 5), ("Impr", 20), ("Weak", 30), ("Lag", 30)]


def mix_equity(panel, opens, sleeves, top_k):
    """Equal initial capital per sleeve, drift (no cross-sleeve rebalancing)."""
    eqs = []
    for q, reb in sleeves:
        dr = trim(combo_backtest(panel, opens, {q}, reb, top_k=top_k)[0])
        eqs.append((1 + dr).cumprod())
    idx = eqs[0].index
    total = sum(e.reindex(idx).ffill() for e in eqs) / len(eqs)
    return total.pct_change().dropna()


def row(name, dr):
    cagr, vol, sharpe, dd = perf(dr)
    final = CAP * (1 + dr).prod()
    return {"策略": name, "最终$": f"{final:,.0f}", "总收益%": round((final/CAP-1)*100, 1),
            "年化%": round(cagr*100, 2), "波动%": round(vol*100, 1), "夏普": round(sharpe, 2),
            "最大回撤%": round(dd*100, 1), "Calmar": round(cagr/abs(dd), 2)}, dr


def main():
    px = fd.load_prices(fd.all_symbols())
    opens = fd.load_prices(fd.all_symbols(), field="open")
    panel = build_panel(px)

    strategies = {}
    for tag, tk in [("持全部成分", None), ("每象限top5", 5)]:
        strategies[f"混合3(Q1@5+Q4@30+Q3@30)·{tag}"] = mix_equity(panel, opens, SLEEVES3, tk)
        strategies[f"混合4(+Q2@20)·{tag}"] = mix_equity(panel, opens, SLEEVES4, tk)
    # reference: best fixed combo from step2, and momentum pair
    strategies["转弱Q4+落后Q3@15d(持全部)"] = trim(combo_backtest(panel, opens, {"Weak", "Lag"}, 15)[0])
    strategies["领先Q1+改善Q2@20d(持全部)"] = trim(combo_backtest(panel, opens, {"Lead", "Impr"}, 20)[0])

    rows, books, yr = [], {}, {}
    for name, dr in strategies.items():
        r, d = row(name, dr); rows.append(r); books[name] = d; yr[name] = yearly(d)
    for b in ["SPY", "QQQ"]:
        dr = trim(px[b].pct_change().dropna())
        r, d = row(f"买入持有{b}", dr); rows.append(r); yr[f"买入持有{b}"] = yearly(d)
    summary = pd.DataFrame(rows).sort_values("夏普", ascending=False)
    print(f"本金 ${CAP:,}  {trim(list(books.values())[0]).index[0].date()} -> {list(books.values())[0].index[-1].date()}")
    print(summary.to_string(index=False))

    yrs = sorted(set(list(books.values())[0].index.year))
    ymat = pd.DataFrame({"策略": list(yr.keys()),
                         **{f"{y}{'*' if y in (2026,) else ''}": [yr[k].get(y, np.nan) for k in yr]
                            for y in yrs}})
    print("\n===== 逐年收益% (含基准) ====="); print(ymat.to_string(index=False))

    # current holdings of the mixed strategy sleeves (top5 & all)
    asof = panel[list(panel)[0]].index[-1]
    def score(row_):
        return (row_["ratio"] - 100) + 1.5 * (row_["mom"] - 100)
    print(f"\n===== 混合策略当前持仓 (截至 {asof.date()}) =====")
    for q, reb in SLEEVES4:
        mem = [(sym, score(panel[sym].loc[asof])) for sym, s in panel.items()
               if s.loc[asof, "state"] == q]
        mem.sort(key=lambda x: -x[1])
        alln = [f"{fd.SECTORS[s]}{s}" for s, _ in mem]
        top5 = [f"{fd.SECTORS[s]}{s}" for s, _ in mem[:5]]
        print(f"{CN[q]}@{reb}d  全部({len(alln)}): {', '.join(alln)}")
        print(f"          top5: {', '.join(top5)}")

    # ---- $100k PnL chart ----
    plot = ["混合3(Q1@5+Q4@30+Q3@30)·持全部成分", "混合4(+Q2@20)·持全部成分",
            "混合3(Q1@5+Q4@30+Q3@30)·每象限top5", "转弱Q4+落后Q3@15d(持全部)",
            "领先Q1+改善Q2@20d(持全部)"]
    colors = ["#1a9850", "#16a085", "#27ae60", "#f39c12", "#d73027"]
    fig, ax = plt.subplots(figsize=(13, 7.5))
    for name, c in zip(plot, colors):
        if name in books:
            eq = CAP * (1 + books[name]).cumprod()
            ax.plot(eq.index, eq.values, color=c, lw=2.2, label=f"{name} → ${eq.iloc[-1]:,.0f}")
    for b, c in [("SPY", "#888"), ("QQQ", "#111")]:
        eq = CAP * (1 + trim(px[b].pct_change().dropna())).cumprod()
        ax.plot(eq.index, eq.values, "--", color=c, lw=2.0, label=f"买入持有{b} → ${eq.iloc[-1]:,.0f}")
    ax.axhline(CAP, color="#aaa", lw=0.8, ls=":")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
    ax.set_ylabel("组合价值 (本金 $100,000)")
    ax.set_title("混合持有周期策略 PnL  ·  Q1@5d + Q4@30d + Q3@30d(±Q2@20d)  ·  $100k · 2021起 · 无对冲", fontsize=12)
    ax.grid(alpha=0.2); ax.legend(fontsize=8.5, loc="upper left")
    fig.tight_layout(); p1 = os.path.join(OUT, "mixed_period_pnl.png")
    fig.savefig(p1, dpi=135); plt.close(fig)
    print("\nsaved:", p1)

    xlsx = os.path.join(OUT, "mixed_period.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="全期汇总", index=False)
        ymat.to_excel(xw, sheet_name="逐年收益", index=False)
    print("saved:", xlsx)
    return summary, ymat, p1


if __name__ == "__main__":
    main()
