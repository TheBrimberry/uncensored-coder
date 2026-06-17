# Omniscient Trading Agent — Chrome Extension

A browser-toolbar front-end for the trading agent. Click the toolbar icon to get
a popup with Analyze, Ask AI, Regime, Multi-Timeframe, Co-Pilot, Trade Plan,
Backtest and Knowledge search — plus optional **background desktop alerts** that
watch a symbol for you while you browse.

## How it works

The extension is the **face**; the Python agent is the **brain**. The popup sends
your requests to the local agent server (`serve.py`) running on your own PC, so
your analysis stays on your machine. Ollama (optional) powers the "Ask AI" button.

```
Chrome extension  ──HTTP──►  python serve.py (127.0.0.1:8765)  ──►  TradingAgent
```

## Setup (one time)

### 1. Start the agent server
From your TradingAgent folder, either:
- double-click **Start Trading Agent.bat**, or
- run `python serve.py`

Leave it running. (For "Ask AI" answers, also have **Ollama** running.)

### 2. Load the extension in Chrome
1. Open Chrome and go to:  `chrome://extensions`
2. Turn on **Developer mode** (top-right toggle).
3. Click **Load unpacked**.
4. Select this `chrome-extension` folder.
5. The 📈 icon appears in your toolbar. Pin it if you like.

### 3. Use it
- Click the toolbar icon, type a symbol, click a button.
- The status line at the bottom shows "agent connected" when it can reach the
  server. If it says "agent offline", start `serve.py` (step 1).

## Background signal watch (optional)

In the popup, click the ⚙ gear:
- tick **Background signal watch**
- set the symbol and interval
- **Save settings**

Chrome will then check that symbol on a schedule and pop a desktop notification
when the market is in an actionable regime (strong trend / high volatility) —
even when the popup is closed. The browser must be running for alerts to fire.

## Settings

- **Agent server URL** — default `http://127.0.0.1:8765`. Change only if you run
  the server on another port/host.
- **Equity / Risk** — used for position sizing in Trade Plan and signals.

## Notes / honesty

- This is a convenience front-end. It needs the Python agent running locally; the
  extension does not trade by itself and places no orders.
- Signals are probabilities, not guarantees. Use for research; trade your own plan.
- Nothing is uploaded to any third party — requests go only to your local agent.
