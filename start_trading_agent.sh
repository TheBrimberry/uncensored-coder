#!/usr/bin/env bash
# Omniscient Trading Agent — launcher (macOS / Linux)
# Run:  ./start_trading_agent.sh
cd "$(dirname "$0")"
echo "Starting the Trading Agent web interface..."
echo "A browser window will open at http://127.0.0.1:8765"
echo "Press Ctrl+C to stop."
python3 serve.py
