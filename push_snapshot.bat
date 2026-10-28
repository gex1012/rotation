@echo off
REM Commit + push the freshly rebuilt snapshot so Streamlit Cloud follows the local data.
cd /d F:\heatmap\rotation
git add output/dashboard.html output/final_results.pkl output/industry_rrg.json output/tech_rrg.json
git diff --cached --quiet && exit /b 0
git commit -m "auto: daily data snapshot" >> output\refresh.log 2>&1
git push origin main >> output\refresh.log 2>&1
