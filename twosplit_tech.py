# -*- coding: utf-8 -*-
"""Two train/test splits on the TECH universe (129 stocks vs SOXX)."""
import os
import pickle
import fmp_data as fd
import tech_data as td
from twosplit import run_two_split, OUT


def main():
    tsyms = td.all_tickers() + ["SOXX", "QQQ"]
    px = fd.load_prices(tsyms)
    op = fd.load_prices(tsyms, field="open")
    stocks = [t for t in td.all_tickers() if t in px.columns]
    R = run_two_split(px, op, stocks, "SOXX", "TECH")
    pickle.dump(R, open(os.path.join(OUT, "twosplit_tech_results.pkl"), "wb"))
    print("\nsaved twosplit_tech_results.pkl")


if __name__ == "__main__":
    main()
