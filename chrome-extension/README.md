# Omniscient Trading Agent — Chrome Extension (v2)

A full trading co-pilot in your browser. The extension is the face; your local
Python agent (`serve.py`) is the brain. Everything runs on your own machine.

```
popup / side panel / background  ──HTTP──►  serve.py (127.0.0.1:8765)  ──►  TradingAgent (+ Ollama)
```

## Features

**Signals tab** — live cards for every watchlist symbol with direction,
conviction, **entry / SL / TP / RR**, suggested size, regime and the top reason.

**Analyze tab** — one-click ★ Signal, Ask AI, Analyze, Regime, Multi-Timeframe,
Co-Pilot, Trade Plan, Backtest, Knowledge search for any symbol.

**Watchlist tab** — manage your basket of symbols and set **price alerts**
(above/below) that fire desktop notifications.

**Journal tab** — every auto-signal is logged locally; review history and
**export to CSV**.

**Settings** — server URL, equity, risk, background-watch interval, minimum
conviction, sound, and a light/dark **theme** toggle.

**Background watcher** — scans your watchlist on a schedule and pushes **full
signal notifications** (entry/SL/TP/RR + reason) with **Analyze / Snooze 1h**
buttons. A toolbar **badge** shows how many live setups exist right now.

**Live side panel** — a persistent, auto-refreshing signal board. Open it with
**Ctrl+Shift+T** (or from a notification's Analyze button).

**Right-click anywhere** — select a ticker on any web page, right-click →
*Analyze "…" with Trading Agent* for an instant signal notification.

## Setup

### 1. Start the agent server
From your TradingAgent folder: double-click **Start Trading Agent.bat**
(or run `python serve.py`). Leave it running. For "Ask AI", also run **Ollama**.

### 2. Load the extension
1. Chrome → `chrome://extensions`
2. Turn on **Developer mode** (top-right)
3. **Load unpacked** → pick this `chrome-extension` folder
4. Pin the 📈 icon.

### 3. Turn on the watcher (optional)
Popup → ⚙ Settings → tick **Background watch** → set interval & min conviction →
**Save**. Add symbols in the **Watchlist** tab.

## Notes / honesty

- Needs `serve.py` running; the extension places no orders and does not trade.
- Signals are probabilities, not guarantees. Research tool — trade your own plan.
- All requests go only to your local agent; nothing is sent to third parties.
- Publishing to the Chrome Web Store is a separate, reviewed process — this is the
  standard "Load unpacked" developer install.
