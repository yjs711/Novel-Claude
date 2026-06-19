@echo off
cd /d C:\Users\abee\ai-novel-frameworks\Novel-Claude
start "Server" .venv\Scripts\python.exe -m uvicorn webui.app:app --host 127.0.0.1 --port 8765
timeout /t 3 /nobreak >nul
start http://127.0.0.1:8765
