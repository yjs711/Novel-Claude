@echo off
title Novel-Claude 写作工作室
echo ========================================
echo   Novel-Claude 写作工作室 启动中...
echo ========================================
echo.

REM 1. Check if llama-router is already running
echo [1/3] 检查模型服务...
curl -s http://localhost:61183/v1/models >nul 2>&1
if %errorlevel% neq 0 (
    echo   模型服务未启动，正在启动...
    start "llama-router" /MIN powershell -ExecutionPolicy Bypass -File "%USERPROFILE%\start-llama-router.ps1"
    echo   等待模型加载 (30秒)...
    timeout /t 30 /nobreak >nul
) else (
    echo   模型服务已在线
)

REM 2. Start WebUI
echo [2/3] 启动 WebUI...
cd /d "%~dp0"
start "Novel-Claude-WebUI" /MIN uv run uvicorn webui.app:app --host 0.0.0.0 --port 8080

REM 3. Open browser
echo [3/3] 打开浏览器...
timeout /t 3 /nobreak >nul
start http://localhost:8080

echo.
echo ========================================
echo   写作工作室已启动!
echo   浏览器: http://localhost:8080
echo   关闭此窗口不会停止服务
echo ========================================
pause
