# -*- coding: utf-8 -*-
"""
Drawdown attribution per strategy. For each quadrant (top-5, 20d, 2021+, MA RRG)
in 行业(vs SPY) and 科技(vs SOXX): max-drawdown depth, peak/trough/recovery dates,
worst single month, and an underwater (drawdown) chart. Plus benchmark.
"""
import os
import pickle
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
START = pd.Timestamp("2021-01-01")
P = RRGParams(model="ma", lr=250, lm=60, ma_smooth=10)   # robust MA (L_M=60 sweet spot)
QUADS = ["Lead", "Impr", "Weak", "Lag"]
QCN = {"Lead": "领先Q1", "Impr": "改善Q2", "Weak": "转弱Q4", "Lag": "落后Q3"}
QCOL = {"Lead": "#1a9850", "Impr": "#4575b4", "Weak": "#f39c12", "Lag": "#d73027"}


def dd_stats(dr):
    eq = (1 + dr).cumprod()
    peak = eq.cummax()
    dd = eq / peak - 1
    trough = dd.idxmin(); depth = dd.min()
    peak_dt = eq[:trough].idxmax()
    rec = eq[trough:][eq[trough:] >= eq.loc[peak_dt]]
    rec_dt = rec.index[0] if len(rec) else None
    # worst calendar month
    mret = (1 + dr).resample("ME").prod() - 1
    wm = mret.idxmin(); wmv = mret.min()
    return dict(depth=depth, peak=peak_dt, trough=trough, rec=rec_dt, dd=dd,
               worst_month=wm, worst_month_ret=wmv)


def run_q(px, op, sectors, bench, q):
    cfg = StratConfig(bench, 20, top_k=5, quad_filter=(q,), fill_mode="cash",
                      execution="t1_close", cost_per_turnover=0.002, params=P, rank_by="score")
    dr = run_strategy(px, sectors, cfg, op)["daily_ret"]
    return dr[dr.index >= START]


def block(px, op, sectors, bench, tag):
    rows, dds = [], {}
    for q in QUADS:
        dr = run_q(px, op, sectors, bench, q)
        s = dd_stats(dr); dds[q] = s
        rows.append({"策略": QCN[q], "最大回撤%": round(s["depth"] * 100, 1),
                     "峰值日": str(s["peak"].date()), "谷底日": str(s["trough"].date()),
                     "回补日": str(s["rec"].date()) if s["rec"] is not None else "未回补",
                     "最差月": f"{s['worst_month'].strftime('%Y-%m')} ({s['worst_month_ret']*100:.0f}%)"})
    bdr = px[bench].pct_change().dropna(); bdr = bdr[bdr.index >= START]
    bs = dd_stats(bdr)
    rows.append({"策略": f"买入持有{bench}", "最大回撤%": round(bs["depth"] * 100, 1),
                 "峰值日": str(bs["peak"].date()), "谷底日": str(bs["trough"].date()),
                 "回补日": str(bs["rec"].date()) if bs["rec"] is not None else "未回补",
                 "最差月": f"{bs['worst_month'].strftime('%Y-%m')} ({bs['worst_month_ret']*100:.0f}%)"})
    df = pd.DataFrame(rows)
    print(f"\n===== {tag} (vs {bench}) 回撤剖析 (MA·LR250/LM60/S10, 20d, 2021+) =====")
    print(df.to_string(index=False))
    # underwater chart
    fig, ax = plt.subplots(figsize=(12, 5.5))
    for q in QUADS:
        d = dds[q]["dd"]
        ax.plot(d.index, d.values * 100, color=QCOL[q], lw=1.5, label=f"{QCN[q]} (谷{dds[q]['depth']*100:.0f}%)")
    ax.plot(bs["dd"].index, bs["dd"].values * 100, color="#111", lw=2, ls="--", label=f"买入持有{bench} (谷{bs['depth']*100:.0f}%)")
    ax.set_title(f"{tag}·各象限水下回撤曲线 (drawdown, vs {bench})", fontsize=12)
    ax.set_ylabel("回撤 %"); ax.grid(alpha=.25); ax.legend(fontsize=9, loc="lower left")
    fig.tight_layout(); path = os.path.join(OUT, f"drawdown_{tag}.png")
    fig.savefig(path, dpi=130); plt.close(fig)
    print("saved", path)
    return df, path, dds


def main():
    ip = fd.load_prices([ind2.BENCH] + ind2.all_tickers())
    io = fd.load_prices([ind2.BENCH] + ind2.all_tickers(), field="open")
    di, pi, ddi = block(ip, io, ind2.all_tickers(), "SPY", "行业")
    tsyms = td.all_tickers() + ["SOXX", "QQQ"]
    tp = fd.load_prices(tsyms); to = fd.load_prices(tsyms, field="open")
    stocks = [t for t in td.all_tickers() if t in tp.columns]
    dt, pt, ddt = block(tp, to, stocks, "SOXX", "科技")
    pickle.dump({"行业": {"df": di, "chart": pi}, "科技": {"df": dt, "chart": pt}},
                open(os.path.join(OUT, "drawdown_results.pkl"), "wb"))
    print("saved drawdown_results.pkl")


if __name__ == "__main__":
    main()
