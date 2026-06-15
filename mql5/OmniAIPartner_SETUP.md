# OmniAIPartner — your interactive AI trading partner in MT5

`OmniAIPartner.mq5` is the full partner. It works *with* you:

- **Watches your back (proactive signals).** Every bar it scans the market and,
  when a high-conviction setup forms, pushes you a ready-made idea — direction,
  entry, stop-loss, take-profit, R:R, suggested lot size and the reasons — without
  you asking.
- **Does what you forget.** Auto-attaches SL/TP to ANY position missing them,
  including trades you place by hand.
- **Manages exits.** Moves to breakeven, then trails with ATR.
- **Scans for the patterns you name** (engulfing, hammer, star, doji, squeeze,
  breakout, RSI divergence) and alerts you — popup, sound, and phone push.
- **Draws the key lines** on your chart: prior-day high/low, support/resistance,
  daily pivots (P/R1/S1), nearest round number.
- **Tells you which strategy fits this symbol** — click "Best Strategy" and it
  ranks 6 approaches on recent history and names the best fit.
- **Trades the session open** automatically when you're away (optional).
- **Answers your questions.** Type in the chat box, click "Ask AI", and it relays
  to the Python AI brain (Ollama) and shows the answer on the chart.
- **Guardian dashboard.** Live equity, day P/L, drawdown, open risk, trade count,
  with a daily-loss circuit breaker and total-drawdown kill switch.

> ⚠️ TEST ON A DEMO ACCOUNT FIRST. Signals are probabilities, not promises.

---

## Part 1 — Install the EA (required)

1. MT5 menu: **File → Open Data Folder → MQL5 → Experts**.
2. Copy `OmniAIPartner.mq5` into that folder.
3. Open **MetaEditor** (F4), open the file, press **Compile** (F7) — 0 errors.
4. In MT5, drag **OmniAIPartner** from Navigator onto a chart.
5. On the **Common** tab tick **Allow Algo Trading**, click OK.
6. Make sure the toolbar **Algo Trading** button is green.

Everything except the "Ask AI" chat works immediately after this. The proactive
signals, auto-protect, pattern alerts, chart lines, dashboard and Best-Strategy
button need NO Python and NO internet beyond your broker feed.

## Part 2 — Connect the AI brain (only for the "Ask AI" chat)

The chat box needs the Python agent running as a local server.

1. On the same PC, start the Python brain (from the TradingAgent folder):
   - double-click **Start Trading Agent.bat**, OR run `python serve.py`.
   - Leave it running. (For AI answers, also have **Ollama** running.)
2. Whitelist the local URL in MT5 so the EA may call it:
   - **Tools → Options → Expert Advisors**
   - tick **Allow WebRequest for listed URL**
   - add:  `http://127.0.0.1:8765`
   - click OK.
3. Now type a question in the chat box on the chart and click **Ask AI**.

If you see "WebRequest blocked", you missed step 2. If you see "Could not reach
the AI brain", the Python server isn't running (step 1).

---

## Key inputs (grouped in the EA settings)

- **Proactive Signal Watch** — `InpProactiveSignals` on/off, `InpSignalMinConv`
  is how strong a setup must be before it pings you (0.45 = fairly selective).
- **Auto-Protect** — `InpProtectManual` also guards trades you place by hand.
- **Trade Management** — breakeven + ATR trailing toggles and distances.
- **Pattern Scanner** — `InpWatchPatterns` is the list to watch; alert methods.
- **Chart Drawing** — toggle prior-day, support/resistance, pivots, round numbers.
- **Strategy Advisor** — runs on load and on the "Best Strategy" button.
- **Session Timing** — auto-trade the open at `InpSessionHour:InpSessionMinute`.
- **Risk Guardian** — risk %, daily-loss %, drawdown kill switch, max positions,
  max trades/day, spread guard.

## What stays in Python (not in MT5)

The 52-lesson knowledge corpus, walk-forward optimizer, news ingestion and the
web dashboard live in the Python agent. The natural split: **Python for deep
research, this EA for live eyes + hands on the chart.**
