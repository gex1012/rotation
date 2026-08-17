# -*- coding: utf-8 -*-
"""Two-split comparison report (new 70-ETF industry universe vs SPY)."""
import os
import pickle
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

from build_report import ST, df_table, img, bullet, hr, footer, OUT


def _f(s):
    return float(str(s).replace(",", ""))


def best_of(df):
    return df.loc[df["OOS夏普"].idxmax()]


def model_block(story, M, mtag, cname):
    b = M["bench"]
    story += [Paragraph(f"{cname} · {mtag} RRG", ST["h2"]),
              Paragraph(f"基准买入持有SPY(OOS)：{b['OOS最终$']}$ / 年化 {b['OOS年化%']}% / 夏普 {b['OOS夏普']} / 回撤 {b['OOS回撤%']}%",
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


def build(R):
    from build_final_report import make_formulas
    make_formulas()
    s = []
    s += [Spacer(1, 44 * mm), Paragraph("行业 RRG · 两种训练/测试划分对比", ST["title"]),
          Paragraph("新 70-ETF 宇宙 · 基准 SPY · EMA/MA 双模型 · 仅做多 · 20bps · T+1 收盘", ST["subtitle"]),
          Spacer(1, 8 * mm), hr(),
          Paragraph("Section A：IS 2018-2021 → OOS 2022+　|　Section B：IS 2021-2023 → OOS 2024+　"
                    "（所有参数与 holding 都在各自 IS 上择优，业绩为各自 OOS）", ST["cap"]),
          PageBreak(),
          Paragraph("方法论（简）", ST["h1"]), hr(),
          Paragraph("同一套 RRG 四象限轮动，两种动量定义：", ST["body"]),
          Paragraph("EMA RRG（z-score 版）：", ST["small"]), img(os.path.join(OUT, "formula_ema.png"), width=145 * mm),
          Paragraph("MA RRG（ROC/均线版）：", ST["small"]), img(os.path.join(OUT, "formula_ma.png"), width=145 * mm),
          bullet("每象限并集按 score=(Ratio−100)+1.5×(Mom−100) 选 top-5 等权，不足留现金，不做空。"),
          bullet("逐步筛选：先 holding=20 选最优参数，再选最优 holding；Step2 相邻象限合并同法。"),
          bullet("新股 63 日护栏 + RRG 6–14 月预热天然排除次新股。"),
          PageBreak()]

    for cname in R["configs"]:
        C = R[cname]
        s += [Paragraph(f"Section {cname}", ST["h1"]), hr(),
              Paragraph(f"训练(IS) {C['IS']} → 实盘(OOS) {C['OOS']}", ST["small"]), Spacer(1, 2 * mm)]
        model_block(s, C["EMA"], "EMA", cname)
        model_block(s, C["MA"], "MA", cname)

    # comparison
    rows = []
    for cname in R["configs"]:
        C = R[cname]
        for m in ["EMA", "MA"]:
            bs = best_of(C[m]["step1"])
            rows.append({"划分": cname, "模型": m, "最佳象限": bs["策略"],
                         "参数/holding": f"{bs['参数']}/{bs['holding']}", "OOS夏普": bs["OOS夏普"],
                         "OOS年化%": bs["OOS年化%"], "基准SPY夏普": C[m]["bench"]["OOS夏普"],
                         "超基准?": "✓" if bs["OOS夏普"] >= C[m]["bench"]["OOS夏普"] else "✗"})
    comp = pd.DataFrame(rows)
    # ascii-safe check marks
    comp["超基准?"] = comp["超基准?"].str.replace("✓", "是").str.replace("✗", "否")
    s += [Paragraph("两划分横向对比与原因分析", ST["h1"]), hr(),
          df_table(comp, fontsize=8),
          Spacer(1, 3 * mm), Paragraph("为什么两个划分结果不同？", ST["h2"]),
          bullet("<b>OOS 市场 regime 不同</b>：A 的 OOS(2022+) 含 2022 大熊市 + 2023-24 修复，是『先跌后涨』；"
                 "B 的 OOS(2024+) 基本是单边牛市。趋势市更利于 MA/趋势跟随，震荡/反转段更考验模型。"),
          bullet("<b>训练 regime 不同</b>：A 在 2018-2021(含2020疫情V反转)上选参；B 在 2021-2023(含2022熊)上选参——"
                 "选出的最优参数/holding 因训练环境不同而不同，泛化到各自 OOS 的效果也不同。"),
          bullet("<b>宇宙可用性不同</b>：11 个较新 ETF(AIQ/QTUM/SRVR 等)在 A 的 IS(2018-21)里历史很薄、"
                 "常被 RRG 预热挡在外；到 B 的 IS(2021-23)已成熟可选——B 的候选池更完整。"),
          bullet("<b>OOS 长度不同</b>：A 的 OOS 约 4.6 年样本更长、更稳；B 的 OOS 约 2.6 年更短、噪声更大、"
                 "极端行情权重更高。短样本的夏普更容易被单一年份主导。"),
          Spacer(1, 3 * mm),
          Paragraph("结论：两划分若<b>同时</b>指向某模型/象限占优，该结论更稳健；若结论相反，多半是上述"
                    "regime/样本差异所致，应以更长 OOS(A) 为主、B 作为近端验证。", ST["body"]),
          Spacer(1, 4 * mm), hr(), Paragraph("免责声明", ST["h2"]),
          Paragraph("历史数据规则化模拟，非真实交易；不构成投资建议。数据源 FMP，EOD 价格。", ST["small"])]

    out = os.path.join(OUT, "twosplit_report.pdf")
    try:
        with open(out, "ab"):
            pass
    except PermissionError:
        out = os.path.join(OUT, "twosplit_report_v2.pdf")
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=20 * mm, title="行业RRG两划分对比报告")
    doc.build(s, onLaterPages=footer)
    print("saved:", out)


if __name__ == "__main__":
    build(pickle.load(open(os.path.join(OUT, "twosplit_results.pkl"), "rb")))
