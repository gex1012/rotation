# -*- coding: utf-8 -*-
"""Two-split comparison report: 行业(70 ETF vs SPY) + 科技(129 vs SOXX), splits A/B."""
import os
import pickle
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

from build_report import ST, df_table, img, bullet, hr, footer, OUT
from build_tech_report import warn_box


def _f(s):
    return float(str(s).replace(",", ""))


def best_of(df):
    return df.loc[df["OOS夏普"].idxmax()]


def model_block(story, M, mtag, cname, bench):
    b = M["bench"]
    story += [Paragraph(f"{cname} · {mtag} RRG", ST["h2"]),
              Paragraph(f"基准买入持有{bench}(OOS)：{b['OOS最终$']}$ / 年化 {b['OOS年化%']}% / 夏普 {b['OOS夏普']} / 回撤 {b['OOS回撤%']}%",
                        ST["small"]),
              Paragraph("Step1 · 各象限（IS 定参+holding → OOS）", ST["cap"]),
              df_table(M["step1"], fontsize=7.8),
              Spacer(1, 1.5 * mm), img(M["charts"]["s1"], width=158 * mm),
              PageBreak(),
              Paragraph(f"{cname} · {mtag} · Step1 逐年 OOS%（含买入持有）", ST["cap"]),
              df_table(M["s1_year"], fontsize=8, bold_rows=[len(M["s1_year"])]),
              Spacer(1, 2 * mm), Paragraph("Step2 · 相邻象限合并", ST["cap"]),
              df_table(M["step2"], fontsize=7.8),
              Spacer(1, 1.5 * mm), img(M["charts"]["s2"], width=158 * mm), PageBreak()]


def universe_block(story, R, title, bench, is_tech, part_no):
    story += [Paragraph(f"第{part_no}部分 · {title}", ST["h1"]), hr()]
    if is_tech:
        story += [warn_box("⚠️ 已用两划分样本外 + 3月新股护栏 + RRG 预热剔除次新股暴涨；但宇宙仍为今日已知名单，"
                           "<b>选择性幸存者偏差未完全消除</b>。B 划分的 OOS(2024+)是单边牛市，绝对夏普整体虚高（连基准都被抬高），"
                           "解读时以『跨两划分是否都赢基准』为准。"), Spacer(1, 2 * mm)]
    for cname in R["configs"]:
        C = R[cname]
        story += [Paragraph(f"Section {cname}", ST["h2"]),
                  Paragraph(f"训练(IS) {C['IS']} → 实盘(OOS) {C['OOS']}", ST["small"]), Spacer(1, 1.5 * mm)]
        model_block(story, C["EMA"], "EMA", cname, bench)
        model_block(story, C["MA"], "MA", cname, bench)


