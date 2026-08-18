# -*- coding: utf-8 -*-
"""
Sector-rotation backtest engine.

Rule (long-only, equal-weight, article-aligned):
  * Compute each sector's RRG position (RS-Ratio, RS-Momentum) vs a benchmark.
  * Every REBALANCE trading days, rank sectors by a composite RRG score and hold
    the top TOP_K equal-weight until the next rebalance.
  * Score = (Ratio-100) + MOM_WEIGHT*(Mom-100), which favours the leading (Q1)
    and improving (Q2) quadrants -- the paper's finding that Q1/Q2 outperform.
  * Optional quad filter: restrict candidates to Mom>=100 (Q1+Q2) before ranking.

No look-ahead: on rebalance day t the signal uses data through t's close and the
basket is entered at t's close; daily returns accrue from t+1 onward. This is the
standard EOD-rebalance convention.

Everything returns plain dicts/Series so report.py can dump to Excel untouched.
"""
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from rrg_model import RRGParams, build_rrg_panel

TRADING_DAYS = 252


@dataclass
class StratConfig:
    bench: str                       # RS denominator + comparison baseline, e.g. "SPY"
    rebalance: int                   # rebalance every N trading days
    top_k: int = 5                   # number of sectors to long
    mom_weight: float = 1.5          # weight on the momentum axis in the score
    quad12_only: bool = False        # legacy: if True, only pick from Q1+Q2 (Mom>=100)
    # general quadrant filter: tuple of allowed states, e.g. ("Impr","Weak")=Q2+Q4.
    # empty -> no filter (unless quad12_only). States: Lead=Q1 Impr=Q2 Weak=Q4 Lag=Q3.
    quad_filter: tuple = ()
    rank_by: str = "score"           # "score" (momentum-tilted) or "dist" (distance from origin)
    # merged-quadrant selection: False -> top_k from the UNION (5 total, best wins);
    #   True -> top_k from EACH quadrant separately (e.g. 5+5=10 names, equal weight)
    per_quad_topk: bool = False
    cost_per_turnover: float = 0.0005  # round-trip cost per unit of traded weight
    params: RRGParams = field(default_factory=RRGParams)
    # what to do when the Q1+Q2 filter leaves fewer than top_k names:
    #   "benchmark" -> fill empty slots with the benchmark ETF (default)
    #   "cash"      -> leave empty slots in cash (0% return)
    #   "concentrate" -> split full capital across the few names we have
    #   "score"     -> old behaviour: fall back to top-k across ALL quadrants
    fill_mode: str = "benchmark"
    # execution timing:
    #   "t1_open"  = signal at close d, trade at OPEN of d+1  (default, realistic)
    #   "t0_close" = signal & fill at the same close d        (MOC idealization)
    #   "t1_close" = signal at close d, fill at close d+1
    execution: str = "t1_open"

    def label(self) -> str:
        allowed = _allowed_states(self)
        if allowed is None:
            f = "ALL"
        else:
            f = "+".join({"Lead": "Q1", "Impr": "Q2", "Weak": "Q4", "Lag": "Q3"}[s]
                         for s in ["Lead", "Impr", "Weak", "Lag"] if s in allowed)
        tail = f"|{self.fill_mode}" if allowed is not None else ""
        rb = "" if self.rank_by == "score" else f"|{self.rank_by}"
        ex = {"t1_open": "|T+1o", "t1_close": "|T+1c", "t0_close": ""}.get(self.execution, "")
        return f"{self.bench}|{self.rebalance}d|top{self.top_k}|{f}{rb}{tail}{ex}"


def _score(row, mom_weight):
    return (row["ratio"] - 100) + mom_weight * (row["mom"] - 100)


def _allowed_states(cfg):
    """Effective set of allowed quadrant states, or None for no filter."""
    if cfg.quad_filter:
        return set(cfg.quad_filter)
    if cfg.quad12_only:
        return {"Lead", "Impr"}
    return None


def _rank_key(cfg):
    if cfg.rank_by == "dist":
        return lambda kv: kv[1]["dist"]           # highest conviction (far from origin)
    if cfg.rank_by == "mom":
        return lambda kv: kv[1]["mom"]            # pure momentum
    return lambda kv: _score(kv[1], cfg.mom_weight)


