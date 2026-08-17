# -*- coding: utf-8 -*-
"""Consolidated view: parameter-selection IS-Sharpe heatmaps + why-MA-beats-EMA
diagnostics. Reuses walkforward internals."""
import os
import pickle
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import fmp_data as fd
import tech_data as td
from rrg_model import build_rrg_panel
import walkforward as wf

OUT = os.path.join(os.path.dirname(__file__), "output")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def short_tag(p):
    return (f"Z{p.zwin}/M{p.mom_lag}" if p.model == "ema"
            else f"R{p.lr}/M{p.lm}")


def is_sharpe_grid(px, op, sectors, bench, grid):
    """IS(2018-21) Sharpe per (quadrant x param) at holding=20."""
    first_px = {s: px[s].first_valid_index() for s in sectors if s in px.columns}
    cols = [short_tag(p) for p in grid]
    mat = np.full((len(wf.QUADS), len(grid)), np.nan)
    for j, p in enumerate(grid):
        pn = build_rrg_panel(px, sectors, bench, p)
        if not pn:
            continue
        dates = pd.DatetimeIndex(sorted(set().union(*[set(s.index) for s in pn.values()])))
        for i, q in enumerate(wf.QUADS):
            dr = wf.run_on_panel(pn, op, first_px, dates, (q,), 20)
            mat[i, j] = wf.sharpe(wf.IS(dr))
    return mat, cols


def heatmap(mat, cols, title, path):
    fig, ax = plt.subplots(figsize=(1.2 * len(cols) + 3, 4.2))
    im = ax.imshow(mat, cmap="RdYlGn", aspect="auto",
                   vmin=np.nanmin(mat), vmax=np.nanmax(mat))
    ax.set_xticks(range(len(cols))); ax.set_xticklabels(cols, fontsize=9)
    ax.set_yticks(range(len(wf.QUADS))); ax.set_yticklabels([wf.QCN[q] for q in wf.QUADS])
    for i in range(len(wf.QUADS)):
        jb = int(np.nanargmax(mat[i]))
        for j in range(len(cols)):
            ax.text(j, i, f"{mat[i,j]:.2f}", ha="center", va="center", fontsize=8.5,
                    fontweight="bold" if j == jb else "normal")
            if j == jb:
                ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, fill=False, edgecolor="#111", lw=2.2))
    ax.set_title(title + "\n(IS 2018-21 夏普, holding=20, 黑框=选中的最优参数)", fontsize=11)
    fig.colorbar(im, ax=ax, shrink=0.7, label="IS 夏普")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig); return path


def main():
    R = pickle.load(open(os.path.join(OUT, "walkforward_results.pkl"), "rb"))
    px_i = fd.load_prices(fd.all_symbols()); op_i = fd.load_prices(fd.all_symbols(), field="open")
    tsyms = td.all_tickers() + ["SOXX", "QQQ"]
    px_t = fd.load_prices(tsyms, field="close"); op_t = fd.load_prices(tsyms, field="open")
    stocks = [t for t in td.all_tickers() if t in px_t.columns]

    charts = {}
    for tag, px, op, sec, bench in [("行业", px_i, op_i, list(fd.SECTORS.keys()), "SPY"),
                                    ("科技", px_t, op_t, stocks, "SOXX")]:
        for mtag, grid in [("EMA", wf.EMA_GRID), ("MA", wf.MA_GRID)]:
            mat, cols = is_sharpe_grid(px, op, sec, bench, grid)
            p = heatmap(mat, cols, f"{tag} · {mtag} RRG 参数选择 (vs {bench})",
                        os.path.join(OUT, f"paramheat_{tag}_{mtag}.png"))
            charts[f"{tag}_{mtag}"] = p
            print("saved", p)

    # consolidated params + OOS + yearly (printed for the writeup)
    for key in ["SPY", "SOXX"]:
        B = R[key]
        print(f"\n===== {B['tag']} 选参汇总 (Step1) =====")
        for m in ["EMA", "MA"]:
            df = B[m]["step1"][["策略", "最优参数", "最优holding", "OOS夏普", "OOS最终$"]].copy()
            df.insert(0, "模型", m)
            print(df.to_string(index=False))
    pickle.dump(charts, open(os.path.join(OUT, "paramheat_charts.pkl"), "wb"))
    print("\nsaved paramheat_charts.pkl")


if __name__ == "__main__":
    main()
