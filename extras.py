# -*- coding: utf-8 -*-
"""
Extra studies for the report (cost 20bps, T+1 close, long-only, top-5):
  1. EMA-RRG vs MA-RRG  -- same quadrant rotation, two momentum definitions
  2. merged selection   -- union-top5 (5, 1/5) vs each-quadrant-top5 (10, 1/10)
  3. tech in/out split  -- params/period fixed on 2018-2021, traded 2022+ (reduce
                           parameter overfit; universe survivorship still noted)
Saves extras_results.pkl + charts.
"""
import os
import pickle
import itertools
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

import fmp_data as fd
import tech_data as td
from rrg_model import RRGParams
from rotation_backtest import StratConfig, run_strategy

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
OUT = os.path.join(os.path.dirname(__file__), "output")

CAP = 100_000
COST = 0.002
EXEC = "t1_close"
QUADS = ["Lead", "Impr", "Weak", "Lag"]
QCN = {"Lead": "领先Q1", "Impr": "改善Q2", "Weak": "转弱Q4", "Lag": "落后Q3"}
ADJ = [("Impr", "Lead"), ("Lead", "Weak"), ("Weak", "Lag"), ("Lag", "Impr")]


def perf(dr):
    n = len(dr); eq = (1 + dr).cumprod()
    cagr = eq.iloc[-1] ** (252 / n) - 1
    vol = dr.std() * np.sqrt(252)
    sharpe = (dr.mean() * 252) / vol if vol > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    return dict(final=CAP * (1 + dr).prod(), cagr=cagr, vol=vol, sharpe=sharpe, dd=dd)


def yearly(dr):
    return {y: round(((1 + s).prod() - 1) * 100, 1) for y, s in dr.groupby(dr.index.year)}


def win(s, a, b=None):
    s = s[s.index >= pd.Timestamp(a)]
    if b:
        s = s[s.index < pd.Timestamp(b)]
    return s


def mrow(name, dr, extra=None):
    m = perf(dr)
    r = {"策略": name, "最终$": f"{m['final']:,.0f}", "年化%": round(m["cagr"] * 100, 2),
         "波动%": round(m["vol"] * 100, 1), "夏普": round(m["sharpe"], 2),
         "最大回撤%": round(m["dd"] * 100, 1), "Calmar": round(m["cagr"] / abs(m["dd"]), 2)}
    if extra:
        r.update(extra)
    return r


def cfg(bench, reb, quads, params, per_quad=False):
    return StratConfig(bench, reb, top_k=5, quad_filter=tuple(quads), fill_mode="cash",
                       execution=EXEC, cost_per_turnover=COST, params=params, per_quad_topk=per_quad)


def dr_of(px, op, sectors, bench, reb, quads, params, per_quad=False):
    return run_strategy(px, sectors, cfg(bench, reb, quads, params, per_quad), op)


def pnl_chart(curves, title, path, start="2021-01-01"):
    fig, ax = plt.subplots(figsize=(12, 6.6))
    for name, dr in curves.items():
        d = win(dr, start); eq = CAP * (1 + d).cumprod()
        ls = "--" if name.startswith("买入持有") else "-"
        ax.plot(eq.index, eq.values, ls, lw=2.2, label=f"{name} → ${eq.iloc[-1]:,.0f}")
    ax.axhline(CAP, color="#aaa", lw=.8, ls=":")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
    ax.set_title(title, fontsize=12); ax.set_ylabel("组合价值 ($100k起)")
    ax.grid(alpha=.2); ax.legend(fontsize=8.5, loc="upper left")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig); return path


