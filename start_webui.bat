@echo off
cd /d C:\Users\abee\ai-novel-frameworks\Novel-Claude
start "" uv run uvicorn webui.app:app --host 127.0.0.1 --port 8080
start http://127.0.0.1:8080
