# -*- coding: utf-8 -*-
"""Walk-forward report: 2018-21 定参 → 2022+ 实盘; 两模型(EMA/MA) x 两块(SPY/SOXX)."""
import os
import pickle
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

from build_report import ST, df_table, img, bullet, hr, footer, OUT
from build_final_report import make_formulas
from build_tech_report import warn_box


def _f(s):
    return float(str(s).replace(",", ""))


def verdict(row, bsh, bfin):
    a = "OOS金额赢基准" if _f(row["OOS最终$"]) > bfin else "OOS金额逊于基准"
    b = "OOS夏普≥基准" if row["OOS夏普"] >= bsh else "OOS夏普<基准"
    c = "回撤偏深" if row["OOS回撤%"] < -35 else "回撤可控"
    return f"{a}；{b}；{c}"


def commentary(df, bench_row):
    bsh, bfin = bench_row["OOS夏普"], _f(bench_row["OOS最终$"])
    best = df.loc[df["OOS夏普"].idxmax()]; worst = df.loc[df["OOS夏普"].idxmin()]
    return [bullet(f"最优：<b>{best['策略']}</b>（参数 {best['最优参数']}、holding {best['最优holding']}、"
                   f"OOS夏普 {best['OOS夏普']}、{best['OOS最终$']}$）—— {verdict(best, bsh, bfin)}"),
            bullet(f"最弱：<b>{worst['策略']}</b>（OOS夏普 {worst['OOS夏普']}）—— {verdict(worst, bsh, bfin)}")]


def model_section(story, B, mtag, bench, is_tech):
    M = B[mtag]; br = M["bench_row"]
    story += [Paragraph(f"{mtag} RRG", ST["h1"]), hr(),
              Paragraph(f"定参区间(IS) {B['IS']} → 实盘(OOS) {B['OOS']}　·　"
                        f"基准『买入持有{bench}』OOS：{br['OOS最终$']}$ / 年化 {br['OOS年化%']}% / "
                        f"夏普 {br['OOS夏普']} / 回撤 {br['OOS回撤%']}%。所有下列指标均为 <b>2022+ 实盘(OOS)</b>。", ST["small"]),
              Spacer(1, 2 * mm),
              Paragraph("Step 1 · 各象限（每象限在 IS 上选最优参数与 holding，再用于 OOS）", ST["h2"]),
              df_table(M["step1"], fontsize=7.6, bold_rows=[])]
    story += commentary(M["step1"], br)
    story += [Spacer(1, 2 * mm), Paragraph("Step1 · OOS PnL（含买入持有）", ST["cap"]),
              img(M["charts"]["s1"], width=163 * mm),
              PageBreak(), Paragraph("Step1 · 逐年 OOS 收益%（含买入持有）", ST["h2"]),
              df_table(M["s1_year"], fontsize=8, bold_rows=[len(M["s1_year"])]),
              Spacer(1, 3 * mm),
              Paragraph("Step 2 · 相邻象限合并（同法在 IS 选最优参数+holding → OOS）", ST["h2"]),
              df_table(M["step2"], fontsize=7.6)]
    story += commentary(M["step2"], br)
    story += [Spacer(1, 2 * mm), Paragraph("Step2 · OOS PnL（含买入持有）", ST["cap"]),
              img(M["charts"]["s2"], width=163 * mm),
              PageBreak(), Paragraph("Step2 · 逐年 OOS 收益%（含买入持有）", ST["h2"]),
              df_table(M["s2_year"], fontsize=8, bold_rows=[len(M["s2_year"])]), PageBreak()]


def ema_vs_ma(story, B):
    e1, m1 = B["EMA"]["step1"], B["MA"]["step1"]
    ebest = e1.loc[e1["OOS夏普"].idxmax()]; mbest = m1.loc[m1["OOS夏普"].idxmax()]
    story += [Paragraph("EMA vs MA · 小结", ST["h2"]),
              bullet(f"EMA 最佳象限：{ebest['策略']}（{ebest['最优参数']}/{ebest['最优holding']}）OOS夏普 {ebest['OOS夏普']}、{ebest['OOS最终$']}$"),
              bullet(f"MA 最佳象限：{mbest['策略']}（{mbest['最优参数']}/{mbest['最优holding']}）OOS夏普 {mbest['OOS夏普']}、{mbest['OOS最终$']}$"),
              bullet(f"→ 本块 <b>{'MA' if mbest['OOS夏普'] > ebest['OOS夏普'] else 'EMA'}</b> RRG 的最佳象限 OOS 夏普更高。"),
              PageBreak()]


