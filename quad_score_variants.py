# -*- coding: utf-8 -*-
"""
Per-quadrant × scoring-method backtest matrix.
For each quadrant (top-5 within it, 20d, 2021+, 20bps, T+1 close) under each
scoring method (score / mom / dist). Shows how the pick-ranking affects each
quadrant's strategy. Heatmap of Sharpe (quadrant × method) per universe.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import fmp_data as fd
import industry2 as ind2
import tech_data as td
from rrg_model import RRGParams
from rotation_backtest import StratConfig, run_strategy

OUT = os.path.join(os.path.dirname(__file__), "output")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
CAP = 100_000
START = pd.Timestamp("2021-01-01")
P = RRGParams(126, 8, 2.2, 3)
QUADS = ["Lead", "Impr", "Weak", "Lag"]
QCN = {"Lead": "领先Q1", "Impr": "改善Q2", "Weak": "转弱Q4", "Lag": "落后Q3"}
METHODS = ["score", "mom", "dist"]
MCN = {"score": "综合score", "mom": "纯动量", "dist": "距离dist"}


def run(px, op, sectors, bench, q, method):
    cfg = StratConfig(bench, 20, top_k=5, quad_filter=(q,), fill_mode="cash",
                      execution="t1_close", cost_per_turnover=0.002, params=P, rank_by=method)
    dr = run_strategy(px, sectors, cfg, op)["daily_ret"]
    dr = dr[dr.index >= START]
    eq = (1 + dr).cumprod(); n = len(dr)
    cagr = eq.iloc[-1] ** (252 / n) - 1
    vol = dr.std() * np.sqrt(252)
    sharpe = (dr.mean() * 252) / vol if vol > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    return dict(final=CAP * float(eq.iloc[-1]), cagr=cagr, sharpe=float(sharpe), dd=float(dd))


def block(px, op, sectors, bench, tag):
    sh = np.full((len(QUADS), len(METHODS)), np.nan)
    rows = []
    for i, q in enumerate(QUADS):
        for j, m in enumerate(METHODS):
            r = run(px, op, sectors, bench, q, m)
            sh[i, j] = r["sharpe"]
            rows.append({"象限": QCN[q], "打分": MCN[m], "夏普": round(r["sharpe"], 2),
                         "年化%": round(r["cagr"] * 100, 1), "最终$": f"{r['final']:,.0f}",
                         "回撤%": round(r["dd"] * 100, 1)})
    df = pd.DataFrame(rows)
    print(f"\n===== {tag} (vs {bench}) 每象限×打分 =====")
    print(df.pivot(index="象限", columns="打分", values="夏普").to_string())
    # heatmap
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    im = ax.imshow(sh, cmap="RdYlGn", aspect="auto", vmin=np.nanmin(sh), vmax=np.nanmax(sh))
    ax.set_xticks(range(len(METHODS))); ax.set_xticklabels([MCN[m] for m in METHODS])
    ax.set_yticks(range(len(QUADS))); ax.set_yticklabels([QCN[q] for q in QUADS])
    for i in range(len(QUADS)):
        jb = int(np.nanargmax(sh[i]))
        for j in range(len(METHODS)):
            ax.text(j, i, f"{sh[i,j]:.2f}", ha="center", va="center", fontsize=10,
                    fontweight="bold" if j == jb else "normal")
            if j == jb:
                ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, fill=False, edgecolor="#111", lw=2.4))
    ax.set_title(f"{tag}·各象限×打分方式 夏普 (vs {bench}, 20d, 2021+, 黑框=该象限最优打分)", fontsize=10.5)
    fig.colorbar(im, ax=ax, shrink=0.75, label="夏普")
    fig.tight_layout(); path = os.path.join(OUT, f"quadscore_{tag}.png")
    fig.savefig(path, dpi=135); plt.close(fig)
    print("saved", path)
    return df, path


def main():
    import pickle
    ip = fd.load_prices([ind2.BENCH] + ind2.all_tickers())
    io = fd.load_prices([ind2.BENCH] + ind2.all_tickers(), field="open")
    di, pi = block(ip, io, ind2.all_tickers(), "SPY", "行业")
    tsyms = td.all_tickers() + ["SOXX", "QQQ"]
    tp = fd.load_prices(tsyms); to = fd.load_prices(tsyms, field="open")
    stocks = [t for t in td.all_tickers() if t in tp.columns]
    dt, pt = block(tp, to, stocks, "SOXX", "科技")
    pickle.dump({"行业": {"df": di, "chart": pi, "bench": "SPY"},
                 "科技": {"df": dt, "chart": pt, "bench": "SOXX"}},
                open(os.path.join(OUT, "quadscore_results.pkl"), "wb"))
    print("saved quadscore_results.pkl")


if __name__ == "__main__":
    main()
