$python = "$PSScriptRoot\.venv\Scripts\python.exe"
Set-Location $PSScriptRoot
Start-Process -FilePath $python -ArgumentList "-m","uvicorn","webui.app:app","--host","127.0.0.1","--port","8765" -WindowStyle Minimized
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:8765"
