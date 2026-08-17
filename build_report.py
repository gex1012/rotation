# -*- coding: utf-8 -*-
"""
Build a full, webpage-style process report PDF from output/results.pkl.

Uses reportlab (Chinese via Microsoft YaHei). Sections:
  封面 -> 执行摘要 -> 方法论(RRG+参数) -> 行业宇宙 -> 回测设计 ->
  主表(默认参数) -> 主表(优化参数) -> 参数敏感性 -> 象限过滤 ->
  当前四象限快照+趋势(金边) -> 结论与建议 -> 免责声明
"""
import os
import pickle
import pandas as pd

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image, Table,
                                TableStyle, PageBreak, HRFlowable)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "output")

pdfmetrics.registerFont(TTFont("YaHei", "C:/Windows/Fonts/msyh.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("YaHeiBold", "C:/Windows/Fonts/msyhbd.ttc", subfontIndex=0))

INK = colors.HexColor("#1a2233")
ACCENT = colors.HexColor("#1f6feb")
GREEN = colors.HexColor("#1a9850")
RED = colors.HexColor("#d73027")
GOLD = colors.HexColor("#DAA520")
LIGHT = colors.HexColor("#eef2f7")
GREY = colors.HexColor("#5a6673")

styles = getSampleStyleSheet()


def S(name, **kw):
    base = dict(fontName="YaHei", textColor=INK, leading=15)
    base.update(kw)
    return ParagraphStyle(name, **base)


ST = {
    "title": S("title", fontName="YaHeiBold", fontSize=26, leading=32, textColor=INK, alignment=TA_CENTER),
    "subtitle": S("subtitle", fontSize=13, leading=20, textColor=GREY, alignment=TA_CENTER),
    "h1": S("h1", fontName="YaHeiBold", fontSize=16, leading=22, textColor=ACCENT, spaceBefore=6, spaceAfter=6),
    "h2": S("h2", fontName="YaHeiBold", fontSize=12.5, leading=18, textColor=INK, spaceBefore=8, spaceAfter=3),
    "body": S("body", fontSize=10, leading=16),
    "small": S("small", fontSize=8.5, leading=12, textColor=GREY),
    "cap": S("cap", fontSize=8.5, leading=12, textColor=GREY, alignment=TA_CENTER),
    "kpi": S("kpi", fontName="YaHeiBold", fontSize=20, leading=22, textColor=ACCENT, alignment=TA_CENTER),
    "kpil": S("kpil", fontSize=8.5, leading=11, textColor=GREY, alignment=TA_CENTER),
}


def hr():
    return HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#d0d7de"),
                      spaceBefore=4, spaceAfter=8)


def df_table(df, col_widths=None, fontsize=7.6, highlight_col=None, hi_rows=None,
             bold_rows=None, page_width=175 * mm):
    header = list(df.columns)
    data = [header] + df.astype(object).values.tolist()
    for r in range(1, len(data)):
        data[r] = ["" if (v is None or (isinstance(v, float) and pd.isna(v))) else v
                   for v in data[r]]
    ncol = len(header)
    if col_widths is None:
        col_widths = [page_width / ncol] * ncol
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "YaHei"),
        ("FONTNAME", (0, 0), (-1, 0), "YaHeiBold"),
        ("FONTSIZE", (0, 0), (-1, -1), fontsize),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.white),
        ("GRID", (0, 1), (-1, -1), 0.3, colors.HexColor("#e2e6ea")),
    ]
    for r in range(1, len(data)):
        if r % 2 == 0:
            style.append(("BACKGROUND", (0, r), (-1, r), LIGHT))
    if bold_rows:
        for r in bold_rows:
            style.append(("FONTNAME", (0, r), (-1, r), "YaHeiBold"))
            style.append(("TEXTCOLOR", (0, r), (-1, r), GREY))
    if hi_rows:
        for r in hi_rows:
            style.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#fff6d6")))
            style.append(("FONTNAME", (0, r), (-1, r), "YaHeiBold"))
    t.setStyle(TableStyle(style))
    return t


