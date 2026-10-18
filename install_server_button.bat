@echo off
REM ============================================================
REM  Installs the "Start server" button helper for the Chrome
REM  extension (Chrome Native Messaging host). Run this ONCE.
REM  Double-click it from your agent folder (next to serve.py).
REM ============================================================
setlocal
set "DIR=%~dp0"
if "%DIR:~-1%"=="\" set "DIR=%DIR:~0,-1%"
echo Installing the Start-server helper from:
echo   %DIR%
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%DIR%\install_server_button.ps1"
echo.
pause
