# -*- coding: utf-8 -*-
"""Second PDF: Tech-sector RRG rotation vs QQQ. Reuses build_report helpers."""
import os
import pickle
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

import tech_data as td
from build_report import ST, df_table, img, kpi_band, bullet, hr, footer, OUT


def warn_box(text):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    t = Table([[Paragraph(text, ST["body"])]], colWidths=[170 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff3cd")),
                           ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#d39e00")),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


def build(r):
    s = []
    asof = r["asof"]; snap = r["snap"]
    sub_row = r["summary"][r["summary"]["策略"].str.contains("子板块")].iloc[0]
    stk_row = r["summary"][r["summary"]["策略"].str.contains("个股")].iloc[0]

    # cover
    s += [Spacer(1, 42 * mm), Paragraph("美股科技板块 RRG 轮动", ST["title"]),
          Paragraph("129 个科技个股 + 21 个子板块 · 相对 QQQ 的四象限动量轮动", ST["subtitle"]),
          Spacer(1, 8 * mm), hr(),
          Paragraph(f"基准：QQQ（纳斯达克100）　|　数据：Financial Modeling Prep　|　截至 {asof}", ST["cap"]),
          Paragraph("配套交互面板（网页版）见随附 Artifact 链接。", ST["cap"]),
          Spacer(1, 60 * mm),
          Paragraph("本报告为历史回测研究，业绩为模拟，且存在下述幸存者偏差，不构成投资建议。", ST["small"]),
          PageBreak()]

    # exec summary + WARNING
    s += [Paragraph("一、执行摘要", ST["h1"]), hr(),
          kpi_band([(f"{r['n_stocks']}", "科技个股"), (f"{r['n_subs']}", "子板块"),
                    (f"{stk_row['夏普']}", "个股轮动夏普"), (f"{sub_row['夏普']}", "子板块轮动夏普"),
                    ("QQQ", "基准")]),
          Spacer(1, 5 * mm),
          warn_box("⚠️ <b>重要：幸存者/选择偏差警告</b>　本宇宙是<b>当下已知的热门科技标的</b>"
                   "（英伟达、Palantir、CoreWeave、IonQ、Oklo、AppLovin 等），其中不少是 2023–2026 的"
                   "大赢家，部分在 2021 年尚未上市。用『事后才知道的赢家名单』回测动量策略，收益必然极其亮眼"
                   "（个股轮动回测年化 55%、+1073%），<b>但这不可复现</b>——你无法在 2021 年就选中这份名单。"
                   "因此下文<b>绝对收益不可信</b>，仅『个股 vs 子板块 vs QQQ 的相对关系』与『当前象限分布』有参考价值。"),
          Spacer(1, 4 * mm),
          bullet("个股轮动 > 子板块轮动 > QQQ（夏普 1.33 > 1.14 > 0.78）：颗粒度越细、动量表达越强——"
                 "但这个排序同样被偏差放大。"),
          bullet("真正可用的产出是<b>当前四象限快照</b>与<b>子板块相对 QQQ 的强弱结构</b>（第四节），"
                 "以及配套的交互网页面板。"),
          PageBreak()]

    # methodology
    s += [Paragraph("二、方法论", ST["h1"]), hr(),
          bullet("RRG 相对 QQQ：RS = 个股(或子板块合成指数) / QQQ，经 EMA 平滑后标准化为 RS-Ratio(横轴)、"
                 "其变化率标准化为 RS-Momentum(纵轴)，分四象限：领先/改善/转弱/落后。"),
          bullet(f"参数 Z{td.PARAMS.zwin}/S{td.PARAMS.smooth}/M{td.PARAMS.mom_lag}（半年标准化窗口）。"),
          bullet("子板块合成指数 = 该子板块成分股等权、以首日收盘价归一后取均值。"),
          bullet("回测：每 20 交易日换仓，子板块选 top-5、个股选 top-10，等权，T+1 开盘成交，2021 起，$10万。"),
          PageBreak()]

    # universe
    s += [Paragraph("三、科技宇宙（21 子板块）", ST["h1"]), hr()]
    urows = []
    for sub, grp in td.TECH.items():
        urows.append([sub, str(len(grp)), "、".join(list(grp)[:8]) + ("…" if len(grp) > 8 else "")])
    s += [df_table(pd.DataFrame(urows, columns=["子板块", "数", "代表成分(节选)"]),
                   col_widths=[34 * mm, 12 * mm, 129 * mm], fontsize=7.6), PageBreak()]

    # current quadrant snapshot
    tally = {}
    for st in snap["stocks"]:
        tally[st["state"]] = tally.get(st["state"], 0) + 1
    strg = sorted([x for x in snap["stocks"] if x["strengthening"]], key=lambda z: -z["mom"])[:18]
    s += [Paragraph("四、当前四象限分布（vs QQQ）", ST["h1"]), hr(),
          Paragraph(f"个股象限分布：领先Q1 {tally.get('Lead',0)} · 改善Q2 {tally.get('Impr',0)} · "
                    f"转弱Q4 {tally.get('Weak',0)} · 落后Q3 {tally.get('Lag',0)}；走强(金边) "
                    f"{sum(1 for x in snap['stocks'] if x['strengthening'])} 只。", ST["body"]),
          img(r["charts"]["rrg"], width=155 * mm), Paragraph("子板块 RRG（金边=走强）", ST["cap"]),
          Spacer(1, 3 * mm), Paragraph("动能最强的走强个股 (top18)", ST["h2"]),
          df_table(pd.DataFrame([{"代码": x["ticker"], "名称": x["name"], "子板块": x["sub"],
                                  "象限": x["quadrant"], "RS-Mom": x["mom"], "20日%": x["ret20"]}
                                 for x in strg]), fontsize=8, hi_rows=list(range(1, len(strg) + 1))),
          PageBreak()]

    # backtest
    s += [Paragraph("五、回测结果（含偏差警告）", ST["h1"]), hr(),
          df_table(r["summary"], fontsize=8, bold_rows=[len(r["summary"])]),
          Spacer(1, 3 * mm), img(r["charts"]["pnl"], width=165 * mm),
          Paragraph("图：$10万本金净值。绝对收益受幸存者偏差严重放大，见执行摘要警告。", ST["cap"]),
          Spacer(1, 3 * mm), Paragraph("逐年收益%", ST["h2"]),
          df_table(r["ymat"], fontsize=8.5, bold_rows=[len(r["ymat"])]),
          PageBreak()]

    # holdings + conclusion
    s += [Paragraph("六、当前持仓与结论", ST["h1"]), hr(),
          Paragraph("子板块轮动 当前 top5：" + "、".join(r["hold_sub"]), ST["body"]),
          Paragraph("个股轮动 当前 top10：" + "、".join(r["hold_stk"]), ST["body"]),
          Spacer(1, 4 * mm),
          bullet("<b>用法建议</b>：把本套当作<b>科技内部强弱监控与选股漏斗</b>——用当前象限/走强名单做候选池，"
                 "而非直接照搬回测收益。"),
          bullet("<b>要得到可信回测</b>，须用<b>point-in-time 成分</b>（每个历史时点用当时真实存在、可交易的股票池），"
                 "并纳入退市/停牌标的，消除幸存者偏差。当前版本未做到，故绝对业绩仅供演示。"),
          Spacer(1, 4 * mm), hr(),
          Paragraph("免责声明", ST["h2"]),
          Paragraph("本报告为历史数据的规则化模拟，非真实交易结果；宇宙存在幸存者/选择偏差，绝对业绩显著高估；"
                    "不构成任何证券的买卖建议。数据源 FMP，价格为 EOD。", ST["small"])]

    out = os.path.join(OUT, "tech_report.pdf")
    try:
        with open(out, "ab"):
            pass
    except PermissionError:
        out = os.path.join(OUT, "tech_report_v2.pdf")
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=20 * mm, title="科技板块RRG轮动报告(vsQQQ)")
    doc.build(s, onLaterPages=footer)
    print("saved:", out)


if __name__ == "__main__":
    build(pickle.load(open(os.path.join(OUT, "tech_results.pkl"), "rb")))