def _select(snap, cfg):
    """Pick the basket for one rebalance. Returns (weights_dict, picks, bench_weight).
    weights_dict may contain cfg.bench as a key (benchmark fill slots)."""
    scored = sorted(snap.items(), key=_rank_key(cfg), reverse=True)
    k = cfg.top_k
    allowed = _allowed_states(cfg)

    if allowed is None:                           # headline: top-k across all 37 -> never short
        picks = [s for s, _ in scored[:k]]
        w = 1.0 / len(picks) if picks else 0.0
        return {s: w for s in picks}, picks, 0.0

    # "each-quadrant top-k" merged selection: 5 from each quadrant -> 10 names, equal weight
    if cfg.per_quad_topk and len(allowed) >= 2:
        picks = []
        for st in sorted(allowed):
            picks += [s for s, r in scored if r["state"] == st][:k]
        w = 1.0 / len(picks) if picks else 0.0
        return {s: w for s in picks}, picks, 0.0

    cand = [(s, r) for s, r in scored if r["state"] in allowed]   # already rank-sorted
    if len(cand) >= k:
        picks = [s for s, _ in cand[:k]]
        return {s: 1.0 / k for s in picks}, picks, 0.0

    # --- short of k names in the allowed quadrants: apply the chosen fill policy ---
    picks = [s for s, _ in cand]
    n = len(picks)
    if cfg.fill_mode == "benchmark":              # empty slots -> benchmark ETF
        wts = {s: 1.0 / k for s in picks}
        bench_w = (k - n) / k
        if bench_w > 0:
            wts[cfg.bench] = wts.get(cfg.bench, 0) + bench_w
        return wts, picks, bench_w
    if cfg.fill_mode == "cash":                   # empty slots -> cash (uninvested)
        return {s: 1.0 / k for s in picks}, picks, 0.0
    if cfg.fill_mode == "concentrate":            # split full capital over the few names
        w = 1.0 / n if n else 0.0
        return {s: w for s in picks}, picks, 0.0
    # "score": legacy fall-back to top-k across ALL quadrants
    allp = [s for s, _ in scored[:k]]
    return {s: 1.0 / len(allp) for s in allp}, allp, 0.0


def run_strategy(prices: pd.DataFrame, sectors, cfg: StratConfig, opens: pd.DataFrame = None):
    """Run one configuration. Returns dict with equity curve (Series), holdings
    log (list of dicts), and headline metrics. `opens` (open-price frame) is
    required for execution="t1_open"; if omitted it is loaded lazily."""
    panel = build_rrg_panel(prices, sectors, cfg.bench, cfg.params)
    if not panel:
        raise RuntimeError("empty RRG panel")
    if opens is None and cfg.execution == "t1_open":
        import fmp_data as _fd
        opens = _fd.load_prices(list(prices.columns))

    # common tradeable calendar = dates where the benchmark and >=top_k sectors exist
    valid_dates = None
    for s in panel.values():
        idx = s.index
        valid_dates = idx if valid_dates is None else valid_dates.union(idx)
    valid_dates = valid_dates.sort_values()
    ready = []
    for d in valid_dates:
        n = sum(1 for s in panel.values() if d in s.index and not np.isnan(s.loc[d, "ratio"]))
        if n >= max(cfg.top_k, 6):
            ready.append(d)
    dates = pd.DatetimeIndex(ready)
    if len(dates) < cfg.rebalance + 5:
        raise RuntimeError("not enough history after warm-up")

    # reindex every price series to the strategy calendar + ffill, so a held name
    # with gaps / a later inception never KeyErrors on a return-calc date.
    close_px = {sym: panel[sym]["price"].reindex(dates).ffill() for sym in panel}
    close_px[cfg.bench] = prices[cfg.bench].reindex(dates).ffill()
    open_px = {}
    if cfg.execution == "t1_open":
        for sym in list(panel) + [cfg.bench]:
            if sym in opens.columns:
                open_px[sym] = opens[sym].reindex(dates).ffill()

    def cl(sym, dt):
        return close_px[sym].loc[dt]

    def op(sym, dt):
        return open_px[sym].loc[dt] if sym in open_px else close_px[sym].loc[dt]

    daily_ret = pd.Series(0.0, index=dates[1:])
    holdings_log = []
    cur_weights = {}                                # currently held basket
    pending = None                                  # (weights) decided, awaiting execution

    def turnover_of(target):
        return sum(abs(target.get(s, 0) - cur_weights.get(s, 0))
                   for s in set(target) | set(cur_weights))

    for i in range(len(dates) - 1):
        d, d_next = dates[i], dates[i + 1]
        cost = 0.0
        split_new = None   # for t1_open: new basket that starts earning intraday on d_next

        # --- t1_close: a trade decided last step executes at today's close ---
        if pending is not None and cfg.execution == "t1_close":
            cost += turnover_of(pending) * cfg.cost_per_turnover
            cur_weights = pending
            pending = None

        # --- rebalance decision (uses close of day d) ---
        if i % cfg.rebalance == 0:
            snap = {}
            for sym, s in panel.items():
                if d in s.index and not np.isnan(s.loc[d, "ratio"]):
                    snap[sym] = s.loc[d]
            new_weights, picks, bench_w = _select(snap, cfg)
            turnover = turnover_of(new_weights)

            if cfg.execution == "t0_close":            # execute now, same close
                cost += turnover * cfg.cost_per_turnover
                cur_weights = new_weights
            elif cfg.execution == "t1_open":           # execute at d_next's open (split return)
                split_new = new_weights
                cost += turnover * cfg.cost_per_turnover
            else:                                       # t1_close: defer to next close
                pending = new_weights
            holdings_log.append({
                "date": d.date(), "picks": picks,
                "scores": {sym: round(_score(snap[sym], cfg.mom_weight), 2) for sym in picks},
                "states": {sym: snap[sym]["state"] for sym in picks},
                "bench_fill": round(bench_w, 3), "turnover": round(turnover, 3),
            })

        # --- realized return over d -> d_next ---
        if split_new is not None:                      # t1_open switch day
            port_r = 0.0
            for sym, wgt in cur_weights.items():       # old basket held into the open
                port_r += wgt * (op(sym, d_next) / cl(sym, d) - 1)
            for sym, wgt in split_new.items():         # new basket from open to close
                port_r += wgt * (cl(sym, d_next) / op(sym, d_next) - 1)
            cur_weights = split_new
        else:
            port_r = sum(wgt * (cl(sym, d_next) / cl(sym, d) - 1)
                         for sym, wgt in cur_weights.items())
        daily_ret.loc[d_next] = port_r - cost

    equity = (1 + daily_ret).cumprod()
    metrics = compute_metrics(daily_ret, equity, holdings_log, cfg)
    return {"equity": equity, "daily_ret": daily_ret, "holdings": holdings_log,
            "metrics": metrics, "dates": dates}


