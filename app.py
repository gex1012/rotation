# -*- coding: utf-8 -*-
"""
Streamlit host for the RRG dashboard.
  streamlit run app.py     (or: python -m streamlit run app.py)

Embeds the self-contained interactive panel (行业/科技/持仓 tabs) and adds a live
refresh button + natively-rendered backtest tables.
"""
import os
import sys
import json
import pickle
import subprocess
import datetime
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)

st.set_page_config(page_title="RRG 象限轮动看板", layout="wide", page_icon="🎛️")

# cloud: expose the Streamlit secret as an env var so the data layer can fetch
try:
    if "FMP_API_KEY" in st.secrets:
        os.environ["FMP_API_KEY"] = st.secrets["FMP_API_KEY"]
except Exception:
    pass


def _run_refresh():
    return subprocess.run([sys.executable, os.path.join(HERE, "refresh_dashboard.py")],
                          cwd=HERE, capture_output=True, text=True,
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})


NEEDED = ["tech_rrg.json", "industry_rrg.json", "final_results.pkl", "dashboard.html"]
if not all(os.path.exists(os.path.join(OUT, f)) for f in NEEDED):
    st.title("🎛️ RRG 象限轮动看板")
    st.warning("首次运行：数据文件尚未生成。点击下方按钮拉取行情并构建看板（约 9 分钟）。")
    if not (os.environ.get("FMP_API_KEY") or os.path.exists(os.path.join(HERE, ".fmp_api_key"))):
        st.error("未检测到 FMP_API_KEY。请在 Streamlit Secrets 或环境变量中设置后重试。")
        st.stop()
    if st.button("▶ 生成数据 (约 9 分钟)"):
        with st.spinner("首次构建中：取数 → 象限快照 → 回测 → 生成看板…"):
            r = _run_refresh()
        if r.returncode == 0:
            st.rerun()
        else:
            st.error("构建失败："); st.code(r.stderr[-2000:])
    st.stop()


def load():
    tech = json.load(open(os.path.join(OUT, "tech_rrg.json"), encoding="utf-8"))
    ind = json.load(open(os.path.join(OUT, "industry_rrg.json"), encoding="utf-8"))
    R = pickle.load(open(os.path.join(OUT, "final_results.pkl"), "rb"))
    html = open(os.path.join(OUT, "dashboard.html"), encoding="utf-8").read()
    return tech, ind, R, html


tech, ind, R, html = load()

# ---- header ----
c1, c2 = st.columns([4, 1])
with c1:
    st.markdown("### 🎛️ RRG 象限轮动看板")
    st.caption(f"行业(vs {ind['bench']})截至 {ind['asof']} · 科技(vs {tech['bench']})截至 {tech['asof']} · "
               f"成本 {R['cost_bps']}bps · {R['exec']} · 每象限 top-{R['topk']} · 仅做多")
with c2:
    if st.button("🔄 立即刷新数据", use_container_width=True,
                 help="强制拉最新行情并重算全流程，约 9 分钟"):
        with st.spinner("刷新中：取数 → 象限快照 → 回测 → 重生成看板（约 9 分钟）…"):
            r = _run_refresh()
        if r.returncode == 0:
            st.success("已刷新到最新数据"); st.cache_data.clear(); st.rerun()
        else:
            st.error("刷新失败："); st.code(r.stderr[-1500:])
    mt = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(OUT, "dashboard.html")))
    st.caption(f"数据更新于 {mt:%Y-%m-%d %H:%M}")

# ---- interactive panel (行业 / 科技 / 持仓) ----
st.components.v1.html(html, height=1500, scrolling=True)

# ---- native backtest tables ----
st.divider()
st.markdown(f"#### 📊 回测数据表 ({R['cost_bps']:.0f}bps 成本 · T+1 收盘 · 仅做多)")
for uni in ("industry", "tech"):
    U = R[uni]
    with st.expander(f"{U['tag']} (vs {U['bench']}) · 回测结果", expanded=(uni == "industry")):
        st.markdown("**① 各象限最优周期比较**")
        st.dataframe(U["step4"], use_container_width=True, hide_index=True)
        st.markdown("**② 相邻象限合并策略**")
        st.dataframe(U["step5"], use_container_width=True, hide_index=True)
        st.markdown("**③ 逐年收益% (最优周期 + 相邻合并 + 基准)**")
        st.dataframe(U["ymat"], use_container_width=True, hide_index=True)
        st.caption(f"基准 {U['bench_row']['策略']}：{U['bench_row']['最终$']} · 夏普 {U['bench_row']['夏普']}"
                   + ("　⚠️ 科技绝对收益含幸存者偏差，仅看相对关系" if uni == "tech" else ""))

st.caption("提示：本地已配 Windows 计划任务每天 08:07 自动刷新；也可点右上『立即刷新』手动更新。仅供研究，非投资建议。")
