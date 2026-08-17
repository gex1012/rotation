# -*- coding: utf-8 -*-
"""
One-command full refresh of the RRG dashboard.

  1. force-fetch fresh close+open for every industry ETF + tech stock + SPY/QQQ
  2. rebuild industry & tech RRG snapshots (current quadrants)
  3. re-run the full quadrant pipeline (best periods, adjacent combos, holdings/changes)
  4. regenerate output/dashboard.html

Run manually:   python refresh_dashboard.py
Scheduled:      wired via Windows Task Scheduler (see setup notes).
The Artifact URL is only updated when Claude re-publishes output/dashboard.html.
"""
import sys
import datetime

import fmp_data as fd
import tech_data as td
import industry2 as ind2
import build_industry_snapshot
import final_pipeline
import build_dashboard


def refresh(force=True):
    t0 = datetime.datetime.now()
    print(f"[{t0:%Y-%m-%d %H:%M:%S}] refresh start (force={force})")

    syms = sorted(set(fd.all_symbols()) | set(td.all_tickers())
                  | set(ind2.all_tickers()) | {"SPY", "QQQ", "SOXX"})
    # one pass with max_age_hours=0 refreshes both open+close CSV caches
    fd.load_prices(syms, max_age_hours=(0 if force else 12))
    print(f"  fetched {len(syms)} symbols")

    td.build_snapshot()               # -> output/tech_rrg.json
    build_industry_snapshot.main()    # -> output/industry_rrg.json
    final_pipeline.main()             # -> output/final_results.pkl
    path = build_dashboard.build()    # -> output/dashboard.html

    dt = (datetime.datetime.now() - t0).total_seconds()
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] done in {dt:.0f}s -> {path}")
    return path


if __name__ == "__main__":
    refresh(force=("--cache" not in sys.argv))
