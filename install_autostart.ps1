# Registers the Trading Agent server to auto-start at Windows login, runs it
# hidden (pythonw, no console, no browser), and starts it now.
# Run via install_autostart.bat. No admin needed (per-user).

$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runName = "OmniTradingAgentServer"
$serve = Join-Path $dir "serve.py"

if (-not (Test-Path $serve)) {
  Write-Host "ERROR: serve.py not found in $dir. Run from your agent folder." -ForegroundColor Red
  exit 1
}

# Prefer pythonw.exe (no console window). Fall back to python.exe.
$pyw = $null
$cmd = Get-Command pythonw -ErrorAction SilentlyContinue
if ($cmd) { $pyw = $cmd.Source }
if (-not $pyw) {
  $pc = Get-Command python -ErrorAction SilentlyContinue
  if ($pc) {
    $cand = Join-Path (Split-Path $pc.Source) "pythonw.exe"
    if (Test-Path $cand) { $pyw = $cand } else { $pyw = $pc.Source }
  }
}
if (-not $pyw) {
  Write-Host "ERROR: Python not found on PATH. Install Python first." -ForegroundColor Red
  exit 1
}
Write-Host "Using: $pyw"

# Command Windows runs at every login.
$runCmd = "`"$pyw`" `"$serve`" --no-browser"

# Register under the per-user Run key.
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
New-Item -Path $runKey -Force | Out-Null
Set-ItemProperty -Path $runKey -Name $runName -Value $runCmd
Write-Host "Registered auto-start: $runName"

# Start it now (hidden), unless already running.
$alreadyUp = $false
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:8765/api/price?symbol=BTC/USDT" -TimeoutSec 2 -UseBasicParsing
  if ($r.StatusCode -eq 200) { $alreadyUp = $true }
} catch { }

if ($alreadyUp) {
  Write-Host "Server is already running." -ForegroundColor Green
} else {
  Start-Process -FilePath $pyw -ArgumentList "`"$serve`"","--no-browser" `
                -WorkingDirectory $dir -WindowStyle Hidden
  Start-Sleep -Seconds 4
  Write-Host "Server started in the background." -ForegroundColor Green
}

Write-Host ""
Write-Host "DONE. The agent server will now start automatically every time you" -ForegroundColor Green
Write-Host "log in to Windows. Open it any time at http://127.0.0.1:8765" -ForegroundColor Green
Write-Host "To turn this off later, run uninstall_autostart.bat." -ForegroundColor Yellow
