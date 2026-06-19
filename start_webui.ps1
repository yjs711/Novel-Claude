# Novel-Claude WebUI Launcher
$uv = "C:\Users\abee\AppData\Local\Programs\Python\Python312\Scripts\uv.exe"
$proj = "C:\Users\abee\ai-novel-frameworks\Novel-Claude"
Set-Location $proj

# Start server minimized
Start-Process -FilePath $uv -ArgumentList "run","uvicorn","webui.app:app","--host","127.0.0.1","--port","8080" -WindowStyle Minimized

# Wait for server to be ready
Start-Sleep -Seconds 3

# Open browser
Start-Process "http://127.0.0.1:8080"
