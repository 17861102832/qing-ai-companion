@echo off
chcp 65001 >nul
title 小青 · AI数字人伴侣
cd /d "%~dp0"
echo ============================================
echo  小青 · AI数字人伴侣 (Open-LLM-VTuber)
echo ============================================
echo.
echo  [1] 若无 API Key，请先在 conf.yaml 里填
echo      deepseek_llm: llm_api_key 或在环境变量设 DEEPSEEK_API_KEY
echo.
echo  启动中... 请稍候
echo  启动后浏览器打开 http://localhost:12393
echo.
call ".venv\Scripts\python.exe" run_qing.py
pause
