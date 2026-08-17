# -*- coding: utf-8 -*-
"""
Orchestrator: runs the full study and writes all deliverables.

Outputs (into ./output):
  * rotation_backtest.xlsx  -- every table + equity curves + current holdings
  * rrg_quadrant_SPY.png    -- current four-quadrant RRG snapshot (vs SPY)
  * rrg_quadrant_QQQ.png    -- current four-quadrant RRG snapshot (vs QQQ)
  * console tables (main grid, quad-12 grid, parameter sweep, trend readout)

Study layers:
  A. Main grid    : bench[SPY,QQQ] x rebalance[5,10,15,20,25,30], base params,
                    "ALL" selection (top-5 by score). + buy&hold baselines.
  B. Quad-1/2 grid: same grid but candidates restricted to Q1+Q2 (Mom>=100).
  C. Param sweep  : bench=SPY, rebalance=20, ZWIN x SMOOTH x MOM_LAG grid.
"""
import os
import itertools
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import fmp_data as fd
from rrg_model import RRGParams, build_rrg_panel, QUAD_CN, QUAD_QUADRANT
from rotation_backtest import StratConfig, run_strategy, benchmark_curve, benchmark_metrics

warnings.filterwarnings("ignore")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

OUT = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT, exist_ok=True)

REBALANCES = [5, 10, 15, 20, 25, 30]
BENCHES = ["SPY", "QQQ"]
TOP_K = 5
BASE = RRGParams()                                   # 默认 Z63/S8/M5
OPTIMIZED = RRGParams(zwin=126, smooth=8, mom_lag=3)  # 参数扫描胜出组

QUAD_COLOR = {"Lead": "#1a9850", "Impr": "#4575b4", "Weak": "#fdae61", "Lag": "#d73027"}


def metrics_row(label, m, bench_cagr=None):
    row = {
        "策略": label,
        "总收益%": round(m["total_return"] * 100, 1),
        "年化%": round(m["cagr"] * 100, 2),
        "波动%": round(m["vol"] * 100, 1),
        "夏普": round(m["sharpe"], 2),
        "索提诺": round(m["sortino"], 2),
        "最大回撤%": round(m["max_dd"] * 100, 1),
        "Calmar": round(m["calmar"], 2) if not np.isnan(m["calmar"]) else None,
        "周期胜率%": round(m["win_rate"] * 100, 1) if not np.isnan(m["win_rate"]) else None,
        "平均换手": round(m["avg_turnover"], 2),
        "换仓次数": m["n_rebalances"],
    }
    if bench_cagr is not None:
        row["超额年化%"] = round((m["cagr"] - bench_cagr) * 100, 2)
    return row


def run_grid(px, opens, sectors, quad12_only, params=BASE):
    rows, curves = [], {}
    bench_cagrs = {}
    for bench in BENCHES:
        # baseline calendar comes from a representative run to align buy&hold metrics
        base_res = run_strategy(px, sectors, StratConfig(bench=bench, rebalance=20,
                                                         top_k=TOP_K, params=params), opens)
        bm = benchmark_metrics(px, bench, base_res["dates"], 20)
        bench_cagrs[bench] = bm["cagr"]
    for bench in BENCHES:
        for reb in REBALANCES:
            cfg = StratConfig(bench=bench, rebalance=reb, top_k=TOP_K,
                              quad12_only=quad12_only, params=params)
            res = run_strategy(px, sectors, cfg, opens)
            rows.append(metrics_row(cfg.label(), res["metrics"], bench_cagrs[bench]))
            curves[cfg.label()] = res["equity"]
    # buy & hold baselines on a common calendar
    ref_dates = run_strategy(px, sectors, StratConfig(bench="SPY", rebalance=20,
                                                      top_k=TOP_K, params=params), opens)["dates"]
    for bench in BENCHES:
        bm = benchmark_metrics(px, bench, ref_dates, 20)
        rows.append(metrics_row(f"买入持有 {bench}", bm))
        curves[f"买入持有 {bench}"] = benchmark_curve(px, bench, ref_dates)
    return pd.DataFrame(rows), curves


def run_param_sweep(px, opens, sectors):
    zwins = [21, 42, 63, 126]
    smooths = [3, 8, 13]
    momlags = [3, 5, 10]
    rows = []
    for zw, sm, ml in itertools.product(zwins, smooths, momlags):
        p = RRGParams(zwin=zw, smooth=sm, mom_lag=ml)
        cfg = StratConfig(bench="SPY", rebalance=20, top_k=TOP_K, params=p)
        try:
            res = run_strategy(px, sectors, cfg, opens)
        except Exception as e:
            continue
        m = res["metrics"]
        rows.append({
            "ZWIN": zw, "SMOOTH": sm, "MOM_LAG": ml,
            "年化%": round(m["cagr"] * 100, 2),
            "夏普": round(m["sharpe"], 2),
            "最大回撤%": round(m["max_dd"] * 100, 1),
            "Calmar": round(m["calmar"], 2) if not np.isnan(m["calmar"]) else None,
            "周期胜率%": round(m["win_rate"] * 100, 1),
            "平均换手": round(m["avg_turnover"], 2),
        })
    return pd.DataFrame(rows).sort_values("夏普", ascending=False).reset_index(drop=True)


