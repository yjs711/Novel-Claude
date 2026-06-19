# Novel-Claude All-in-One Launcher
$ErrorActionPreference = 'Stop'
$routerPort = 61183
$webuiPort = 8765
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $proj) { $proj = Get-Location }

Write-Host '=== Novel-Claude Launcher ==='

Write-Host '[1/3] Checking model router...'
$routerOk = $false
try {
    $models = Invoke-RestMethod -Uri "http://127.0.0.1:$routerPort/v1/models" -TimeoutSec 5
    Write-Host "  Router online: $($models.data.Count) models"
    $routerOk = $true
} catch {
    Write-Host '  Starting router...'
    $routerScript = "$env:USERPROFILE\start-llama-router.ps1"
    Start-Process -FilePath powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$routerScript`"" -WindowStyle Minimized
    for ($i = 0; $i -lt 45; $i++) {
        Start-Sleep -Seconds 2
        try {
            $models = Invoke-RestMethod -Uri "http://127.0.0.1:$routerPort/v1/models" -TimeoutSec 3
            Write-Host "  Router ready: $($models.data.Count) models ($($i*2)s)"
            $routerOk = $true
            break
        } catch { }
    }
}
if (-not $routerOk) { Write-Host '  ERROR: Router not reachable'; exit 1 }

Write-Host '[2/3] Starting WebUI...'
$python = Join-Path $proj '.venv\Scripts\python.exe'
Start-Process -FilePath $python -ArgumentList '-m','uvicorn','webui.app:app','--host','127.0.0.1','--port',$webuiPort -WorkingDirectory $proj -WindowStyle Minimized
for ($i = 0; $i -lt 8; $i++) {
    Start-Sleep -Seconds 1
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:$webuiPort/api/status" -TimeoutSec 3
        Write-Host "  WebUI ready ($($i+1)s)"
        break
    } catch { }
}

Write-Host '[3/3] Opening browser...'
Start-Process 'http://127.0.0.1:8765'
Write-Host '=== Done ==='