def comparison(story, Rind, Rtech):
    rows = []
    for uni, R in [("行业", Rind), ("科技", Rtech)]:
        for cname in R["configs"]:
            C = R[cname]
            for m in ["EMA", "MA"]:
                bs = best_of(C[m]["step1"]); bh = C[m]["bench"]
                rows.append({"宇宙": uni, "划分": cname[0], "模型": m, "最佳象限": bs["策略"],
                             "OOS夏普": bs["OOS夏普"], "基准夏普": bh["OOS夏普"],
                             "超基准?": "是" if bs["OOS夏普"] >= bh["OOS夏普"] else "否"})
    comp = pd.DataFrame(rows)
    story += [Paragraph("横向对比与原因分析（行业 + 科技 × A/B）", ST["h1"]), hr(),
              df_table(comp, fontsize=8),
              Spacer(1, 3 * mm), Paragraph("核心结论", ST["h2"]),
              bullet("<b>MA RRG 跨划分更稳</b>：行业与科技，MA 在 A、B 两个划分下相对基准的表现都更一致；"
                     "EMA 只在顺风的 B(2024+牛市)出彩，含熊市的 A 常输基准——EMA 的优势 regime 依赖、脆弱。"),
              bullet("<b>绝对夏普高低主要由 OOS 行情决定，不是策略变强</b>：B 的 OOS(2024+)是单边牛，"
                     "连基准 SPY/SOXX 的夏普都从 A 的 0.70/0.82 抬到 1.27/1.20；策略的高夏普里含这块红利，须打折。"),
              Paragraph("为什么两划分结果不同？", ST["h2"]),
              bullet("<b>OOS regime</b>：A(2022+)含 2022 大熊+修复，先跌后涨；B(2024+)基本单边牛。趋势市利于趋势跟随(MA)。"),
              bullet("<b>训练 regime</b>：A 在 2018-21(含2020V反转)选参，B 在 2021-23(含2022熊)选参，选出的参数/holding 不同。"),
              bullet("<b>宇宙可用性</b>：较新标的(科技CRWV/RDDT、行业AIQ/QTUM)在 A 的 IS 里历史薄、被 RRG 预热挡掉；B 的候选池更全。"),
              bullet("<b>OOS 长度</b>：A 约 4.6 年更稳；B 约 2.6 年更短、单一牛市权重高，夏普易被一段行情主导。"),
              Spacer(1, 3 * mm),
              Paragraph("判读方法：<b>只信两划分同时成立的结论</b>（如『MA≥EMA』『MA 稳定接近/超基准』）；"
                        "只在单一划分出现的高夏普(如科技 B 的 EMA 领先Q1 1.93)当作 regime 红利、勿外推。", ST["body"]),
              Spacer(1, 4 * mm), hr(), Paragraph("免责声明", ST["h2"]),
              Paragraph("历史数据规则化模拟，非真实交易；科技宇宙存在选择性偏差；不构成投资建议。数据源 FMP，EOD 价格。", ST["small"])]


def build(Rind, Rtech):
    from build_final_report import make_formulas
    make_formulas()
    s = []
    s += [Spacer(1, 44 * mm), Paragraph("行业 + 科技 RRG · 两训练/测试划分对比", ST["title"]),
          Paragraph("行业70-ETF(vs SPY) + 科技129股(vs SOXX) · EMA/MA 双模型 · 划分 A/B · 仅做多 · 20bps · T+1收盘",
                    ST["subtitle"]),
          Spacer(1, 8 * mm), hr(),
          Paragraph("Section A：IS 2018-2021 → OOS 2022+　|　Section B：IS 2021-2023 → OOS 2024+　"
                    "（参数与 holding 都在各自 IS 择优，业绩为各自 OOS）", ST["cap"]), PageBreak(),
          Paragraph("第一部分 · 方法论（简）", ST["h1"]), hr(),
          Paragraph("同一套 RRG 四象限轮动，两种动量定义：", ST["body"]),
          Paragraph("EMA RRG（z-score 版）：", ST["small"]), img(os.path.join(OUT, "formula_ema.png"), width=145 * mm),
          Paragraph("MA RRG（ROC/均线版）：", ST["small"]), img(os.path.join(OUT, "formula_ma.png"), width=145 * mm),
          bullet("每象限并集按 score=(Ratio−100)+1.5×(Mom−100) 选 top-5 等权，不足留现金，不做空。"),
          bullet("逐步筛选：先 holding=20 选最优参数，再选最优 holding；Step2 相邻象限合并同法；EMA/MA 各自独立。"),
          bullet("新股 63 日护栏 + RRG 6–14 月预热天然排除次新股。"),
          PageBreak()]
    universe_block(s, Rind, "行业板块（70 ETF vs SPY）", "SPY", False, 2)
    universe_block(s, Rtech, "科技个股（129 只 vs SOXX）", "SOXX", True, 3)
    s += [Paragraph("第四部分 · 横向对比", ST["h1"]), hr()]
    comparison(s, Rind, Rtech)

    out = os.path.join(OUT, "twosplit_report.pdf")
    try:
        with open(out, "ab"):
            pass
    except PermissionError:
        out = os.path.join(OUT, "twosplit_report_v2.pdf")
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=20 * mm, title="行业科技RRG两划分对比报告")
    doc.build(s, onLaterPages=footer)
    print("saved:", out)


if __name__ == "__main__":
    Rind = pickle.load(open(os.path.join(OUT, "twosplit_results.pkl"), "rb"))
    Rtech = pickle.load(open(os.path.join(OUT, "twosplit_tech_results.pkl"), "rb"))
    build(Rind, Rtech)
