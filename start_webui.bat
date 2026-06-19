@echo off
cd /d C:\Users\abee\ai-novel-frameworks\Novel-Claude
set PATH=C:\Users\abee\AppData\Local\Programs\Python\Python312\Scripts;%PATH%
start "Server" uv run uvicorn webui.app:app --host 127.0.0.1 --port 8080
timeout /t 3 /nobreak >nul
start http://127.0.0.1:8080
