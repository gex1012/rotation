# -*- coding: utf-8 -*-
"""Comprehensive final PDF: methodology + param testing + industry & tech pipelines,
with holding-mechanics explanation, drawdown analysis and per-result commentary."""
import os
import pickle
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

from build_report import ST, df_table, img, kpi_band, bullet, hr, footer, OUT
from build_tech_report import warn_box


def _f(s):
    return float(str(s).replace(",", ""))


def verdict(row, bench_final, bench_sh):
    """One-line 评语 for a strategy row (dict from mrow)."""
    f, sh, dd = _f(row["最终$"]), row["夏普"], row["最大回撤%"]
    a = "跑赢基准金额" if f > bench_final else "金额逊于基准"
    b = "风险调整后不输" if sh >= bench_sh else f"夏普低于基准"
    c = "回撤偏深" if dd < -30 else ("回撤可控" if dd > -22 else "回撤中等")
    return f"{a}；{b}；{c}"


def commentary_block(df, bench_row, title="评语"):
    bf, bsh = _f(bench_row["最终$"]), bench_row["夏普"]
    best = df.loc[df["夏普"].idxmax()]; worst = df.loc[df["夏普"].idxmin()]
    items = [Paragraph(f"<b>{title}</b>", ST["h2"]),
             bullet(f"最优：<b>{best['策略']}</b>（夏普 {best['夏普']}、{best['最终$']}$、回撤 {best['最大回撤%']}%）—— {verdict(best, bf, bsh)}"),
             bullet(f"最弱：<b>{worst['策略']}</b>（夏普 {worst['夏普']}、回撤 {worst['最大回撤%']}%）—— {verdict(worst, bf, bsh)}")]
    return items


def universe_section(story, U, tag, is_tech=False):
    bench = U["bench"]; br = U["bench_row"]; bf, bsh = _f(br["最终$"]), br["夏普"]
    story += [Paragraph(f"{tag} · Q1–Q4 象限轮动 (vs {bench})", ST["h1"]), hr()]
    if is_tech:
        story += [warn_box("⚠️ <b>幸存者/选择偏差</b>：科技个股宇宙为当下已知热门标的，绝对收益被显著高估、"
                           "不可复现；此处仅看『象限相对关系 / 参数结构 / 回撤形态』。"), Spacer(1, 3 * mm)]
    story += [Paragraph(f"基准 {br['策略']}：{br['最终$']}$ · 年化 {br['年化%']}% · 夏普 {bsh} · 回撤 {br['最大回撤%']}%",
                        ST["small"]), Spacer(1, 2 * mm)]

    # ① holding @20d
    story += [Paragraph("① 各象限 holding 回测（固定 20 日换仓）", ST["h2"]),
              df_table(U["step2"], fontsize=8)]
    story += commentary_block(U["step2"], br)
    story += [PageBreak()]

    # ② parameter testing
    story += [Paragraph("② 参数回测（ZWIN × SMOOTH × MOM_LAG）", ST["h2"]),
              Paragraph("在代表性策略（全象限 top-5 · 20 日）上遍历参数网格，按夏普排序（前 8）：", ST["body"]),
              df_table(U["psweep"].head(8), fontsize=8),
              Spacer(1, 2 * mm),
              Paragraph("SCALE 不变性验证：仅改 SCALE（2.2 → 6.0）、其余不变，绩效完全一致，"
                        "证明 SCALE 只影响画图、不影响任何决策，故不纳入寻优：", ST["body"]),
              df_table(pd.DataFrame(U["scale_inv"]), col_widths=[30*mm, 40*mm, 40*mm, 45*mm], fontsize=8.5)]
    ps = U["psweep"]
    story += commentary_block(
        pd.DataFrame([{"策略": f"Z{r.ZWIN}/S{r.SMOOTH}/M{r.MOM_LAG}", "夏普": r["夏普"],
                       "最终$": "0", "最大回撤%": r["最大回撤%"]} for _, r in ps.head(6).iterrows()]),
        {"最终$": "0", "夏普": 0}, title="参数评语")
    story += [Paragraph(f"※ 结论：采用 <b>Z126/S8/M3</b>（半年标准化窗口更稳）。注意此为样本内寻优，"
                        "此前样本外检验显示参数会漂移，务必滚动验证。", ST["small"]), PageBreak()]

    # ③ holding-period optimisation + mechanics
    story += [Paragraph("③ 各象限持有周期寻优 + holding 机制说明", ST["h2"]),
              img(U["charts"]["heatmap"], width=150 * mm),
              df_table(U["step4"], fontsize=8),
              Spacer(1, 2 * mm),
              Paragraph("<b>holding 机制（回答『20日内象限变了怎么办』）</b>：策略<b>只在每 N 日的换仓点</b>"
                        "重新计算象限并重选 top-5；两个换仓点<b>之间持仓固定不动</b>——某标的即使在周期内离开了"
                        "原象限，也<b>持有到下一个换仓日才处理</b>，不做盘中/日内离场。这是刻意设计：换手更低、"
                        "成本更省、避免象限边界抖动带来的来回打脸。代价是拐点处反应慢一个周期。", ST["body"]),
              img(U["charts"]["singles"], width=163 * mm), Paragraph("各象限最优周期净值 vs 买入持有", ST["cap"])]
    story += commentary_block(U["step4"], br)
    story += [PageBreak()]

    # ④ adjacent merge + merged holding period
    qcn = {"Lead": "领先Q1", "Impr": "改善Q2", "Weak": "转弱Q4", "Lag": "落后Q3"}
    adjbp = "、".join(f"{qcn[a]}+{qcn[b]}@{r}d" for (a, b), r in U["adj_best"].items())
    story += [Paragraph("④ 相邻象限合并策略（RRG 轮动相邻 · 仅做多）", ST["h2"]),
              Paragraph("<b>合并后的持有周期怎么定</b>：不沿用单象限的周期，而是把合并组合<b>当作一个新策略</b>，"
                        "对其单独做 5–30 日的周期寻优，取其自身最优。下面 A 表为统一 20 日、B 表为各自最优周期。",
                        ST["body"]),
              Paragraph("A. 统一 20 日", ST["cap"]), df_table(U["step5"], fontsize=8),
              Spacer(1, 2 * mm), Paragraph(f"B. 各自最优周期（{adjbp}）", ST["cap"]),
              df_table(U["step5b"], fontsize=8)]
    story += commentary_block(U["step5b"], br)
    story += [PageBreak()]

    # ⑤ yearly + drawdown analysis
    story += [Paragraph("⑤ 逐年收益 + 最大回撤分析", ST["h2"]),
              df_table(U["ymat"], fontsize=7.5, bold_rows=[len(U["ymat"])])]
    # drawdown analysis
    allrows = pd.concat([U["step4"][["策略", "夏普", "最大回撤%"]], U["step5b"][["策略", "夏普", "最大回撤%"]]])
    deepest = allrows.loc[allrows["最大回撤%"].idxmin()]; shallow = allrows.loc[allrows["最大回撤%"].idxmax()]
    story += [Spacer(1, 2 * mm), Paragraph("最大回撤分析", ST["h2"]),
              bullet(f"回撤最深：<b>{deepest['策略']}</b> {deepest['最大回撤%']}%；最浅：<b>{shallow['策略']}</b> {shallow['最大回撤%']}%。"),
              bullet(f"全部象限策略回撤区间约 {allrows['最大回撤%'].min():.0f}% ~ {allrows['最大回撤%'].max():.0f}%，"
                     f"普遍深于 cap-weighted 基准 {br['最大回撤%']}%——等权 + 高波动细分标的在 2022 熊市回撤更大，"
                     "是本方法的主要风险敞口。"),
              bullet("弱动量象限（转弱/落后）虽收益高，但回撤也最深；改善象限回撤相对温和，风险调整后更均衡。"),
              PageBreak()]