def img(path, width=175 * mm):
    from PIL import Image as PILImage
    w, h = PILImage.open(path).size
    return Image(path, width=width, height=width * h / w)


def kpi_band(items):
    """items: list of (value, label). Renders a row of KPI cards."""
    cells = []
    for val, lab in items:
        inner = Table([[Paragraph(val, ST["kpi"])], [Paragraph(lab, ST["kpil"])]],
                      colWidths=[165 * mm / len(items)])
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f8ff")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cfe0ff")),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        cells.append(inner)
    outer = Table([cells], colWidths=[170 * mm / len(items)] * len(items))
    outer.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 3),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
    return outer


def bullet(text):
    return Paragraph(f"•&nbsp;&nbsp;{text}", ST["body"])


# --- page furniture ---------------------------------------------------------
def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("YaHei", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(20 * mm, 12 * mm, "美股行业板块 RRG 轮动策略 · 回测研究报告")
    canvas.drawRightString(190 * mm, 12 * mm, f"第 {doc.page} 页")
    canvas.setStrokeColor(colors.HexColor("#d0d7de"))
    canvas.line(20 * mm, 15 * mm, 190 * mm, 15 * mm)
    canvas.restoreState()


def build(results):
    story = []
    asof = results["asof"]
    win = results["window"]
    bp, op = results["base_params"], results["opt_params"]
    main_df, opt_df = results["main_df"], results["opt_df"]
    q12_df, sweep_df = results["q12_df"], results["sweep_df"]
    snap_spy = results["snap_spy"]
    charts = results["charts"]
    n_sectors = len(results["sectors"])

    # ---------- COVER ----------
    story += [Spacer(1, 40 * mm),
              Paragraph("美股行业板块 RRG 轮动策略", ST["title"]),
              Paragraph("相对旋转图 (Relative Rotation Graph) 四象限动量轮动 · 多周期换仓回测", ST["subtitle"]),
              Spacer(1, 8 * mm), hr(),
              Paragraph(f"数据区间：{win[0]} 至 {win[1]}　|　回测标的：{n_sectors} 个细分行业 ETF", ST["cap"]),
              Paragraph(f"基准：SPY (标普500) / QQQ (纳斯达克100)　|　数据源：Financial Modeling Prep", ST["cap"]),
              Paragraph(f"生成日期：{asof}", ST["cap"]),
              Spacer(1, 60 * mm),
              Paragraph("本报告为量化策略回测研究，所有业绩均为历史模拟，不构成投资建议。", ST["small"]),
              PageBreak()]

    # ---------- 执行摘要 ----------
    story += [Paragraph("一、执行摘要", ST["h1"]), hr()]
    # 用超额收益选“最佳”，突出真正跑赢基准的那组；基准取优化网格同窗口的买入持有
    opt_strats = opt_df[opt_df["超额年化%"].notna()].copy()
    best_opt = opt_strats.loc[opt_strats["超额年化%"].astype(float).idxmax()]
    spy_bh = opt_df[opt_df["策略"] == "买入持有 SPY"].iloc[0]
    story += [kpi_band([
        (f"{n_sectors}", "细分行业数"),
        (f"{best_opt['年化%']}%", "最佳策略年化"),
        (f"+{best_opt['超额年化%']}%", "对SPY超额"),
        (f"{best_opt['夏普']}", "夏普"),
        (f"{best_opt['最大回撤%']}%", "最大回撤"),
    ]), Spacer(1, 3 * mm),
        Paragraph(f"最佳策略 = <b>{best_opt['策略']}</b>（优化参数 Z126/S8/M3）；"
                  f"同窗口 SPY 买入持有年化 {spy_bh['年化%']}%。", ST["small"]),
        Spacer(1, 4 * mm)]
    story += [
        bullet(f"<b>换仓频率存在明显甜蜜点</b>：5–15 天过于频繁，换手磨损收益；<b>20–25 天</b>综合最优，"
               f"与原文『提高换手率无法稳定提升收益』一致。"),
        bullet(f"<b>参数比换仓周期更关键</b>：把 RRG 标准化窗口 ZWIN 从默认 63 天（1季度）拉长到 "
               f"<b>126 天（半年）</b>，风险调整后收益发生质变——最佳组年化 {best_opt['年化%']}%、"
               f"夏普 {best_opt['夏普']}、回撤仅 {best_opt['最大回撤%']}%，优于 SPY 买入持有。"),
        bullet(f"<b>象限过滤（只选一二象限 Mom≥100）</b>验证了原文方向——一二象限未来表现更优——"
               f"但在本宇宙中为边际改善，且抬高换手。"),
        bullet(f"<b>细分行业宇宙</b>把选择性从『11 选 5』提升到『{n_sectors} 选 5』(~13%)，"
               f"科技被拆为半导体/软件/云计算/网络安全等，龙头得以集中表达。"),
        Spacer(1, 3 * mm),
        Paragraph("※ 结论稳健性：优化参数在全部 6 个换仓周期上一致改善，非单点过拟合；但半年窗口天然"
                  "更慢，牛市转熊拐点处仍会滞后。", ST["small"]),
        PageBreak()]

    # ---------- 方法论 ----------
    story += [Paragraph("二、方法论：RRG 相对旋转图", ST["h1"]), hr(),
              Paragraph("每个行业相对基准的强弱，被投影到二维平面的四个象限：", ST["body"]),
              Spacer(1, 2 * mm)]
    story += [df_table(pd.DataFrame([
        ["第一象限 · 领先 Leading", "RS-Ratio ≥ 100", "RS-Mom ≥ 100", "相对强且动能强化"],
        ["第二象限 · 改善 Improving", "RS-Ratio < 100", "RS-Mom ≥ 100", "相对弱但动能转强(早期信号)"],
        ["第三象限 · 落后 Lagging", "RS-Ratio < 100", "RS-Mom < 100", "相对弱且动能衰减"],
        ["第四象限 · 转弱 Weakening", "RS-Ratio ≥ 100", "RS-Mom < 100", "相对强但动能衰减"],
    ], columns=["象限", "横轴", "纵轴", "含义"]),
        col_widths=[52 * mm, 38 * mm, 38 * mm, 47 * mm], fontsize=9)]
    story += [Spacer(1, 4 * mm), Paragraph("计算链条", ST["h2"]),
              Paragraph("RS = 板块价格 / 基准价格　→　RS_smooth = EMA(RS, SMOOTH)　→　"
                        "RS-Ratio = 100 + zscore(RS_smooth, ZWIN)×SCALE　→　"
                        "RawMom = RS-Ratio 的 MOM_LAG 日变化　→　"
                        "RS-Momentum = 100 + zscore(RawMom, ZWIN)×SCALE", ST["body"]),
              Spacer(1, 3 * mm), Paragraph("四个参数", ST["h2"])]
    story += [df_table(pd.DataFrame([
        ["ZWIN", f"{bp['zwin']} / {op['zwin']}", "z-score 标准化窗口(交易日)", "调大→更平滑更看长趋势、换手低"],
        ["SMOOTH", f"{bp['smooth']}", "原始 RS 线的 EMA 去噪跨度", "调大→去噪更狠、反应更慢"],
        ["MOM_LAG", f"{bp['mom_lag']} / {op['mom_lag']}", "动量回溯步长(交易日)", "调小→动量更快、更易翻多翻空"],
        ["SCALE", f"{bp['scale']}", "仅缩放，落到 ~92–108 视觉区间", "★ 对选股/排序完全无影响，仅画图"],
    ], columns=["参数", "默认/优化", "含义", "调参效果"]),
        col_widths=[24 * mm, 26 * mm, 62 * mm, 63 * mm], fontsize=8.4)]
    story += [Spacer(1, 3 * mm),
              Paragraph("为什么 SCALE 不用测：象限判定只看 z 的符号(≥0 或 <0)，与 SCALE 无关；"
                        "排序打分中横纵轴被同一个 SCALE 等比放大，次序不变。故真正影响回测的只有 "
                        "ZWIN / SMOOTH / MOM_LAG 三个。", ST["small"]),
              PageBreak()]

    # ---------- 行业宇宙 ----------
    story += [Paragraph("三、行业宇宙（细分行业 ETF）", ST["h1"]), hr(),
              Paragraph(f"共 {n_sectors} 个行业/主题 ETF。将有流动性子行业 ETF 的宽基板块（尤其科技）拆分到"
                        "子行业，无法干净拆分的防御板块（必需消费/公用事业/地产/通信）保留宽基作为防御锚。",
                        ST["body"]), Spacer(1, 3 * mm)]
    secs = list(results["sectors"].items())
    rows = []
    for i in range(0, len(secs), 3):
        chunk = secs[i:i + 3]
        row = []
        for sym, nm in chunk:
            row += [sym, nm]
        while len(row) < 6:
            row += ["", ""]
        rows.append(row)
    story += [df_table(pd.DataFrame(rows, columns=["代码", "行业", "代码", "行业", "代码", "行业"]),
                       col_widths=[22 * mm, 36 * mm] * 3, fontsize=8.6)]
    story += [Spacer(1, 3 * mm),
              Paragraph("注：SMH∈XLK、XBI∈XLV 等子行业与其宽基母板存在重叠，属刻意设计——让科技/医疗内部"
                        "的强势细分得以在 top-5 中集中表达。", ST["small"]),
              PageBreak()]

    # ---------- 回测设计 ----------
    story += [Paragraph("四、回测设计", ST["h1"]), hr()]
    story += [bullet("<b>规则</b>：每 N 个交易日，按 RRG 综合打分 <font face='YaHeiBold'>score = (Ratio−100) + 1.5×(Mom−100)</font> "
                     "对全部行业排序，等权做多前 5 名，持有至下次换仓。"),
              bullet("<b>换仓周期</b>：N ∈ {5, 10, 15, 20, 25, 30} 交易日，各自独立回测。"),
              bullet("<b>基准双重角色</b>：SPY / QQQ 既作 RS 分母(定义相对强弱)，又作对比基线。"),
              bullet("<b>权重</b>：选中标的<b>等权</b>(各 1/5)；与原文一致，最稳健、不易过拟合。"),
              bullet("<b>成交时点 = T+1 开盘</b>：第 t 日收盘用截至 t 的数据算信号，第 t+1 日"
                     "<b>开盘价</b>成交。换仓当日收益拆成『旧组合持有至开盘 + 新组合开盘到收盘』两段，"
                     "无前视、贴近实盘（较同日收盘成交约损耗 1%+/年）。"),
              bullet("<b>缺额补齐</b>：象限过滤下若 Q1+Q2 不足 5 个，缺的仓位买<b>基准 ETF</b>"
                     "(全空则 100% 持基准，自动转防御)；另提供现金/集中/回退全体三种可选。"),
              bullet("<b>交易成本</b>：按换手 × 5bp 计入换仓日收益。"),
              bullet("<b>指标</b>：年化(CAGR)、年化波动、夏普、索提诺、最大回撤、Calmar、周期胜率、平均换手。"),
              PageBreak()]

    # ---------- 象限 PnL ----------
    quad_df = results.get("quad_df")
    if quad_df is not None and "quad_pnl" in charts and charts["quad_pnl"]:
        nq2 = len(quad_df)
        story += [Paragraph("四之二、四象限 PnL 验证（文章核心命题）", ST["h1"]), hr(),
                  Paragraph("把每个象限单独做成组合：每次换仓时买入当前落在该象限的<b>全部</b> ETF(等权)，"
                            "持有至下次换仓，四象限各成一条净值。用于直接检验『哪个象限未来表现更优』。",
                            ST["body"]),
                  df_table(quad_df, fontsize=8.4, bold_rows=[nq2 - 1]),
                  Spacer(1, 3 * mm), Paragraph("图：各象限组合净值 + 象限占用数量时序", ST["cap"]),
                  img(charts["quad_pnl"], width=170 * mm),
                  Paragraph("结论：<b>改善象限(Q2)风险调整后最优</b>(夏普最高)，印证原文『第二象限捕捉趋势反转"
                            "早期信号』；但本样本中<b>领先象限(Q1)年化最低</b>——板块『熬成领先』时往往涨势已尽，"
                            "与原文『一象限最优』略有出入。四象限单独均未跑赢 cap-weighted 的 SPY 夏普。", ST["small"]),
                  PageBreak()]

    # ---------- 主表 默认 ----------
    n = len(main_df)
    bold = [n - 1, n - 2]  # last two = buy&hold
    story += [Paragraph("五、主表结果 · 默认参数 Z63/S8/M5", ST["h1"]), hr(),
              df_table(main_df, fontsize=7.4, bold_rows=bold),
              Spacer(1, 3 * mm), Paragraph("图：各策略净值曲线（对数轴，虚线为买入持有基准）", ST["cap"]),
              img(charts["eq_def"], width=170 * mm),
              Paragraph("默认参数下绝对收益普遍跑输买入持有——2022–2026 大盘由超大权重科技股拉动，"
                        "等权轮动天然吃亏；但 20–25 天档的回撤与夏普已贴近基准。", ST["small"]),
              PageBreak()]

    # ---------- 主表 优化 ----------
    no = len(opt_df)
    story += [Paragraph("六、主表结果 · 优化参数 Z126/S8/M3", ST["h1"]), hr(),
              df_table(opt_df, fontsize=7.4, bold_rows=[no - 1, no - 2]),
              Spacer(1, 3 * mm), Paragraph("图：优化参数下各策略净值曲线", ST["cap"]),
              img(charts["eq_opt"], width=170 * mm),
              Paragraph("把标准化窗口拉长到半年后，多数换仓档的风险调整后收益系统性抬升，回撤显著收窄，"
                        "换手同时下降——这是全报告最重要的可执行结论。", ST["small"]),
              PageBreak()]

    # ---------- 参数敏感性 ----------
    story += [Paragraph("七、参数敏感性扫描", ST["h1"]), hr(),
              Paragraph("固定 SPY / 20 天换仓，对 ZWIN×SMOOTH×MOM_LAG 共 36 组网格逐一回测，按夏普排序。"
                        "以下为最优 12 组与最差 5 组：", ST["body"]), Spacer(1, 2 * mm),
              Paragraph("最优 12 组", ST["h2"]),
              df_table(sweep_df.head(12).reset_index(drop=True), fontsize=8, hi_rows=[1]),
              Spacer(1, 3 * mm), Paragraph("最差 5 组", ST["h2"]),
              df_table(sweep_df.tail(5).reset_index(drop=True), fontsize=8),
              Spacer(1, 3 * mm),
              Paragraph("排名前列几乎清一色 ZWIN=126：行业相对强度是慢变量，半年窗口标准化才稳；"
                        "默认 63 天窗口噪声过大，是默认档跑输的主因。", ST["small"]),
              PageBreak()]

    # ---------- 象限过滤 ----------
    nq = len(q12_df)
    story += [Paragraph("八、象限过滤对比（只从一、二象限选，默认参数）", ST["h1"]), hr(),
              df_table(q12_df, fontsize=7.4, bold_rows=[nq - 1, nq - 2]),
              Spacer(1, 3 * mm),
              Paragraph("要求候选行业动能 Mom≥100（一、二象限）后再排序 top-5。方向与原文一致——一二象限"
                        "未来表现更优——本宇宙中为边际改善，且换手略升。", ST["body"]),
              PageBreak()]

    # ---------- 当前快照 ----------
    story += [Paragraph("九、当前四象限分布与趋势", ST["h1"]), hr(),
              Paragraph(f"截至 {asof}，各细分行业相对 SPY 的 RRG 位置。"
                        "<font face='YaHeiBold' color='#DAA520'>金边圆点 = 仍在走强</font>"
                        "（动能 Mom≥100 且 5 日动能继续上行）。", ST["body"]),
              img(charts["rrg_spy"], width=165 * mm),
              Paragraph("基准 SPY", ST["cap"]), PageBreak(),
              Paragraph("相对 QQQ 的分布：", ST["body"]),
              img(charts["rrg_qqq"], width=165 * mm),
              Paragraph("基准 QQQ", ST["cap"]), Spacer(1, 4 * mm)]

    strengthening = snap_spy[snap_spy["strengthening"] == True]
    story += [Paragraph("仍在走强的板块（金边）", ST["h2"])]
    if len(strengthening):
        srows = strengthening[["sector", "symbol", "quadrant", "ratio", "mom", "dMom5", "days_in_state"]]
        srows = srows.rename(columns={"sector": "行业", "symbol": "代码", "quadrant": "象限",
                                      "ratio": "RS-Ratio", "mom": "RS-Mom", "dMom5": "5日动能变化",
                                      "days_in_state": "在象限天数"})
        story += [df_table(srows, fontsize=8.6, hi_rows=list(range(1, len(srows) + 1)))]
    else:
        story += [Paragraph("当前无板块满足『金边』条件（全部动能走弱）。", ST["body"])]
    story += [Spacer(1, 3 * mm),
              Paragraph("完整 37 行快照见随附 Excel（当前快照_vs_SPY / vs_QQQ 两个 sheet，"
                        "已按『走强优先→动能→强度』排序）。", ST["small"]),
              PageBreak()]

    # ---------- 结论 ----------
    story += [Paragraph("十、结论与建议", ST["h1"]), hr(),
              bullet("<b>推荐配置</b>：ZWIN=126 / SMOOTH=8 / MOM_LAG=3~5 / 换仓 20~25 天 / 细分行业宇宙 top-5 等权。"),
              bullet("<b>可执行含义</b>：该组合在 2022–2026 历史上做到风险调整后不输、回撤优于买入持有，且换手可控。"),
              bullet("<b>象限过滤</b>可作为可选增强（一二象限筛选），但预期为边际贡献。"),
              bullet("<b>局限</b>：半年窗口在牛熊拐点滞后；样本仅一个宏观周期（含 2022 熊市与其后修复），"
                     "建议滚动/分段再验证，并对交易成本与容量做压力测试。"),
              Spacer(1, 5 * mm), hr(),
              Paragraph("免责声明", ST["h2"]),
              Paragraph("本报告所有业绩均为基于历史数据的规则化模拟(backtest)，非真实交易结果，"
                        "不代表未来表现，不构成任何证券的买卖建议或投资咨询。数据源为 Financial Modeling Prep，"
                        "价格为其 EOD 收盘价。回测未完全计入冲击成本、滑点、税费与 ETF 跟踪误差。", ST["small"])]

    out_pdf = os.path.join(OUT, "rotation_report.pdf")
    try:                     # avoid clobbering a copy the user has open in a viewer
        with open(out_pdf, "ab"):
            pass
    except PermissionError:
        out_pdf = os.path.join(OUT, "rotation_report_v2.pdf")
    doc = SimpleDocTemplate(out_pdf, pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=20 * mm,
                            title="美股行业板块RRG轮动策略回测报告")
    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=footer)
    print("saved:", out_pdf)


if __name__ == "__main__":
    with open(os.path.join(OUT, "results.pkl"), "rb") as f:
        res = pickle.load(f)
    build(res)
