@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ========================================
echo   Novel-Claude 写作工作室
echo ========================================
echo.

echo [1/2] 启动 WebUI 服务...
start "NovelClaude-WebUI" /B uv run uvicorn webui.app:app --host 127.0.0.1 --port 8080

echo [2/2] 等待服务就绪...
timeout /t 3 /nobreak >nul

echo 打开浏览器...
start http://127.0.0.1:8080

echo.
echo 写作工作室已启动!
echo 地址: http://127.0.0.1:8080
echo 关闭此窗口不会停止服务 (需要停止时关闭命令行窗口)
echo.
pause