def compute_metrics(daily_ret: pd.Series, equity: pd.Series, holdings_log, cfg) -> dict:
    n = len(daily_ret)
    total = equity.iloc[-1] - 1
    years = n / TRADING_DAYS
    cagr = equity.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    vol = daily_ret.std() * np.sqrt(TRADING_DAYS)
    sharpe = (daily_ret.mean() * TRADING_DAYS) / vol if vol > 0 else np.nan
    downside = daily_ret[daily_ret < 0].std() * np.sqrt(TRADING_DAYS)
    sortino = (daily_ret.mean() * TRADING_DAYS) / downside if downside > 0 else np.nan
    roll_max = equity.cummax()
    dd = equity / roll_max - 1
    max_dd = dd.min()
    calmar = cagr / abs(max_dd) if max_dd < 0 else np.nan
    avg_turn = np.mean([h["turnover"] for h in holdings_log]) if holdings_log else 0.0

    # per-rebalance-period hit rate (was each holding period positive?)
    period_rets = []
    dates = daily_ret.index
    for k in range(0, n, cfg.rebalance):
        seg = daily_ret.iloc[k:k + cfg.rebalance]
        if len(seg):
            period_rets.append((1 + seg).prod() - 1)
    win = np.mean([1 for r in period_rets if r > 0]) if period_rets else np.nan
    win_rate = (sum(1 for r in period_rets if r > 0) / len(period_rets)) if period_rets else np.nan

    return {
        "total_return": total, "cagr": cagr, "vol": vol, "sharpe": sharpe,
        "sortino": sortino, "max_dd": max_dd, "calmar": calmar,
        "win_rate": win_rate, "avg_turnover": avg_turn,
        "n_rebalances": len(holdings_log), "n_days": n,
    }


def benchmark_curve(prices: pd.DataFrame, sym: str, dates: pd.DatetimeIndex) -> pd.Series:
    """Buy & hold equity curve for a benchmark on the strategy's calendar."""
    p = prices[sym].reindex(dates).ffill()
    return p / p.iloc[0]


def benchmark_metrics(prices: pd.DataFrame, sym: str, dates: pd.DatetimeIndex, rebalance: int) -> dict:
    eq = benchmark_curve(prices, sym, dates)
    dr = eq.pct_change().dropna()
    cfg = StratConfig(bench=sym, rebalance=rebalance)
    return compute_metrics(dr, eq / eq.iloc[0], [], cfg)
