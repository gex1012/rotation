# -*- coding: utf-8 -*-
"""
RRG model layer -- JdK RS-Ratio / RS-Momentum, computed as a FULL history so
the backtest can index into any past day without recomputing.

Chain (per sector vs a benchmark):
    RS         = Price_sector / Price_bench
    RS_smooth  = EMA(RS, span=SMOOTH)                    -- denoise
    RS_Ratio   = 100 + zscore(RS_smooth, ZWIN) * SCALE   -- x-axis
    RawMom     = RS_Ratio.diff(MOM_LAG)                  -- rate of change
    RS_Mom     = 100 + zscore(RawMom, ZWIN) * SCALE      -- y-axis

Quadrants:
    Lead  Ratio>=100 & Mom>=100   (领先)
    Weak  Ratio>=100 & Mom<100    (转弱)
    Lag   Ratio<100  & Mom<100    (落后)
    Impr  Ratio<100  & Mom>=100   (改善)

SCALE is cosmetic only: it scales both axes by the same factor, so it never
changes quadrant membership or the ranking used by the backtest. It's kept so
the numbers land in the familiar ~92-108 band.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RRGParams:
    zwin: int = 63      # z-score normalization window (trading days)
    smooth: int = 8     # EMA span to denoise raw RS
    scale: float = 2.2  # cosmetic spread multiplier (no effect on decisions)
    mom_lag: int = 5    # rate-of-change lag for momentum (trading days)

    def tag(self) -> str:
        return f"Z{self.zwin}_S{self.smooth}_M{self.mom_lag}"


def zscore(s: pd.Series, window: int) -> pd.Series:
    m = s.rolling(window).mean()
    sd = s.rolling(window).std()
    return (s - m) / sd


def quad(r: float, m: float) -> str:
    if r >= 100 and m >= 100:
        return "Lead"
    if r >= 100 and m < 100:
        return "Weak"
    if r < 100 and m < 100:
        return "Lag"
    return "Impr"


QUAD_CN = {"Lead": "领先", "Weak": "转弱", "Lag": "落后", "Impr": "改善"}
QUAD_QUADRANT = {"Lead": "第一象限", "Impr": "第二象限", "Lag": "第三象限", "Weak": "第四象限"}


def rrg_series(price: pd.Series, bench: pd.Series, p: RRGParams) -> pd.DataFrame | None:
    """Full-history ratio/mom/state frame for one sector vs one benchmark, or
    None if there isn't enough overlapping history."""
    df = pd.concat([price.rename("price"), bench.rename("b")], axis=1).dropna()
    if len(df) < p.zwin + p.mom_lag + p.smooth + 10:
        return None
    rs = df["price"] / df["b"]
    rs_smooth = rs.ewm(span=p.smooth, adjust=False).mean()
    rs_ratio = 100 + zscore(rs_smooth, p.zwin) * p.scale
    raw_mom = rs_ratio.diff(p.mom_lag)
    rs_mom = 100 + zscore(raw_mom, p.zwin) * p.scale
    out = pd.concat(
        [df["price"], rs_ratio.rename("ratio"), rs_mom.rename("mom")], axis=1
    ).dropna()
    if out.empty:
        return None
    out["state"] = [quad(r, m) for r, m in zip(out["ratio"], out["mom"])]
    # distance from origin (100,100) and days-in-current-state, both used downstream
    out["dist"] = np.sqrt((out["ratio"] - 100) ** 2 + (out["mom"] - 100) ** 2)
    change = (out["state"] != out["state"].shift()).cumsum()
    out["days"] = out.groupby(change).cumcount() + 1
    out["dRatio5"] = out["ratio"].diff(5)
    out["dMom5"] = out["mom"].diff(5)
    return out


def build_rrg_panel(prices: pd.DataFrame, sectors, bench_sym: str, p: RRGParams) -> dict:
    """Return {sector_symbol: rrg_series DataFrame} for every sector that has
    enough history vs the given benchmark."""
    bench = prices[bench_sym].dropna()
    panel = {}
    for sym in sectors:
        if sym not in prices.columns:
            continue
        s = rrg_series(prices[sym].dropna(), bench, p)
        if s is not None:
            panel[sym] = s
    return panel
