@echo off
REM Turn OFF auto-start of the Trading Agent server.
setlocal
set "DIR=%~dp0"
if "%DIR:~-1%"=="\" set "DIR=%DIR:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'OmniTradingAgentServer' -ErrorAction SilentlyContinue; Write-Host 'Auto-start removed. The server will no longer start at login.' -ForegroundColor Green"
echo.
echo (The server may still be running now. Reboot or end the pythonw task to stop it.)
echo.
pause
