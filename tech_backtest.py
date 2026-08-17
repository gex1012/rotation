# -*- coding: utf-8 -*-
"""
Tech backtests vs QQQ (long-only, T+1 open, from 2021, $100k):
  A. sub-sector rotation  -- 21 synthetic sub-sector indices, top-5 by RRG score
  B. stock rotation       -- 129 stocks, top-10 by RRG score
Both rebalanced 20d. Saves metrics/curves + a sub-sector RRG chart for the PDF.
"""
import os
import pickle
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

import fmp_data as fd
import tech_data as td
from rrg_model import RRGParams, build_rrg_panel, QUAD_QUADRANT
from rotation_backtest import StratConfig, run_strategy, benchmark_curve

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
OUT = os.path.join(os.path.dirname(__file__), "output")
CAP = 100_000
START = "2021-01-01"
BENCH = "QQQ"
PARAMS = RRGParams(126, 8, 2.2, 3)
QCOL = {"Lead": "#22c55e", "Impr": "#3b82f6", "Weak": "#f59e0b", "Lag": "#ef4444"}


def synth_frames(px, opens):
    """Equal-weight rebased synthetic close/open index per sub-sector (+ QQQ passthrough)."""
    cl, op = {}, {}
    for sub, grp in td.TECH.items():
        avail = [t for t in grp if t in px.columns and px[t].dropna().shape[0] > 200]
        if len(avail) < 2:
            continue
        base = px[avail].bfill().iloc[0]
        cl[sub] = (px[avail] / base * 100).mean(axis=1)
        op[sub] = (opens[avail] / base * 100).mean(axis=1)
    cl[BENCH] = px[BENCH]; op[BENCH] = opens[BENCH]
    return pd.DataFrame(cl).ffill(limit=3), pd.DataFrame(op).ffill(limit=3)


def metr(dr):
    n = len(dr); eq = (1 + dr).cumprod()
    cagr = eq.iloc[-1] ** (252 / n) - 1
    vol = dr.std() * np.sqrt(252)
    sharpe = (dr.mean() * 252) / vol if vol > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    return {"final": CAP * (1 + dr).prod(), "cagr": cagr, "vol": vol, "sharpe": sharpe, "dd": dd}


def yearly(dr):
    return {y: round(((1 + s).prod() - 1) * 100, 1) for y, s in dr.groupby(dr.index.year)}


def mrow(name, dr):
    m = metr(dr)
    return {"策略": name, "最终$": f"{m['final']:,.0f}", "总收益%": round((m['final']/CAP-1)*100, 1),
            "年化%": round(m['cagr']*100, 2), "波动%": round(m['vol']*100, 1),
            "夏普": round(m['sharpe'], 2), "最大回撤%": round(m['dd']*100, 1),
            "Calmar": round(m['cagr']/abs(m['dd']), 2)}


def trim(s):
    return s[s.index >= pd.Timestamp(START)]