def build(R):
    make_formulas()
    cost_bps = R["cost_bps"]
    s = []
    # cover
    s += [Spacer(1, 44 * mm), Paragraph("美股 RRG 象限轮动 · 样本外实盘研究", ST["title"]),
          Paragraph("2018-2021 定参 → 2022+ 实盘 · EMA/MA 双模型 · SPY / SOXX 两大块 · 仅做多", ST["subtitle"]),
          Spacer(1, 8 * mm), hr(),
          Paragraph(f"成本 {cost_bps:.0f}bps · T+1 收盘 · 每象限 top-{R['topk']} 等权 · "
                    f"新股 {R['min_hist']} 日护栏(≈3月，RRG 预热更严) · 所有业绩为 2022+ 实盘(OOS)", ST["cap"]),
          PageBreak()]
    # methodology (保留解释性文字)
    s += [Paragraph("第一部分 · 方法论", ST["h1"]), hr(),
          Paragraph("RRG 把每个板块相对基准投影到 RS-Ratio(横) × RS-Momentum(纵) 平面，以 100 为界分四象限："
                    "领先/改善/转弱/落后。本研究实现两套动量定义并对比：", ST["body"]),
          Paragraph("<b>EMA RRG</b>（z-score 版）：", ST["small"]), img(os.path.join(OUT, "formula_ema.png"), width=150 * mm),
          Paragraph("<b>MA RRG</b>（长期相对趋势 ROC/均线版）：", ST["small"]), img(os.path.join(OUT, "formula_ma.png"), width=150 * mm),
          Spacer(1, 3 * mm), Paragraph("回测与筛选规则", ST["h2"]),
          bullet("<b>样本外</b>：<b>所有参数与 holding 都只在 2018-2021 上择优</b>，原封不动用于 2022+『实盘』；报告业绩全为 OOS。"),
          bullet(f"<b>逐步筛选</b>：Step1 每象限——先在 holding=20 下选最优模型参数，再在该参数下选最优 holding 跨度；"
                 f"Step2 把相邻象限合并、同法各自寻优。EMA、MA 两模型分别独立做。"),
          bullet(f"<b>仅做多</b>：每象限并集按 score=(Ratio−100)+1.5×(Mom−100) 选 top-{R['topk']} 等权，不足留现金，不做空。"),
          bullet(f"<b>成交/成本</b>：T+1 收盘价换仓；换手 × {cost_bps:.0f}bps。"),
          bullet(f"<b>新股护栏</b>：上市不足 {R['min_hist']} 交易日(≈3月)的股票不参与；且 RRG 需 6–14 月预热，天然把次新股排除在外——"
                 "从而剔除『次新股暴涨』带来的虚高超额。"),
          PageBreak()]

    # Block SPY then SOXX (科技在后)
    for key, title, is_tech in [("SPY", "第二部分 · 行业板块（37 ETF · 基准 SPY）", False),
                                ("SOXX", "第三部分 · 科技个股（129 只 · 基准 SOXX）", True)]:
        B = R[key]
        s += [Paragraph(title, ST["h1"]), hr()]
        if is_tech:
            s += [warn_box("⚠️ 已用 2018→2022 样本外 + 3月新股护栏 + RRG 预热，<b>剔除了次新股暴涨的虚高</b>；"
                           "但宇宙仍为今日已知名单，<b>选择性幸存者偏差未完全消除</b>（须 point-in-time 成分才能彻底解决）。"),
                  Spacer(1, 2 * mm)]
        model_section(s, B, "EMA", B["bench"], is_tech)
        model_section(s, B, "MA", B["bench"], is_tech)
        ema_vs_ma(s, B)

    # conclusion
    s += [Paragraph("第四部分 · 结论（待你选择推进的模型）", ST["h1"]), hr(),
          bullet("本报告把所有策略统一到『2018-21 定参 → 2022+ 实盘』，消除了参数过拟合；两模型(EMA/MA)、两块(SPY/SOXX)、"
                 "Step1/Step2 的 OOS 结果与逐年、PnL 均已列出，供你选择推进哪套做进一步优化。"),
          bullet("科技块绝对收益仍偏高（选择性幸存者偏差），比较时以<b>相对基准的 OOS 夏普/超额</b>为准，勿看绝对值。"),
          Spacer(1, 4 * mm), hr(), Paragraph("免责声明", ST["h2"]),
          Paragraph("历史数据规则化模拟，非真实交易；科技宇宙存在选择性偏差；不构成投资建议。数据源 FMP，EOD 价格。", ST["small"])]

    out = os.path.join(OUT, "walkforward_report.pdf")
    try:
        with open(out, "ab"):
            pass
    except PermissionError:
        out = os.path.join(OUT, "walkforward_report_v2.pdf")
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=20 * mm, title="RRG样本外实盘研究报告")
    doc.build(s, onLaterPages=footer)
    print("saved:", out)


if __name__ == "__main__":
    build(pickle.load(open(os.path.join(OUT, "walkforward_results.pkl"), "rb")))
