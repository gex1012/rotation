@echo off
REM ===== 双击启动 RRG 看板 (Streamlit) =====
REM 服务跑在这个窗口里，别关这个黑窗口；关了服务就停。
REM 浏览器会自动打开 http://localhost:8501
title RRG Dashboard - 关闭此窗口即停止服务
set PYTHONIOENCODING=utf-8
cd /d F:\heatmap\rotation
echo 正在启动看板... 稍等几秒浏览器会自动打开 http://localhost:8501
python -m streamlit run app.py --server.port 8501
pause
