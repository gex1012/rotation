# RRG 象限轮动看板 — 本地运行 & Streamlit Cloud 部署

美股行业(vs SPY) / 科技个股(vs SOXX) 的 RRG 四象限轮动看板 + 回测。

## 本地运行

```bash
# 1) 放置 FMP API key（二选一）
#    a. 环境变量:  set FMP_API_KEY=xxxx        (Windows)  /  export FMP_API_KEY=xxxx
#    b. 或建文件:  rotation/.fmp_api_key       内容为纯 key（已被 .gitignore 忽略）

# 2) 装依赖
pip install -r requirements.txt

# 3) 启动
python -m streamlit run app.py
```

首次打开会提示「生成数据（约 9 分钟）」，点一下即可；之后每天由 Windows 计划任务 08:07 自动刷新，
也可点页面右上「立即刷新」。

## Streamlit Community Cloud 部署（可分享公网 URL）

1. 把 `rotation/` 目录推到一个 **GitHub 仓库**（`.fmp_api_key`、`data_cache/` 已被忽略，key 不会进仓库）。
2. 打开 <https://share.streamlit.io> → New app → 选该仓库、主文件 `app.py`。
3. 在 **App settings → Secrets** 粘贴：
   ```toml
   FMP_API_KEY = "你的FMP_key"
   ```
4. Deploy。首屏用仓库里已提交的 `output/*.json` / `final_results.pkl` 立即渲染；点「立即刷新」会在云端重新取数重算。

> 注：Streamlit Cloud 容器文件系统是临时的——云端刷新只在本次运行内有效，重启后回到仓库里提交的数据。
> 若要云端也**每日自动更新**，用 GitHub Actions 定时跑 `refresh_dashboard.py` 并回提交 `output/`，或改用带持久化的托管。

## 主要文件

| 文件 | 作用 |
|---|---|
| `app.py` | Streamlit 入口（内嵌交互看板 + 回测表 + 刷新按钮） |
| `refresh_dashboard.py` | 一键全量刷新（取数→快照→回测→生成看板） |
| `final_pipeline.py` | 象限回测流程（参数扫描 / 各象限最优周期 / 相邻合并 / 持仓变化） |
| `rrg_model.py` | JdK RS-Ratio/Momentum 计算 |
| `fmp_data.py` | FMP 数据层（key 从 env 或 .fmp_api_key 读取） |
| `build_dashboard.py` | 生成自包含交互看板 HTML |

仅供研究，非投资建议。
