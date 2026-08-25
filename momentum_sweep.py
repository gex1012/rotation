# -*- coding: utf-8 -*-
"""
Is 'longer momentum lookback (L_M) is better' robust across regimes?
Fix MA params LR=250, S=10; sweep L_M in {20,40,60,80,100}. Measure OOS Sharpe
in two windows: 2022+ (split A OOS) and 2024+ (split B OOS), for the all-quadrant
top-5 rotation and the Q4-only strategy, on 行业(SPY) and 科技(SOXX).
No IS selection — each L_M is measured directly in each window (cross-regime test).
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
from rrg_model import RRGParams, build_rrg_panel
import walkforward as wf

OUT = os.path.join(os.path.dirname(__file__), "output")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

LMS = [20, 40, 60, 80, 100]
LR, S = 250, 10
ALL = {"Lead", "Impr", "Weak", "Lag"}
W22 = pd.Timestamp("2022-01-01")
W24 = pd.Timestamp("2024-01-01")


def sh_win(dr, a):
    d = dr[dr.index >= a]
    return wf.sharpe(d)


def block(px, op, sectors, bench, tag):
    first_px = {s: px[s].first_valid_index() for s in sectors if s in px.columns}
    rows = []
    for lm in LMS:
        p = RRGParams(model="ma", lr=LR, lm=lm, ma_smooth=S)
        pn = build_rrg_panel(px, sectors, bench, p)
        dates = pd.DatetimeIndex(sorted(set().union(*[set(s.index) for s in pn.values()])))
        for sname, quads in [("全象限top5", ALL), ("转弱Q4", {"Weak"})]:
            dr = wf.run_on_panel(pn, op, first_px, dates, quads, 20)
            rows.append({"L_M": lm, "策略": sname,
                         "夏普_2022+": round(sh_win(dr, W22), 2),
                         "夏普_2024+": round(sh_win(dr, W24), 2)})
    df = pd.DataFrame(rows)
    print(f"\n===== {tag} (vs {bench}) MA · LR={LR} S={S} · L_M 扫描 =====")
    for s in ["全象限top5", "转弱Q4"]:
        print(df[df["策略"] == s].to_string(index=False))
    return df


def chart(dfs):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), sharey=False)
    styles = {"行业": "-o", "科技": "-s"}
    colors = {"2022+": "#1f6feb", "2024+": "#f39c12"}
    for ax, sname in zip(axes, ["全象限top5", "转弱Q4"]):
        for tag, df in dfs.items():
            d = df[df["策略"] == sname]
            ax.plot(d["L_M"], d["夏普_2022+"], styles[tag], color=colors["2022+"],
                    label=f"{tag}·2022+(划分A)")
            ax.plot(d["L_M"], d["夏普_2024+"], styles[tag], color=colors["2024+"],
                    label=f"{tag}·2024+(划分B)")
        ax.set_title(f"{sname} · L_M vs OOS夏普", fontsize=12)
        ax.set_xlabel("L_M (动量回溯天数)"); ax.set_ylabel("OOS 夏普")
        ax.set_xticks(LMS); ax.grid(alpha=.25); ax.legend(fontsize=8)
    fig.suptitle("动量回溯 L_M 敏感性 · MA RRG (LR=250,S=10) · 两 OOS 窗口", fontsize=13)
    fig.tight_layout(); path = os.path.join(OUT, "momentum_sweep.png")
    fig.savefig(path, dpi=135); plt.close(fig)
    print("saved", path); return path


def main():
    ip = fd.load_prices([ind2.BENCH] + ind2.all_tickers())
    io = fd.load_prices([ind2.BENCH] + ind2.all_tickers(), field="open")
    di = block(ip, io, ind2.all_tickers(), "SPY", "行业")
    tsyms = td.all_tickers() + ["SOXX", "QQQ"]
    tp = fd.load_prices(tsyms); to = fd.load_prices(tsyms, field="open")
    stocks = [t for t in td.all_tickers() if t in tp.columns]
    dt = block(tp, to, stocks, "SOXX", "科技")
    chart({"行业": di, "科技": dt})
    import pickle
    pickle.dump({"行业": di, "科技": dt}, open(os.path.join(OUT, "momentum_sweep.pkl"), "wb"))


if __name__ == "__main__":
    main()
