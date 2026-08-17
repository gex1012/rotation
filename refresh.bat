@echo off
REM RRG dashboard auto-refresh wrapper (run by Windows Task Scheduler)
set PYTHONIOENCODING=utf-8
cd /d F:\heatmap\rotation
python refresh_dashboard.py >> output\refresh.log 2>&1
