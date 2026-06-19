# Novel-Claude All-in-One Launcher
$routerPort = 61183
$webuiPort = 8080

Write-Host "=== Novel-Claude Launcher ==="

# --- 1. llama-router ---
Write-Host "[1/3] Checking model router..."
$routerOk = $false
try {
    $null = Invoke-RestMethod -Uri "http://127.0.0.1:$routerPort/v1/models" -TimeoutSec 3
    Write-Host "  Router already online"
    $routerOk = $true
} catch {
    Write-Host "  Starting router..."
    Start-Process -FilePath "powershell" -ArgumentList "-ExecutionPolicy Bypass -File `"$env:USERPROFILE\start-llama-router.ps1`"" -WindowStyle Minimized
    for ($i = 0; $i -lt 90; $i++) {
        Start-Sleep -Seconds 2
        try {
            $models = Invoke-RestMethod -Uri "http://127.0.0.1:$routerPort/v1/models" -TimeoutSec 3
            Write-Host "  Router ready: $($models.data.Count) models (${i}s)"
            $routerOk = $true
            break
        } catch {}
    }
}
if (-not $routerOk) { Write-Host "  ERROR: Router failed to start"; exit 1 }

# --- 2. WebUI ---
Write-Host "[2/3] Starting WebUI..."
$uv = "$env:USERPROFILE\AppData\Local\Programs\Python\Python312\Scripts\uv.exe"
$proj = "$env:USERPROFILE\ai-novel-frameworks\Novel-Claude"
Get-Process -Name "uv" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

Start-Process -FilePath $uv -ArgumentList "run","uvicorn","webui.app:app","--host","127.0.0.1","--port","$webuiPort" -WorkingDirectory $proj -WindowStyle Minimized

for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:$webuiPort/api/status" -TimeoutSec 3
        Write-Host "  WebUI ready (${i}s)"
        break
    } catch {}
}

# --- 3. Browser ---
Write-Host "[3/3] Opening browser..."
Start-Process "http://127.0.0.1:8080"
Write-Host "=== Done ==="
