# -*- coding: utf-8 -*-
"""Add step-① extras (date window, PnL chart, yearly table) for the fixed-20d
per-quadrant holding backtest into final_results.pkl."""
import os
import pickle
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

import fmp_data as fd
import tech_data as td
from rotation_backtest import run_strategy
from final_pipeline import cfg, yearly, trim, QUADS, QCN, CAP, OUT


def pnl_chart(curves, title, path):
    fig, ax = plt.subplots(figsize=(12, 6.4))
    for name, eq in curves.items():
        ls = "--" if name.startswith("买入持有") else "-"
        lw = 2.6 if name.startswith("买入持有") else 1.9
        ax.plot(eq.index, eq.values, ls, lw=lw, label=f"{name} → ${eq.iloc[-1]:,.0f}")
    ax.axhline(CAP, color="#aaa", lw=.8, ls=":")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
    ax.set_title(title, fontsize=12); ax.set_ylabel("组合价值 ($100k起)")
    ax.grid(alpha=.2); ax.legend(fontsize=9, loc="upper left")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig); return path


def build_step2(px, op, sectors, bench, tag):
    curves, yr, dates = {}, {}, None
    for q in QUADS:
        dr = trim(run_strategy(px, sectors, cfg(bench, 20, (q,)), op)["daily_ret"])
        curves[QCN[q]] = CAP * (1 + dr).cumprod(); yr[QCN[q]] = yearly(dr); dates = dr.index
    bdr = trim(px[bench].pct_change().dropna())
    curves[f"买入持有{bench}"] = CAP * (1 + bdr).cumprod(); yr[f"买入持有{bench}"] = yearly(bdr)
    window = (str(dates[0].date()), str(dates[-1].date()))
    yrs = sorted({y for d in yr.values() for y in d})
    ymat = pd.DataFrame({"策略": list(yr.keys()),
                         **{f"{y}{'*' if y == 2026 else ''}": [yr[k].get(y) for k in yr] for y in yrs}})
    path = pnl_chart(curves, f"{tag}·各象限@20d holding PnL vs 买入持有{bench}  ({window[0]} ~ {window[1]})",
                     os.path.join(OUT, f"step2_{tag}.png"))
    return window, ymat, path


def main():
    R = pickle.load(open(os.path.join(OUT, "final_results.pkl"), "rb"))
    px_i = fd.load_prices(fd.all_symbols()); op_i = fd.load_prices(fd.all_symbols(), field="open")
    w, ym, p = build_step2(px_i, op_i, list(fd.SECTORS.keys()), "SPY", "行业")
    R["industry"].update(window=w, step2_ymat=ym); R["industry"]["charts"]["step2"] = p
    print("industry window", w)

    tsyms = td.all_tickers() + ["SOXX", "QQQ"]
    px_t = fd.load_prices(tsyms, field="close"); op_t = fd.load_prices(tsyms, field="open")
    stocks = [t for t in td.all_tickers() if t in px_t.columns]
    w, ym, p = build_step2(px_t, op_t, stocks, "SOXX", "科技")
    R["tech"].update(window=w, step2_ymat=ym); R["tech"]["charts"]["step2"] = p
    print("tech window", w)

    pickle.dump(R, open(os.path.join(OUT, "final_results.pkl"), "wb"))
    print("patched final_results.pkl")


if __name__ == "__main__":
    main()