def current_snapshot(px, sectors, bench):
    """Latest RRG position for each sector vs `bench`, plus a trend read."""
    panel = build_rrg_panel(px, sectors, bench, BASE)
    rows = []
    for sym, s in panel.items():
        last = s.iloc[-1]
        strengthening = (last["mom"] >= 100 and last["dMom5"] > 0)  # top-half & accelerating
        rows.append({
            "symbol": sym, "sector": fd.SECTORS[sym],
            "ratio": round(last["ratio"], 2), "mom": round(last["mom"], 2),
            "dRatio5": round(last["dRatio5"], 2), "dMom5": round(last["dMom5"], 2),
            "dist": round(last["dist"], 2),
            "state": last["state"], "quadrant": QUAD_QUADRANT[last["state"]],
            "days_in_state": int(last["days"]),
            "strengthening": strengthening,
        })
    df = pd.DataFrame(rows).sort_values(
        ["strengthening", "mom", "ratio"], ascending=[False, False, False]
    ).reset_index(drop=True)
    return df, panel


def plot_rrg(panel, bench, path, tail=8):
    fig, ax = plt.subplots(figsize=(11, 9))
    all_r, all_m = [], []
    for sym, s in panel.items():
        seg = s.iloc[-tail:]
        all_r += list(seg["ratio"]); all_m += list(seg["mom"])
    rmin, rmax = min(all_r + [100]) - 1, max(all_r + [100]) + 1
    mmin, mmax = min(all_m + [100]) - 1, max(all_m + [100]) + 1

    ax.axhline(100, color="#888", lw=1); ax.axvline(100, color="#888", lw=1)
    ax.fill_between([100, rmax], 100, mmax, color="#1a9850", alpha=0.06)
    ax.fill_between([rmin, 100], 100, mmax, color="#4575b4", alpha=0.06)
    ax.fill_between([rmin, 100], mmin, 100, color="#d73027", alpha=0.06)
    ax.fill_between([100, rmax], mmin, 100, color="#fdae61", alpha=0.08)
    ax.text(rmax - 0.2, mmax - 0.3, "领先 Leading", ha="right", va="top", color="#1a9850", fontsize=11, weight="bold")
    ax.text(rmin + 0.2, mmax - 0.3, "改善 Improving", ha="left", va="top", color="#4575b4", fontsize=11, weight="bold")
    ax.text(rmin + 0.2, mmin + 0.3, "落后 Lagging", ha="left", va="bottom", color="#d73027", fontsize=11, weight="bold")
    ax.text(rmax - 0.2, mmin + 0.3, "转弱 Weakening", ha="right", va="bottom", color="#b8860b", fontsize=11, weight="bold")

    for sym, s in panel.items():
        seg = s.iloc[-tail:]
        last = seg.iloc[-1]
        col = QUAD_COLOR[last["state"]]
        ax.plot(seg["ratio"], seg["mom"], "-", color=col, alpha=0.5, lw=1.4)
        strengthening = (last["mom"] >= 100 and last["dMom5"] > 0)
        edge = "#DAA520" if strengthening else "white"
        ew = 3.0 if strengthening else 1.0
        ax.scatter(last["ratio"], last["mom"], s=260, color=col,
                   edgecolors=edge, linewidths=ew, zorder=5)
        label = f"{fd.SECTORS[sym]}\n{sym}"
        ax.annotate(label, (last["ratio"], last["mom"]),
                    xytext=(6, 6), textcoords="offset points", fontsize=9, weight="bold")

    ax.set_xlabel("JdK RS-Ratio  (相对强度趋势 →)", fontsize=12)
    ax.set_ylabel("JdK RS-Momentum  (相对强度动能 ↑)", fontsize=12)
    ax.set_title(f"美股行业板块 RRG 四象限  ·  基准 {bench} ({fd.BENCHMARKS[bench]})\n"
                 f"金边 = 仍在走强 (动能>100 且 5日动能上行)  ·  截至 {panel[list(panel)[0]].index[-1].date()}",
                 fontsize=13)
    ax.set_xlim(rmin, rmax); ax.set_ylim(mmin, mmax)
    ax.grid(alpha=0.15)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def main():
    px = fd.load_prices(fd.all_symbols())
    opens = fd.load_prices(fd.all_symbols(), field="open")
    sectors = list(fd.SECTORS.keys())
    asof = px.index[-1].date()
    print(f"data through {asof},  {px.shape[0]} sessions,  {len(sectors)} sectors  (T+1 open execution)\n")

    print("=== A. Main grid — DEFAULT params Z63/S8/M5 (top-5, no quad filter) ===")
    main_df, main_curves = run_grid(px, opens, sectors, quad12_only=False, params=BASE)
    print(main_df.to_string(index=False))

    print("\n=== A2. Main grid — OPTIMIZED params Z126/S8/M3 ===")
    opt_df, opt_curves = run_grid(px, opens, sectors, quad12_only=False, params=OPTIMIZED)
    print(opt_df.to_string(index=False))

    print("\n=== B. Quadrant-1/2 filter grid (candidates must have Mom>=100, default params) ===")
    q12_df, q12_curves = run_grid(px, opens, sectors, quad12_only=True, params=BASE)
    print(q12_df.to_string(index=False))

    print("\n=== C. Parameter sweep (SPY, 20d rebalance) top rows by Sharpe ===")
    sweep_df = run_param_sweep(px, opens, sectors)
    print(sweep_df.head(12).to_string(index=False))
    print("... worst 5:")
    print(sweep_df.tail(5).to_string(index=False))

    print("\n=== C2. Quadrant PnL (T+1 open, 20d, optimized params) ===")
    import quadrant_pnl as qp
    quad_df, quad_png = qp.main()   # generates output/quadrant_pnl.png + returns metrics table
    print(quad_df.to_string(index=False))

    # current snapshot + charts
    snap_spy, panel_spy = current_snapshot(px, sectors, "SPY")
    snap_qqq, panel_qqq = current_snapshot(px, sectors, "QQQ")
    p1 = plot_rrg(panel_spy, "SPY", os.path.join(OUT, "rrg_quadrant_SPY.png"))
    p2 = plot_rrg(panel_qqq, "QQQ", os.path.join(OUT, "rrg_quadrant_QQQ.png"))

    print("\n=== D. Current RRG snapshot vs SPY (sorted: strengthening first) ===")
    show = snap_spy[["sector", "symbol", "quadrant", "ratio", "mom", "dMom5", "dist",
                     "days_in_state", "strengthening"]]
    print(show.to_string(index=False))

    # ---- Excel ----
    xlsx = os.path.join(OUT, "rotation_backtest.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        main_df.to_excel(xw, sheet_name="主表_默认参数", index=False)
        opt_df.to_excel(xw, sheet_name="主表_优化参数", index=False)
        q12_df.to_excel(xw, sheet_name="象限过滤_Q12", index=False)
        sweep_df.to_excel(xw, sheet_name="参数敏感性_ParamSweep", index=False)
        snap_spy.to_excel(xw, sheet_name="当前快照_vs_SPY", index=False)
        snap_qqq.to_excel(xw, sheet_name="当前快照_vs_QQQ", index=False)
        pd.DataFrame([{"symbol": s, "sector": n} for s, n in fd.SECTORS.items()]
                     ).to_excel(xw, sheet_name="行业清单_Universe", index=False)
        quad_df.to_excel(xw, sheet_name="象限PnL_QuadrantPnL", index=False)
        eq = pd.DataFrame({k: v for k, v in main_curves.items()}); eq.index.name = "date"
        eq.to_excel(xw, sheet_name="净值_默认参数")
        eqo = pd.DataFrame({k: v for k, v in opt_curves.items()}); eqo.index.name = "date"
        eqo.to_excel(xw, sheet_name="净值_优化参数")
    print(f"\nsaved: {xlsx}\nsaved: {p1}\nsaved: {p2}")

    # ---- equity charts ----
    eq_def = plot_equity(main_curves, "行业轮动净值 · 默认参数 Z63/S8/M5  (对数轴)",
                         os.path.join(OUT, "equity_default.png"))
    eq_opt = plot_equity(opt_curves, "行业轮动净值 · 优化参数 Z126/S8/M3  (对数轴)",
                         os.path.join(OUT, "equity_optimized.png"))
    print(f"saved: {eq_def}\nsaved: {eq_opt}")

    # ---- persist everything for the PDF builder ----
    import pickle
    results = {
        "asof": str(asof), "n_sessions": int(px.shape[0]), "sectors": fd.SECTORS,
        "benches": fd.BENCHMARKS, "rebalances": REBALANCES, "top_k": TOP_K,
        "base_params": BASE.__dict__, "opt_params": OPTIMIZED.__dict__,
        "main_df": main_df, "opt_df": opt_df, "q12_df": q12_df, "sweep_df": sweep_df,
        "quad_df": quad_df,
        "snap_spy": snap_spy, "snap_qqq": snap_qqq,
        "window": (str(snap_dates_start(main_curves)), str(asof)),
        "execution": "t1_open",
        "charts": {"rrg_spy": p1, "rrg_qqq": p2, "eq_def": eq_def, "eq_opt": eq_opt,
                   "quad_pnl": quad_png},
    }
    with open(os.path.join(OUT, "results.pkl"), "wb") as f:
        pickle.dump(results, f)
    print("saved: results.pkl")
    return results


def snap_dates_start(curves):
    for v in curves.values():
        return v.index[0].date()
    return None


def plot_equity(curves, title, path):
    fig, ax = plt.subplots(figsize=(12, 7))
    for k, v in curves.items():
        style = "--" if k.startswith("买入持有") else "-"
        lw = 2.6 if k.startswith("买入持有") else 1.2
        ax.plot(v.index, v.values, style, lw=lw, label=k, alpha=0.9)
    ax.set_title(title, fontsize=13)
    ax.set_ylabel("净值 (起点=1)")
    ax.set_yscale("log"); ax.grid(alpha=0.2); ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=130); plt.close(fig)
    return path


if __name__ == "__main__":
    main()
