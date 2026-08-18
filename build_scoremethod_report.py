# -*- coding: utf-8 -*-
"""PDF: per-quadrant × scoring-method backtest matrix (行业 vs SPY, 科技 vs SOXX)."""
import os
import pickle
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

from build_report import ST, df_table, img, bullet, hr, footer, OUT


def best_per_quad(df):
    out = {}
    for q in df["象限"].unique():
        sub = df[df["象限"] == q]
        r = sub.loc[sub["夏普"].idxmax()]
        out[q] = (r["打分"], r["夏普"])
    return out


def uni_section(story, U, tag, part):
    df = U["df"]; bench = U["bench"]
    story += [Paragraph(f"第{part}部分 · {tag}（vs {bench}）", ST["h1"]), hr(),
              Paragraph("每个象限单独回测（该象限内 top-5 · 20 日 · 2021 起 · 20bps · T+1收盘），"
                        "分别用三种打分方式排序选股。夏普热力图（黑框=该象限最优打分）：", ST["body"]),
              img(U["chart"], width=145 * mm),
              Spacer(1, 2 * mm), Paragraph("完整数据（夏普 / 年化 / 最终$ / 回撤）", ST["h2"]),
              df_table(df, fontsize=8)]
    bp = best_per_quad(df)
    story += [Spacer(1, 2 * mm), Paragraph("各象限最优打分", ST["h2"])]
    for q, (m, s) in bp.items():
        story += [bullet(f"<b>{q}</b> → 最优打分 <b>{m}</b>（夏普 {s}）")]
    story += [PageBreak()]


def build(R):
    s = []
    s += [Spacer(1, 44 * mm), Paragraph("RRG 打分方式对比 · 每象限回测", ST["title"]),
          Paragraph("每个象限 × 三种打分方式（综合score / 纯动量 / 距离）· 仅做多 · 20bps · T+1收盘",
                    ST["subtitle"]),
          Spacer(1, 8 * mm), hr(),
          Paragraph("行业 70-ETF(vs SPY) + 科技 129股(vs SOXX) · 全样本 2021 起 · 每象限 top-5 · 20日换仓", ST["cap"]),
          PageBreak(),
          Paragraph("方法论 · 三种打分", ST["h1"]), hr(),
          Paragraph("同一象限内，用不同指标给候选标的排序，取分数最高的 top-5：", ST["body"]),
          df_table(pd.DataFrame([
              ["综合score", "(RS-Ratio−100) + 1.5×(RS-Momentum−100)", "带方向、动量加权，偏向又强又有动能的"],
              ["纯动量 mom", "RS-Momentum − 100", "只看动能，谁在加速选谁"],
              ["距离 dist", "√[(Ratio−100)² + (Mom−100)²]", "离原点最远=信号最极端(无符号)，偏向 Ratio 最高的强势票"]],
              columns=["打分", "公式", "含义"]),
              col_widths=[26 * mm, 68 * mm, 81 * mm], fontsize=8.5, wrap_cols=[1, 2]),
          PageBreak()]
    uni_section(s, R["行业"], "行业", 2)
    uni_section(s, R["科技"], "科技", 3)
    # conclusion
    s += [Paragraph("第四部分 · 结论", ST["h1"]), hr(),
          bullet("<b>最优打分方式随象限而变，没有一种通吃</b>——这是核心发现。"),
          bullet("<b>强动量象限(领先Q1)</b>：综合score / 纯动量更好（本就在冲，追动量对）。"),
          bullet("<b>转弱象限(Q4，强但减速)</b>：<b>距离dist 明显最好</b>（科技 Q4 距离夏普 1.39，vs score 0.99、mom 0.67）。"
                 "原因：距离选『离原点最远=相对强度最高』的强势回调票，而 score 的 −1.5×动量项会躲开它们。"),
          bullet("<b>改善Q2</b>：科技用距离、行业用综合score；<b>落后Q3</b>：普遍弱，意义有限。"),
          Spacer(1, 3 * mm), Paragraph("可执行推论：每象限用其最优打分的『混合打分』策略", ST["h2"]),
          bullet("领先Q1→综合score　·　改善Q2→距离　·　转弱Q4→距离　·　落后Q3→综合score"),
          bullet("科技里最亮：<b>转弱Q4 + 距离打分 = 夏普 1.39</b>，高于任何单一配置。"),
          Spacer(1, 4 * mm), hr(), Paragraph("免责声明", ST["h2"]),
          Paragraph("历史数据规则化模拟，非真实交易；科技宇宙存在选择性偏差；不构成投资建议。数据源 FMP，EOD 价格。", ST["small"])]

    out = os.path.join(OUT, "scoremethod_report.pdf")
    try:
        with open(out, "ab"):
            pass
    except PermissionError:
        out = os.path.join(OUT, "scoremethod_report_v2.pdf")
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=20 * mm, title="RRG打分方式每象限对比")
    doc.build(s, onLaterPages=footer)
    print("saved:", out)


if __name__ == "__main__":
    build(pickle.load(open(os.path.join(OUT, "quadscore_results.pkl"), "rb")))
