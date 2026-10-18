@echo off
REM ============================================================
REM   Omniscient Trading Agent — double-click launcher (Windows)
REM   Just double-click this file. Your browser will open.
REM ============================================================
cd /d "%~dp0"
echo Starting the Trading Agent web interface...
echo A browser window will open at http://127.0.0.1:8765
echo.
echo Keep this window open while you use the agent.
echo Close it (or press Ctrl+C) when you are done.
echo.
python serve.py
echo.
echo The agent has stopped. Press any key to close this window.
pause >nul