def main():
    px = td.load("close"); opens = td.load("open")
    cl_syn, op_syn = synth_frames(px, opens)
    subs = [c for c in cl_syn.columns if c != BENCH]

    # A. sub-sector rotation top-5
    res_sub = run_strategy(cl_syn, subs, StratConfig(BENCH, 20, top_k=5, params=PARAMS), op_syn)
    dr_sub = trim(res_sub["daily_ret"])
    # B. stock rotation top-10
    stocks = [t for t in td.all_tickers() if t in px.columns]
    res_stk = run_strategy(px, stocks, StratConfig(BENCH, 20, top_k=10, params=PARAMS), opens)
    dr_stk = trim(res_stk["daily_ret"])
    # benchmark
    dr_qqq = trim(px[BENCH].pct_change().dropna())

    rows = [mrow("科技子板块轮动(top5,20d)", dr_sub),
            mrow("科技个股轮动(top10,20d)", dr_stk),
            mrow("买入持有QQQ", dr_qqq)]
    summary = pd.DataFrame(rows)
    print(summary.to_string(index=False))

    yrs = sorted(set(dr_sub.index.year))
    ymat = pd.DataFrame({"策略": ["子板块轮动", "个股轮动", "买入持有QQQ"],
                         **{f"{y}{'*' if y==2026 else ''}":
                            [yearly(dr_sub).get(y), yearly(dr_stk).get(y), yearly(dr_qqq).get(y)]
                            for y in yrs}})
    print("\n逐年%:"); print(ymat.to_string(index=False))

    # current holdings of both strategies
    hold_sub = res_sub["holdings"][-1]
    hold_stk = res_stk["holdings"][-1]
    print("\n子板块当前持仓:", hold_sub["picks"])
    print("个股当前持仓:", hold_stk["picks"])

    # ---- PnL chart ----
    fig, ax = plt.subplots(figsize=(12, 7))
    for name, dr, c in [("科技子板块轮动 top5", dr_sub, "#38bdf8"),
                        ("科技个股轮动 top10", dr_stk, "#22c55e"),
                        ("买入持有 QQQ", dr_qqq, "#111")]:
        eq = CAP * (1 + dr).cumprod()
        ls = "--" if "QQQ" in name else "-"
        ax.plot(eq.index, eq.values, ls, color=c, lw=2.3, label=f"{name} → ${eq.iloc[-1]:,.0f}")
    ax.axhline(CAP, color="#aaa", lw=.8, ls=":")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
    ax.set_title("科技轮动策略 PnL vs QQQ · $100k · 2021起 · T+1开盘", fontsize=13)
    ax.set_ylabel("组合价值 ($100,000起)"); ax.grid(alpha=.2); ax.legend(fontsize=10, loc="upper left")
    fig.tight_layout(); p_pnl = os.path.join(OUT, "tech_pnl.png"); fig.savefig(p_pnl, dpi=135); plt.close(fig)

    # ---- sub-sector RRG scatter (matplotlib, for PDF) ----
    panel = build_rrg_panel(cl_syn, subs, BENCH, PARAMS)
    fig, ax = plt.subplots(figsize=(11, 9))
    rr = [panel[s].iloc[-1]["ratio"] for s in panel]; mm = [panel[s].iloc[-1]["mom"] for s in panel]
    xmin, xmax = min(96, *rr)-.5, max(104, *rr)+.5; ymin, ymax = min(96, *mm)-.5, max(104, *mm)+.5
    ax.axhline(100, color="#888", lw=1); ax.axvline(100, color="#888", lw=1)
    ax.fill_between([100, xmax], 100, ymax, color="#22c55e", alpha=.06)
    ax.fill_between([xmin, 100], 100, ymax, color="#3b82f6", alpha=.06)
    ax.fill_between([xmin, 100], ymin, 100, color="#ef4444", alpha=.06)
    ax.fill_between([100, xmax], ymin, 100, color="#f59e0b", alpha=.07)
    for s in panel:
        last = panel[s].iloc[-1]; seg = panel[s].iloc[-8:]
        col = QCOL[last["state"]]
        strengthening = last["mom"] >= 100 and last["dMom5"] > 0
        ax.plot(seg["ratio"], seg["mom"], "-", color=col, alpha=.4, lw=1.2)
        ax.scatter(last["ratio"], last["mom"], s=200, color=col,
                   edgecolors="#DAA520" if strengthening else "white", linewidths=2.5 if strengthening else 1, zorder=5)
        ax.annotate(s, (last["ratio"], last["mom"]), xytext=(6, 5), textcoords="offset points", fontsize=8.5, weight="bold")
    ax.set_title(f"科技子板块 RRG 四象限 · 基准 QQQ · 截至 {res_sub['dates'][-1].date()}\n金边=仍在走强", fontsize=12)
    ax.set_xlabel("JdK RS-Ratio →"); ax.set_ylabel("JdK RS-Momentum ↑")
    ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax); ax.grid(alpha=.15)
    fig.tight_layout(); p_rrg = os.path.join(OUT, "tech_subsector_rrg.png"); fig.savefig(p_rrg, dpi=130); plt.close(fig)

    xlsx = os.path.join(OUT, "tech_backtest.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="回测汇总", index=False)
        ymat.to_excel(xw, sheet_name="逐年收益", index=False)
    snap = json_load()
    results = {"summary": summary, "ymat": ymat, "hold_sub": hold_sub["picks"],
               "hold_stk": hold_stk["picks"], "charts": {"pnl": p_pnl, "rrg": p_rrg},
               "asof": snap["asof"], "n_stocks": len(snap["stocks"]), "n_subs": len(snap["subs"]),
               "snap": snap}
    pickle.dump(results, open(os.path.join(OUT, "tech_results.pkl"), "wb"))
    print(f"\nsaved: {p_pnl}\nsaved: {p_rrg}\nsaved: {xlsx}\nsaved: tech_results.pkl")
    return results


def json_load():
    import json
    return json.load(open(os.path.join(OUT, "tech_rrg.json"), encoding="utf-8"))


if __name__ == "__main__":
    main()
