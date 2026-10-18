@echo off
REM ============================================================
REM  Make the Trading Agent server AUTO-START at Windows login
REM  (silent background, no window, no browser popup).
REM  Double-click ONCE from your agent folder (next to serve.py).
REM ============================================================
setlocal
set "DIR=%~dp0"
if "%DIR:~-1%"=="\" set "DIR=%DIR:~0,-1%"
echo Setting up auto-start from:
echo   %DIR%
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%DIR%\install_autostart.ps1"
echo.
pause
