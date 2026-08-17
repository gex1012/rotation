# -*- coding: utf-8 -*-
"""
Unified quadrant pipeline for one universe (long-only, top-5, T+1 close, 40bps cost).

Steps (per universe):
  2. per-quadrant holding backtest @ 20d
  3. per-quadrant holding-PERIOD parameter sweep [5..30]
  4. each quadrant at its BEST period -> comparison
  5. adjacent-quadrant merged strategies (RRG-cycle adjacency)
Plus benchmark buy&hold, PnL curves, current holdings.

Runs for: 行业(37 ETF vs SPY) and 科技(129 stock vs QQQ). Saves final_results.pkl.
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
from rrg_model import RRGParams
from rotation_backtest import StratConfig, run_strategy, benchmark_curve

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
OUT = os.path.join(os.path.dirname(__file__), "output")

CAP = 100_000
START = pd.Timestamp("2021-01-01")
COST = 0.002          # 2 per-mille (20 bps) of traded notional per unit turnover
EXEC = "t1_close"     # signal at close d, execute at close d+1
TOPK = 5
PARAMS = RRGParams(126, 8, 2.2, 3)
REBS = [5, 10, 15, 20, 25, 30]
QUADS = ["Lead", "Impr", "Weak", "Lag"]
QCN = {"Lead": "领先Q1", "Impr": "改善Q2", "Weak": "转弱Q4", "Lag": "落后Q3"}
QCOL = {"Lead": "#1a9850", "Impr": "#4575b4", "Weak": "#f39c12", "Lag": "#d73027"}
# RRG-cycle adjacency: Impr->Lead->Weak->Lag->Impr
ADJ = [("Impr", "Lead"), ("Lead", "Weak"), ("Weak", "Lag"), ("Lag", "Impr")]


def cfg(bench, reb, quads, params=PARAMS):
    return StratConfig(bench, reb, top_k=TOPK, quad_filter=tuple(quads), rank_by="score",
                       fill_mode="cash", execution=EXEC, cost_per_turnover=COST, params=params)


def cfg_all(bench, reb, params):
    """all-quadrant top-k rotation (no filter) -- representative for param testing."""
    return StratConfig(bench, reb, top_k=TOPK, quad_filter=(), fill_mode="cash",
                       execution=EXEC, cost_per_turnover=COST, params=params)


def param_sweep(prices, opens, sectors, bench):
    """Sweep ZWIN x SMOOTH x MOM_LAG on the representative top-5 rotation (20d)."""
    import itertools
    rows = []
    for zw, sm, ml in itertools.product([63, 126], [3, 8, 13], [3, 5, 10]):
        p = RRGParams(zw, sm, 2.2, ml)
        try:
            dr = trim(run_strategy(prices, sectors, cfg_all(bench, 20, p), opens)["daily_ret"])
        except Exception:
            continue
        m = perf(dr)
        rows.append({"ZWIN": zw, "SMOOTH": sm, "MOM_LAG": ml, "年化%": round(m["cagr"] * 100, 2),
                     "夏普": round(m["sharpe"], 2), "最大回撤%": round(m["dd"] * 100, 1)})
    return pd.DataFrame(rows).sort_values("夏普", ascending=False).reset_index(drop=True)


def scale_check(prices, opens, sectors, bench):
    """Prove SCALE is cosmetic: two very different scales -> identical performance."""
    out = []
    for sc in [2.2, 6.0]:
        p = RRGParams(126, 8, sc, 3)
        m = perf(trim(run_strategy(prices, sectors, cfg_all(bench, 20, p), opens)["daily_ret"]))
        out.append({"SCALE": sc, "夏普": round(m["sharpe"], 4), "年化%": round(m["cagr"] * 100, 4),
                    "最大回撤%": round(m["dd"] * 100, 3)})
    return out


def trim(s):
    return s[s.index >= START]


def perf(dr):
    dr = trim(dr)
    n = len(dr); eq = (1 + dr).cumprod()
    cagr = eq.iloc[-1] ** (252 / n) - 1
    vol = dr.std() * np.sqrt(252)
    sharpe = (dr.mean() * 252) / vol if vol > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    return dict(final=CAP * (1 + dr).prod(), cagr=cagr, vol=vol, sharpe=sharpe, dd=dd)


def yearly(dr):
    dr = trim(dr)
    return {y: round(((1 + s).prod() - 1) * 100, 1) for y, s in dr.groupby(dr.index.year)}


def mrow(name, dr, extra=None):
    m = perf(dr)
    r = {"策略": name, "最终$": f"{m['final']:,.0f}", "总收益%": round((m['final']/CAP-1)*100, 1),
         "年化%": round(m['cagr']*100, 2), "波动%": round(m['vol']*100, 1),
         "夏普": round(m['sharpe'], 2), "最大回撤%": round(m['dd']*100, 1),
         "Calmar": round(m['cagr']/abs(m['dd']), 2)}
    if extra:
        r.update(extra)
    return r


def run_universe(prices, opens, sectors, bench, tag):
    print(f"\n########## {tag} (vs {bench}, cost {COST*1e4:.0f}bps, {EXEC}) ##########")

    # cache daily_ret + holdings for (quads-tuple, reb)
    cache = {}
    def get(quads, reb):
        k = (tuple(sorted(quads)), reb)
        if k not in cache:
            cache[k] = run_strategy(prices, sectors, cfg(bench, reb, quads), opens)
        return cache[k]

    # Step 2: per-quadrant @ 20d
    step2 = pd.DataFrame([mrow(QCN[q], get([q], 20)["daily_ret"]) for q in QUADS])

    # Step 3: per-quadrant period sweep (Sharpe matrix)
    sh = np.full((len(QUADS), len(REBS)), np.nan)
    for i, q in enumerate(QUADS):
        for j, r in enumerate(REBS):
            sh[i, j] = perf(get([q], r)["daily_ret"])["sharpe"]
    best_period = {q: REBS[int(np.nanargmax(sh[i]))] for i, q in enumerate(QUADS)}

    # Step 4: each quadrant at best period
    step4 = pd.DataFrame([mrow(f"{QCN[q]}@{best_period[q]}d", get([q], best_period[q])["daily_ret"],
                               {"最优周期": f"{best_period[q]}d"}) for q in QUADS])

    # Step 5: adjacent-quadrant merged @ 20d, AND at each pair's own best period
    step5 = pd.DataFrame([mrow(f"{QCN[a]}+{QCN[b]}", get([a, b], 20)["daily_ret"]) for a, b in ADJ])
    adj_best = {}
    for a, b in ADJ:
        best_r, best_s = 20, -9
        for r in REBS:
            sh_ = perf(get([a, b], r)["daily_ret"])["sharpe"]
            if sh_ > best_s:
                best_s, best_r = sh_, r
        adj_best[(a, b)] = best_r
    step5b = pd.DataFrame([mrow(f"{QCN[a]}+{QCN[b]}@{adj_best[(a,b)]}d", get([a, b], adj_best[(a, b)])["daily_ret"],
                                {"最优周期": f"{adj_best[(a,b)]}d"}) for a, b in ADJ])

    # parameter testing (representative top-5 rotation) + SCALE invariance
    psweep = param_sweep(prices, opens, sectors, bench)
    scale_inv = scale_check(prices, opens, sectors, bench)

    # benchmark
    bench_dr = trim(prices[bench].pct_change().dropna())
    bench_row = mrow(f"买入持有{bench}", prices[bench].pct_change().dropna())

    # curves for PnL charts
    curves = {}
    for q in QUADS:
        curves[f"{QCN[q]}@{best_period[q]}d"] = CAP * (1 + trim(get([q], best_period[q])["daily_ret"])).cumprod()
    for a, b in ADJ:
        curves[f"{QCN[a]}+{QCN[b]}"] = CAP * (1 + trim(get([a, b], 20)["daily_ret"])).cumprod()
    curves[f"买入持有{bench}"] = CAP * (1 + bench_dr).cumprod()

    # yearly for best-period singles + adjacent + bench
    ykeys = [(f"{QCN[q]}@{best_period[q]}d", get([q], best_period[q])["daily_ret"]) for q in QUADS] \
        + [(f"{QCN[a]}+{QCN[b]}", get([a, b], 20)["daily_ret"]) for a, b in ADJ] \
        + [(f"买入持有{bench}", prices[bench].pct_change().dropna())]
    yrs = sorted(set(trim(bench_dr).index.year))
    ymat = pd.DataFrame({"策略": [k for k, _ in ykeys],
                         **{f"{y}{'*' if y == 2026 else ''}": [yearly(d).get(y) for _, d in ykeys] for y in yrs}})

    # current + previous holdings (last two rebalances) for change-detection
    def hpack(log):
        cur = log[-1]; prev = log[-2] if len(log) > 1 else {"picks": [], "date": None}
        added = [x for x in cur["picks"] if x not in prev["picks"]]
        removed = [x for x in prev["picks"] if x not in cur["picks"]]
        return {"date": str(cur["date"]), "picks": cur["picks"], "states": cur.get("states", {}),
                "prev_date": str(prev.get("date")), "prev_picks": prev.get("picks", []),
                "added": added, "removed": removed}
    holds = {}
    for q in QUADS:
        holds[f"{QCN[q]}@{best_period[q]}d"] = hpack(get([q], best_period[q])["holdings"])
    for a, b in ADJ:
        holds[f"{QCN[a]}+{QCN[b]}"] = hpack(get([a, b], 20)["holdings"])

    # ---- charts ----
    def pnl_chart(keys, title, path):
        fig, ax = plt.subplots(figsize=(12, 6.8))
        for k in keys:
            ls = "--" if k.startswith("买入持有") else "-"
            lw = 2.4 if k.startswith("买入持有") else 1.9
            ax.plot(curves[k].index, curves[k].values, ls, lw=lw, label=f"{k} → ${curves[k].iloc[-1]:,.0f}")
        ax.axhline(CAP, color="#aaa", lw=.8, ls=":")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
        ax.set_title(title, fontsize=12); ax.set_ylabel("组合价值 ($100k起)")
        ax.grid(alpha=.2); ax.legend(fontsize=8.5, loc="upper left")
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig); return path

    singles_keys = [f"{QCN[q]}@{best_period[q]}d" for q in QUADS] + [f"买入持有{bench}"]
    adj_keys = [f"{QCN[a]}+{QCN[b]}" for a, b in ADJ] + [f"买入持有{bench}"]
    c_single = pnl_chart(singles_keys, f"{tag}·各象限最优周期 PnL vs {bench} (40bps,T+1收盘)",
                         os.path.join(OUT, f"final_{tag}_singles.png"))
    c_adj = pnl_chart(adj_keys, f"{tag}·相邻象限合并 PnL vs {bench} (20d,40bps,T+1收盘)",
                     os.path.join(OUT, f"final_{tag}_adj.png"))

    # heatmap
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    im = ax.imshow(sh, cmap="RdYlGn", aspect="auto", vmin=np.nanmin(sh), vmax=np.nanmax(sh))
    ax.set_xticks(range(len(REBS))); ax.set_xticklabels([f"{r}d" for r in REBS])
    ax.set_yticks(range(len(QUADS))); ax.set_yticklabels([QCN[q] for q in QUADS])
    for i in range(len(QUADS)):
        jb = int(np.nanargmax(sh[i]))
        for j in range(len(REBS)):
            ax.text(j, i, f"{sh[i,j]:.2f}", ha="center", va="center", fontsize=8,
                    fontweight="bold" if j == jb else "normal")
            if j == jb:
                ax.add_patch(plt.Rectangle((j-.5, i-.5), 1, 1, fill=False, edgecolor="#111", lw=2))
    ax.set_title(f"{tag}·各象限×持有周期 夏普 (黑框=最优)", fontsize=11)
    fig.tight_layout(); c_hm = os.path.join(OUT, f"final_{tag}_heatmap.png")
    fig.savefig(c_hm, dpi=130); plt.close(fig)

    print(step4.to_string(index=False))
    return {"tag": tag, "bench": bench, "best_period": best_period, "adj_best": adj_best,
            "step2": step2, "step4": step4, "step5": step5, "step5b": step5b,
            "psweep": psweep, "scale_inv": scale_inv, "bench_row": bench_row,
            "ymat": ymat, "holds": holds, "sharpe_matrix": sh.tolist(), "rebs": REBS,
            "charts": {"singles": c_single, "adj": c_adj, "heatmap": c_hm}}


def main():
    # industry -- new 70-ETF universe vs SPY
    import industry2 as ind2
    isyms = [ind2.BENCH] + ind2.all_tickers()
    px_i = fd.load_prices(isyms)
    op_i = fd.load_prices(isyms, field="open")
    ind = run_universe(px_i, op_i, ind2.all_tickers(), "SPY", "行业板块")
    # tech (stocks vs SOXX -- semiconductor benchmark, per request)
    tsyms = td.all_tickers() + ["SOXX", "QQQ"]
    px_t = fd.load_prices(tsyms, field="close"); op_t = fd.load_prices(tsyms, field="open")
    stocks = [t for t in td.all_tickers() if t in px_t.columns]
    tech = run_universe(px_t, op_t, stocks, "SOXX", "科技个股")

    pickle.dump({"industry": ind, "tech": tech, "cost_bps": COST*1e4, "exec": EXEC,
                 "params": PARAMS.__dict__, "topk": TOPK},
                open(os.path.join(OUT, "final_results.pkl"), "wb"))
    print("\nsaved final_results.pkl")


if __name__ == "__main__":
    main()