# ---------------- 1. EMA vs MA RRG ----------------
def ema_vs_ma(px, op, sectors, bench, tag):
    ema_p = RRGParams(model="ema", zwin=126, smooth=8, mom_lag=3)
    # small MA grid, pick best by Sharpe on all-quad top-5 rotation
    best = None
    for lr, lm, s in itertools.product([180, 250], [40, 80], [10, 20]):
        p = RRGParams(model="ma", lr=lr, lm=lm, ma_smooth=s)
        try:
            dr = win(dr_of(px, op, sectors, bench, 20, (), p)["daily_ret"], "2021-01-01")
        except Exception:
            continue
        sh = perf(dr)["sharpe"]
        if best is None or sh > best[0]:
            best = (sh, p, dr)
    ma_p = best[1]; ma_dr = best[2]
    ema_dr = win(dr_of(px, op, sectors, bench, 20, (), ema_p)["daily_ret"], "2021-01-01")
    bench_dr = win(px[bench].pct_change().dropna(), "2021-01-01")

    ename = f"EMA RRG (Z{ema_p.zwin}/S{ema_p.smooth}/M{ema_p.mom_lag})"
    mname = f"MA RRG (R{ma_p.lr}/M{ma_p.lm}/S{ma_p.ma_smooth})"
    summ = pd.DataFrame([mrow(ename, ema_dr), mrow(mname, ma_dr), mrow(f"买入持有{bench}", bench_dr)])
    yrs = sorted(set(bench_dr.index.year))
    ymat = pd.DataFrame({"策略": [ename, mname, f"买入持有{bench}"],
                         **{f"{y}{'*' if y == 2026 else ''}":
                            [yearly(ema_dr).get(y), yearly(ma_dr).get(y), yearly(bench_dr).get(y)]
                            for y in yrs}})
    chart = pnl_chart({ename: ema_dr, mname: ma_dr, f"买入持有{bench}": bench_dr},
                      f"{tag}·EMA RRG vs MA RRG (全象限top5·20d·20bps)",
                      os.path.join(OUT, f"extra_emama_{tag}.png"))
    print(f"[{tag}] EMA vs MA:\n", summ.to_string(index=False))
    return {"summary": summ, "ymat": ymat, "chart": chart, "ema_params": ema_p.__dict__,
            "ma_params": ma_p.__dict__, "ename": ename, "mname": mname}


# ---------------- 2. merged selection: union-5 vs each-5 ----------------
def merged_selection(px, op, sectors, bench, tag, params):
    rows, curves = [], {}
    for a, b in ADJ:
        u = win(dr_of(px, op, sectors, bench, 20, (a, b), params, per_quad=False)["daily_ret"], "2021-01-01")
        e = win(dr_of(px, op, sectors, bench, 20, (a, b), params, per_quad=True)["daily_ret"], "2021-01-01")
        rows.append(mrow(f"{QCN[a]}+{QCN[b]}·并集选5", u))
        rows.append(mrow(f"{QCN[a]}+{QCN[b]}·各取5(10只)", e))
        curves[f"{QCN[a]}+{QCN[b]}·并集5"] = u
        curves[f"{QCN[a]}+{QCN[b]}·各取5"] = e
    summ = pd.DataFrame(rows)
    # chart: pick the strongest adjacent pair both ways + bench
    bench_dr = win(px[bench].pct_change().dropna(), "2021-01-01")
    a, b = ("Weak", "Lag")
    chart = pnl_chart({f"{QCN[a]}+{QCN[b]}·并集选5": curves[f"{QCN[a]}+{QCN[b]}·并集5"],
                       f"{QCN[a]}+{QCN[b]}·各取5(10只)": curves[f"{QCN[a]}+{QCN[b]}·各取5"],
                       f"买入持有{bench}": bench_dr},
                      f"{tag}·合并选股: 并集选5 vs 各取5(10只1/10) — 以{QCN[a]}+{QCN[b]}为例",
                      os.path.join(OUT, f"extra_merge_{tag}.png"))
    print(f"[{tag}] merged selection:\n", summ.to_string(index=False))
    return {"summary": summ, "chart": chart}


