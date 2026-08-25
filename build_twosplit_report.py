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
              PageBreak()]


def drawdown_section(story, DD):
    story += [Paragraph("第五部分 · 回撤剖析与规避建议", ST["h1"]), hr(),
              Paragraph("各象限策略(top-5 · 20日 · MA·LR250/LM60/S10 · 2021起)的最大回撤：发生时点、深度、"
                        "回补时间。水下曲线见下。", ST["body"])]
    for tag in ["行业", "科技"]:
        U = DD[tag]
        story += [Paragraph(f"{tag} · 各象限最大回撤", ST["h2"]),
                  df_table(U["df"], fontsize=8, bold_rows=[len(U["df"])]),
                  Spacer(1, 1.5 * mm), img(U["chart"], width=160 * mm), PageBreak()]
    story += [Paragraph("为什么会出现最大回撤（逐象限归因）", ST["h2"]),
              bullet("<b>领先Q1（两宇宙都最深, -42%/-68%）</b>：峰在 2021 底/2022 初(成长动量顶)、谷在 2022-10(熊底)。"
                     "领先象限装『又强又热』的高动量/成长/投机票(科技尤甚)，2022 加息把长久期高 beta 杀得最惨，远超基准。"
                     "拥挤龙头=最深回撤，科技 Q1 熬到 2024-11 才回本(水下3年)。"),
              bullet("<b>转弱Q4</b>：『买强势回调』在<b>持续下跌里失效</b>——行业 Q4 在 2022 熊市里高Ratio但走弱的票一路跌到 2023 初；"
                     "科技 Q4 的最大回撤竟是 2025-10→12 那波半导体/AI 急跌(它持的强势票当时已 extended)。"),
              bullet("<b>落后Q3</b>：本就装弱势板块，熊市里『弱者恒弱』跟跌，无相对强度支撑。"),
              bullet("<b>改善Q2（最浅、修复最快）</b>：弱转强早期、不拥挤、估值未极端，2022 挨打较轻、反弹先启动；"
                     "科技 Q2 谷 2022-12、2023-06 就回本。"),
              bullet("<b>共性</b>：主因是 2022 加息熊(多数峰2021-22初/谷2022-10)；等权 top-5 集中+高波动细分 → 普遍比 cap-weighted 基准回撤深。"),
              Spacer(1, 3 * mm), Paragraph("如何规避大回撤（建议）", ST["h2"]),
              bullet("<b>① 降 Q1、抬 Q2 权重</b>：Q1 是回撤最大的敞口(尤其熊市)，Q2 最抗跌、修复最快；"
                     "组合里给 Q1 减配、Q2 加配，能显著压低整体回撤。"),
              bullet("<b>② 给强动量象限(Q1/Q4)加趋势关</b>：基准跌破 200 日线(且 200 线下行)时，"
                     "对 Q1/Q4 敞口减仓/转现金(仅做多、不做空)——2022 那种单边熊能少挨打；用『收回 50 日线』快出避免 whipsaw。"),
              bullet("<b>③ 别在下跌趋势里买 Q4 回调</b>：Q4『买强势回调』只在趋势/震荡市成立；"
                     "叠加一个大盘趋势过滤(200线之上才开 Q4)，避免把回调买成接飞刀。"),
              bullet("<b>④ 分散/限单票权重</b>：等权 top-5 过于集中；可扩到 top-8~10 或对单票设上限，降低个股暴雷冲击。"),
              bullet("<b>⑤ 现金缓冲</b>：象限内合格标的不足时留现金(本报告已如此)，天生在极端普跌时降暴露。"),
              Spacer(1, 2 * mm),
              Paragraph("⚠️ 以上『趋势关/择时』属可选增强，会牺牲部分上行(whipsaw 成本)换回撤更浅；"
                        "且同样有过拟合风险，需跨 regime 验证。", ST["small"]), PageBreak()]


def build(Rind, Rtech):
    from build_final_report import make_formulas
    from build_scoremethod_report import make_score_formulas
    make_formulas(); make_score_formulas()
    DD = None
    ddp = os.path.join(OUT, "drawdown_results.pkl")
    if os.path.exists(ddp):
        DD = pickle.load(open(ddp, "rb"))
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
          Paragraph("选股打分公式（本报告 Step1/Step2 默认用『综合 score』；RSRatio=横轴, RSMom=纵轴, 均以100为界）：", ST["small"]),
          img(os.path.join(OUT, "formula_scores.png"), width=150 * mm),
          bullet("<b>Step1 选股</b>：在单个象限内，按综合 score=(RSRatio−100)+1.5×(RSMom−100) 排序取 top-5 等权(各1/5)，"
                 "不足留现金，不做空。"),
          bullet("<b>Step2 相邻象限合并选股（重点说明）</b>：把相邻<b>两象限的成分并成一个池子一起竞争</b>，"
                 "按<b>同一个</b> score 排序，取<b>全场最高的 5 个、等权(各1/5)</b>——<b>不是</b>每象限各取5(那样会是10只1/10)，"
                 "<b>也不是</b>按离原点距离；某象限可能占4个、另一个占1个，谁强谁多。不足5个留现金。"),
          bullet("<b>逐步寻优</b>：Step1 每象限先在 holding=20 选最优参数、再选最优 holding；"
                 "Step2 把<b>合并组合当作一个新策略</b>，对其单独做 5–30 天周期寻优，<b>不沿用单象限的周期</b>；EMA/MA 各自独立。"),
          bullet("<b>相邻</b>指 RRG 轮动相邻：改善→领先→转弱→落后→改善，故 4 组相邻对为 Q1+Q2、Q1+Q4、Q4+Q3、Q3+Q2。"),
          bullet("新股 63 日护栏 + RRG 6–14 月预热天然排除次新股。成交 T+1 收盘，成本 20bps。"),
          PageBreak()]
    universe_block(s, Rind, "行业板块（70 ETF vs SPY）", "SPY", False, 2)
    universe_block(s, Rtech, "科技个股（129 只 vs SOXX）", "SOXX", True, 3)
    s += [Paragraph("第四部分 · 横向对比", ST["h1"]), hr()]
    comparison(s, Rind, Rtech)
    if DD is not None:
        drawdown_section(s, DD)
    s += [hr(), Paragraph("免责声明", ST["h2"]),
          Paragraph("历史数据规则化模拟，非真实交易；科技宇宙存在选择性偏差；参数为样本内寻优、存在过拟合；"
                    "不构成投资建议。数据源 FMP，EOD 价格。", ST["small"])]

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
