$ErrorActionPreference = 'SilentlyContinue'

# Stop uvicorn processes that are serving twilio_app
Get-CimInstance Win32_Process | Where-Object {
  $_.Name -match 'python\.exe' -and $_.CommandLine -match 'uvicorn' -and $_.CommandLine -match 'twilio_app:app'
} | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force
  "Stopped uvicorn PID=$($_.ProcessId)"
}

# Stop ngrok
Get-Process ngrok -ErrorAction SilentlyContinue | ForEach-Object {
  Stop-Process -Id $_.Id -Force
  "Stopped ngrok PID=$($_.Id)"
}