# ---------------- 3. tech in-sample(2018-2021) / OOS(2022+) ----------------
def tech_is_oos(px, op, sectors, bench, params):
    REBS = [5, 10, 15, 20, 25, 30]
    cache = {}
    def get(q, r):
        k = (q, r)
        if k not in cache:
            cache[k] = run_strategy(px, sectors, cfg(bench, r, (q,), params), op)["daily_ret"]
        return cache[k]
    # best period per quadrant chosen ONLY on 2018-2021
    is_period = {}
    for q in QUADS:
        best_r, best_s = 20, -9
        for r in REBS:
            sh = perf(win(get(q, r), "2018-01-01", "2022-01-01"))["sharpe"]
            if sh > best_s:
                best_s, best_r = sh, r
        is_period[q] = best_r
    # mixed sleeve (drop Q2 like before): equal-capital drift
    def mix(periods):
        eqs = [(1 + get(q, r)).cumprod() for q, r in periods.items()]
        idx = eqs[0].index
        return (sum(e.reindex(idx).ffill() for e in eqs) / len(eqs)).pct_change().dropna()
    mix_is = {q: is_period[q] for q in ["Lead", "Weak", "Lag"]}
    mix_dr = mix(mix_is)
    fixed20 = mix({q: 20 for q in ["Lead", "Weak", "Lag"]})
    rows = []
    for name, dr in [("混合·IS(2018-21)调周期", mix_dr), ("混合·固定20d", fixed20),
                     (f"买入持有{bench}", px[bench].pct_change().dropna())]:
        rows.append({"策略": name,
                     "IS(18-21)夏普": round(perf(win(dr, "2018-01-01", "2022-01-01"))["sharpe"], 2),
                     "OOS(22+)夏普": round(perf(win(dr, "2022-01-01"))["sharpe"], 2),
                     "OOS(22+)年化%": round(perf(win(dr, "2022-01-01"))["cagr"] * 100, 2),
                     "OOS(22+)回撤%": round(perf(win(dr, "2022-01-01"))["dd"] * 100, 1)})
    summ = pd.DataFrame(rows)
    # OOS yearly
    yrs = sorted(set(win(mix_dr, "2022-01-01").index.year))
    ymat = pd.DataFrame({"策略(OOS 2022+)": ["混合·IS调周期", "混合·固定20d", f"买入持有{bench}"],
                         **{f"{y}{'*' if y == 2026 else ''}":
                            [yearly(win(mix_dr, "2022-01-01")).get(y),
                             yearly(win(fixed20, "2022-01-01")).get(y),
                             yearly(win(px[bench].pct_change().dropna(), "2022-01-01")).get(y)]
                            for y in yrs}})
    chart = pnl_chart({"混合·IS调周期": win(mix_dr, "2022-01-01"),
                       "混合·固定20d": win(fixed20, "2022-01-01"),
                       f"买入持有{bench}": win(px[bench].pct_change().dropna(), "2022-01-01")},
                      f"科技 OOS(2022+)实盘: IS(2018-21)定周期 vs 固定 vs {bench}",
                      os.path.join(OUT, "extra_tech_oos.png"), start="2022-01-01")
    is_period_cn = {QCN[q]: f"{r}d" for q, r in is_period.items()}
    print("[tech IS/OOS] IS periods:", is_period_cn, "\n", summ.to_string(index=False))
    return {"summary": summ, "ymat": ymat, "chart": chart, "is_period": is_period_cn}


def main():
    px_i = fd.load_prices(fd.all_symbols())
    op_i = fd.load_prices(fd.all_symbols(), field="open")
    ind_sectors = list(fd.SECTORS.keys())
    P = RRGParams(model="ema", zwin=126, smooth=8, mom_lag=3)

    R = {}
    R["emama_ind"] = ema_vs_ma(px_i, op_i, ind_sectors, "SPY", "行业")
    R["merge_ind"] = merged_selection(px_i, op_i, ind_sectors, "SPY", "行业", P)

    tsyms = td.all_tickers() + ["SOXX", "QQQ"]
    px_t = fd.load_prices(tsyms, field="close"); op_t = fd.load_prices(tsyms, field="open")
    stocks = [t for t in td.all_tickers() if t in px_t.columns]
    R["tech_oos"] = tech_is_oos(px_t, op_t, stocks, "SOXX", P)

    pickle.dump(R, open(os.path.join(OUT, "extras_results.pkl"), "wb"))
    print("\nsaved extras_results.pkl")


if __name__ == "__main__":
    main()