def build(R):
    ind, tech = R["industry"], R["tech"]
    cost_bps = R["cost_bps"]; p = R["params"]
    s = []

    # cover
    s += [Spacer(1, 44 * mm), Paragraph("美股行业与科技板块 RRG 象限轮动", ST["title"]),
          Paragraph("理论 · 参数寻优 · 四象限持有 · 相邻象限合并 · 仅做多", ST["subtitle"]),
          Spacer(1, 8 * mm), hr(),
          Paragraph(f"成本 {cost_bps:.1f}bps/换手 · T+1 收盘成交 · 每象限 top-{R['topk']} 等权 · "
                    f"参数 Z{p['zwin']}/S{p['smooth']}/M{p['mom_lag']} · 2021 起 · $10万 · "
                    f"行业 vs SPY · 科技 vs {tech['bench']}", ST["cap"]),
          PageBreak()]

    # Part 1 methodology
    s += [Paragraph("第一部分 · 方法论与参数详解", ST["h1"]), hr(),
          Paragraph("1.1 RRG 四象限", ST["h2"]),
          Paragraph("每个板块相对基准的强弱被投影到二维平面：横轴 RS-Ratio（相对强度趋势）、"
                    "纵轴 RS-Momentum（该强度的动能），以 100 为界分四象限。", ST["body"]),
          df_table(pd.DataFrame([
              ["第一象限 领先 Lead", "Ratio≥100 & Mom≥100", "相对强且动能强化"],
              ["第二象限 改善 Impr", "Ratio<100 & Mom≥100", "相对弱但动能转强(早期)"],
              ["第四象限 转弱 Weak", "Ratio≥100 & Mom<100", "相对强但动能衰减"],
              ["第三象限 落后 Lag", "Ratio<100 & Mom<100", "相对弱且动能衰减"]],
              columns=["象限", "定义", "含义"]), col_widths=[46*mm, 55*mm, 74*mm], fontsize=9),
          Spacer(1, 3 * mm), Paragraph("1.2 计算链条", ST["h2"]),
          Paragraph("RS = 板块 / 基准 → RS_smooth = EMA(RS, SMOOTH) → "
                    "RS-Ratio = 100 + zscore(RS_smooth, ZWIN)×SCALE → "
                    "RawMom = RS-Ratio 的 MOM_LAG 日变化 → RS-Momentum = 100 + zscore(RawMom, ZWIN)×SCALE。", ST["body"]),
          Spacer(1, 3 * mm), Paragraph("1.3 四个参数详解", ST["h2"]),
          df_table(pd.DataFrame([
              ["ZWIN", str(p["zwin"]), "z-score 标准化窗口(交易日)。126≈半年。决定平滑/记忆长度",
               "调大→更平滑、更看长趋势、换手低、拐点慢；调小→更敏感、噪声大"],
              ["SMOOTH", str(p["smooth"]), "对原始 RS 线做 EMA 去噪的跨度",
               "调大→去噪更狠、反应更慢；调小→保留更多短期波动"],
              ["MOM_LAG", str(p["mom_lag"]), "动量的回溯步长(交易日)，衡量 Ratio 的变化速度",
               "调大→动量更平滑滞后；调小→动量更快、更易翻多翻空"],
              ["SCALE", str(p["scale"]), "仅把 z-score 缩放到 ~92–108 视觉区间",
               "★ 象限判定看 z 的符号、排序看等比放大后的相对值，均与 SCALE 无关→只影响画图"]],
              columns=["参数", "值", "含义", "调参效果"]),
              col_widths=[22*mm, 14*mm, 66*mm, 73*mm], fontsize=7.8),
          PageBreak(),
          Paragraph("1.4 回测规则", ST["h2"]),
          bullet(f"<b>仅做多</b>：每象限按打分选 top-{R['topk']} 等权，不足则留现金，<b>不做空</b>。"),
          bullet("<b>成交</b>：收盘价出信号，<b>T+1 收盘价</b>换仓（无前视）。"),
          bullet(f"<b>成本</b>：换手 notional × {cost_bps:.1f}bps（千分之0.4）。"),
          bullet("<b>holding</b>：仅在每 N 日换仓点重算象限并重选；周期内持仓固定，象限中途变化不即时离场（见各部分 ③）。"),
          bullet("<b>流程</b>：各象限固定周期 holding → 参数(ZWIN/SMOOTH/MOM_LAG)寻优 → 各象限持有周期寻优 → 相邻象限合并(其周期单独寻优)。"),
          PageBreak()]

    # Part 2 industry
    s += [Paragraph("第二部分 · 行业板块（37 细分行业 ETF）", ST["h1"]), hr()]
    universe_section(s, ind, "行业", is_tech=False)

    # Part 3 tech
    s += [Paragraph(f"第三部分 · 科技个股（129 只 vs {tech['bench']}）", ST["h1"]), hr()]
    universe_section(s, tech, "科技", is_tech=True)

    # Part 4 overall
    s += [Paragraph("第四部分 · 总结论与免责", ST["h1"]), hr(),
          bullet("<b>参数</b>：Z126/S8/M3（半年窗口）样本内最稳；SCALE 已验证不影响决策；参数与周期均存在过拟合，须滚动验证。"),
          bullet("<b>holding</b>：周期内不即时离场是刻意的低换手设计；短周期在 4bps 成本后仍被压缩。"),
          bullet("<b>合并象限</b>：其持有周期单独寻优，而非沿用单象限周期。"),
          bullet("<b>回撤</b>：象限策略回撤普遍深于 cap-weighted 基准，弱动量象限收益高但回撤最深。"),
          bullet(f"<b>科技(vs {tech['bench']})</b>：绝对业绩含幸存者偏差，仅作强弱监控/选股漏斗；可信回测需 point-in-time 成分。"),
          Spacer(1, 4 * mm), hr(), Paragraph("免责声明", ST["h2"]),
          Paragraph("本报告为历史数据规则化模拟，非真实交易；科技宇宙存在幸存者/选择偏差致业绩高估；"
                    "参数为样本内寻优、存在过拟合；不构成任何证券买卖建议。数据源 FMP，EOD 价格。", ST["small"])]

    out = os.path.join(OUT, "final_report.pdf")
    try:
        with open(out, "ab"):
            pass
    except PermissionError:
        out = os.path.join(OUT, "final_report_v2.pdf")
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=20 * mm,
                            title="行业与科技RRG象限轮动综合报告")
    doc.build(s, onLaterPages=footer)
    print("saved:", out)


if __name__ == "__main__":
    build(pickle.load(open(os.path.join(OUT, "final_results.pkl"), "rb")))
