#!/usr/bin/env python3
"""
Omniscient Trading Agent — local web interface.

A zero-dependency web UI (uses only Python's standard library). Launch it and
your browser opens a clickable dashboard: type a symbol, click a button, read
the analysis. No command line needed after launch.

Run:
    python serve.py
    # then open http://127.0.0.1:8765 (opens automatically)
"""

from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading import TradingAgent

HOST = "127.0.0.1"
PORT = 8765

# One shared agent (lazy LLM, so this is cheap until you click "Ask AI").
_agent_lock = threading.Lock()
_agent = None


def get_agent(equity=10_000.0, risk=1.0):
    global _agent
    with _agent_lock:
        if _agent is None:
            _agent = TradingAgent(account_equity=equity, risk_pct=risk)
        return _agent


def build_signal(symbol, timeframe, equity, risk):
    """Compute a full structured trade signal (entry/SL/TP + context) in one
    market-data fetch. Returns a JSON-serializable dict for the extension."""
    from trading.strategies import run_all, ensemble
    from trading.patterns import analyze_patterns
    from trading.regime import detect_regime
    from trading.forecast import Forecaster
    from trading.risk import build_trade_plan, position_size
    from trading import indicators as ind

    agent = get_agent(equity, risk)
    symbol = (symbol or "").strip()
    sig = {"symbol": symbol, "timeframe": timeframe, "ok": False}
    if not symbol:
        sig["error"] = "no symbol"
        return sig
    try:
        data = agent.engine.md.get_ohlcv(symbol, timeframe)
        bars = data.as_bars()
        price = float(data.close[-1])
        net = ensemble(run_all(bars))
        direction = net.direction.value          # long | short | flat
        conviction = round(float(net.strength), 3)
        ins = analyze_patterns(symbol, bars)
        reg = detect_regime(symbol, bars)
        fc = Forecaster().forecast(symbol, bars, horizon=5)
        atr = ind.last(ind.atr(bars["high"], bars["low"], bars["close"], 14)) or 0.0

        reasons = []
        reasons += ins.highlights[:2]
        reasons += [p.name for p in ins.patterns[:2]]
        if reg.notes:
            reasons.append(reg.notes[0])

        has_trade = direction in ("long", "short") and atr > 0
        entry = stop = take_profit = rr = size = None
        if has_trade:
            plan = build_trade_plan(symbol, direction, entry=price,
                                    atr_value=atr, rr=2.0)
            entry = round(plan.entry, 6)
            stop = round(plan.stop, 6)
            take_profit = round(plan.take_profit, 6)
            rr = round(getattr(plan, "risk_reward", 2.0), 2)
            sf = reg.size_factor if reg.size_factor > 0 else 1.0
            size = round(position_size(equity, risk, plan.entry, plan.stop) * sf, 6)

        sig.update({
            "ok": True,
            "price": round(price, 6),
            "direction": direction,
            "has_trade": has_trade,
            "conviction": conviction,
            "entry": entry, "stop": stop, "take_profit": take_profit,
            "rr": rr, "size": size,
            "regime": reg.regime.value,
            "size_factor": reg.size_factor,
            "atr_pct": reg.atr_pct,
            "prob_up": round(float(fc.prob_up), 3),
            "confidence": round(float(fc.confidence), 3),
            "reasons": reasons,
            "rationale": net.rationale,
        })
    except Exception as e:  # noqa: BLE001
        sig["error"] = str(e)
    return sig


def quick_price(symbol, timeframe):
    """Cheap last-price lookup for price alerts."""
    agent = get_agent()
    try:
        data = agent.engine.md.get_ohlcv((symbol or "").strip(), timeframe or "1d")
        return {"symbol": symbol, "price": round(float(data.close[-1]), 6), "ok": True}
    except Exception as e:  # noqa: BLE001
        return {"symbol": symbol, "ok": False, "error": str(e)}


def run_action(action, symbol, timeframe, question, strategy, equity, risk):
    """Dispatch a UI action to the agent and return plain text."""
    agent = get_agent(equity, risk)
    symbol = (symbol or "").strip()
    if not symbol and action not in ("knowledge",):
        return "Please enter a symbol (e.g. BTC/USDT, AAPL, EURUSD)."
    try:
        if action == "analyze":
            return agent.analyze(symbol, timeframe=timeframe).to_text()
        if action == "regime":
            return agent.regime(symbol, timeframe=timeframe).to_text()
        if action == "mtf":
            return agent.mtf(symbol).to_text()
        if action == "insights":
            return agent.insights(symbol, timeframe=timeframe).to_text()
        if action == "backtest":
            return agent.backtest(symbol, strategy=strategy or "ensemble",
                                  timeframe=timeframe).summary()
        if action == "plan":
            plan = agent.trade_plan(symbol, timeframe=timeframe)
            if plan is None:
                return "No actionable trade plan right now (signal is flat). " \
                       "That's a valid answer — patience beats forcing a trade."
            return plan.to_text() if hasattr(plan, "to_text") else str(plan)
        if action == "ask":
            return agent.ask(symbol, question=question or None, timeframe=timeframe)
        if action == "knowledge":
            q = (question or symbol or "trading edge risk").strip()
            return agent.learn(q)
        return f"Unknown action: {action}"
    except Exception as e:  # noqa: BLE001
        return f"Error running '{action}' for {symbol}:\n{e}\n\n" \
               "Tip: some symbols need a specific format — try BTC/USDT, AAPL, or EURUSD."


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Omniscient Trading Agent</title>
<style>
  :root { --bg:#0d1117; --panel:#161b22; --border:#30363d; --text:#e6edf3;
          --accent:#2ea043; --accent2:#1f6feb; --muted:#8b949e; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: 'Segoe UI', system-ui, sans-serif;
         background:var(--bg); color:var(--text); }
  header { padding:18px 24px; border-bottom:1px solid var(--border);
           display:flex; align-items:center; gap:12px; background:var(--panel); }
  header h1 { font-size:18px; margin:0; font-weight:600; }
  header .tag { color:var(--muted); font-size:13px; }
  .wrap { max-width:1000px; margin:0 auto; padding:24px; }
  .controls { display:grid; grid-template-columns: 1fr 130px 110px 100px;
              gap:10px; margin-bottom:14px; }
  @media (max-width:720px){ .controls{ grid-template-columns:1fr 1fr; } }
  label { font-size:12px; color:var(--muted); display:block; margin-bottom:4px; }
  input, select { width:100%; padding:10px; border-radius:8px;
                  border:1px solid var(--border); background:#0d1117;
                  color:var(--text); font-size:15px; }
  input:focus, select:focus { outline:none; border-color:var(--accent2); }
  .qrow { margin-bottom:14px; }
  .buttons { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:18px; }
  button { padding:10px 16px; border:none; border-radius:8px; cursor:pointer;
           font-size:14px; font-weight:600; background:var(--accent2);
           color:white; transition:filter .15s; }
  button:hover { filter:brightness(1.15); }
  button.alt { background:var(--accent); }
  button.ghost { background:#21262d; color:var(--text); border:1px solid var(--border); }
  #out { background:var(--panel); border:1px solid var(--border); border-radius:10px;
         padding:18px; white-space:pre-wrap; font-family:'Cascadia Code',Consolas,monospace;
         font-size:13.5px; line-height:1.55; min-height:240px; overflow-x:auto; }
  .spin { color:var(--accent2); }
  .hint { color:var(--muted); font-size:12px; margin-top:10px; }
</style>
</head>
<body>
<header>
  <span style="font-size:22px">📈</span>
  <h1>Omniscient Trading Agent</h1>
  <span class="tag">multi-asset · honest probabilities, not promises</span>
</header>
<div class="wrap">
  <div class="controls">
    <div>
      <label>Symbol</label>
      <input id="symbol" value="BTC/USDT" placeholder="BTC/USDT, AAPL, EURUSD"
             onkeydown="if(event.key==='Enter')go('analyze')">
    </div>
    <div>
      <label>Timeframe</label>
      <select id="timeframe">
        <option>1d</option><option>1w</option><option>4h</option>
        <option>1h</option><option>15m</option><option>5m</option>
      </select>
    </div>
    <div>
      <label>Equity ($)</label>
      <input id="equity" value="10000">
    </div>
    <div>
      <label>Risk (%)</label>
      <input id="risk" value="1">
    </div>
  </div>

  <div class="qrow">
    <label>Question / strategy (optional — used by "Ask AI", "Backtest", "Knowledge")</label>
    <input id="question" placeholder="e.g. is this a good long? &nbsp; or strategy: ensemble">
  </div>

  <div class="buttons">
    <button class="alt" onclick="go('analyze')">Analyze</button>
    <button onclick="go('ask')">Ask AI 🤖</button>
    <button onclick="go('regime')">Regime</button>
    <button onclick="go('mtf')">Multi-Timeframe</button>
    <button onclick="go('insights')">Co-Pilot Insights</button>
    <button onclick="go('plan')">Trade Plan</button>
    <button onclick="go('backtest')">Backtest</button>
    <button class="ghost" onclick="go('knowledge')">Knowledge Search</button>
  </div>

  <div id="out">Enter a symbol above and click a button.

• Analyze — full computed read (no AI needed)
• Ask AI — narrated answer (needs Ollama running)
• Regime — trending / ranging / high-volatility + recommended size
• Multi-Timeframe — alignment across 1w / 1d / 4h / 1h
• Co-Pilot Insights — patterns, key levels, candlestick signals
• Trade Plan — entry, stop-loss, take-profit, position size
• Backtest — test a strategy on historical bars
• Knowledge Search — query the 52-lesson quant corpus</div>
  <div class="hint">Runs locally on your PC. Nothing is sent anywhere except market-data lookups.</div>
</div>

<script>
function go(action){
  const out = document.getElementById('out');
  out.innerHTML = '<span class="spin">Working… (first AI call can take a moment)</span>';
  const p = new URLSearchParams({
    action,
    symbol: document.getElementById('symbol').value,
    timeframe: document.getElementById('timeframe').value,
    question: document.getElementById('question').value,
    strategy: document.getElementById('question').value.replace(/^strategy:\\s*/i,''),
    equity: document.getElementById('equity').value || '10000',
    risk: document.getElementById('risk').value || '1',
  });
  fetch('/api/run?' + p.toString())
    .then(r => r.json())
    .then(d => { out.textContent = d.text; })
    .catch(e => { out.textContent = 'Connection error: ' + e; });
}
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # quiet

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        # CORS preflight for the Chrome extension / external callers.
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send(200, PAGE)
            return
        if parsed.path == "/api/run":
            q = parse_qs(parsed.query)
            g = lambda k, d="": (q.get(k, [d])[0])
            try:
                equity = float(g("equity", "10000") or 10000)
                risk = float(g("risk", "1") or 1)
            except ValueError:
                equity, risk = 10000.0, 1.0
            text = run_action(
                action=g("action", "analyze"),
                symbol=g("symbol"),
                timeframe=g("timeframe", "1d"),
                question=g("question"),
                strategy=g("strategy"),
                equity=equity,
                risk=risk,
            )
            self._send(200, json.dumps({"text": text}),
                       ctype="application/json; charset=utf-8")
            return
        if parsed.path == "/api/signal":
            q = parse_qs(parsed.query)
            g = lambda k, d="": (q.get(k, [d])[0])
            try:
                equity = float(g("equity", "10000") or 10000)
                risk = float(g("risk", "1") or 1)
            except ValueError:
                equity, risk = 10000.0, 1.0
            sig = build_signal(g("symbol"), g("timeframe", "1d"), equity, risk)
            self._send(200, json.dumps(sig),
                       ctype="application/json; charset=utf-8")
            return
        if parsed.path == "/api/price":
            q = parse_qs(parsed.query)
            g = lambda k, d="": (q.get(k, [d])[0])
            self._send(200, json.dumps(quick_price(g("symbol"), g("timeframe", "1d"))),
                       ctype="application/json; charset=utf-8")
            return
        self._send(404, "Not found")


def main():
    url = f"http://{HOST}:{PORT}"
    print("=" * 60)
    print("  📈  OMNISCIENT TRADING AGENT — web interface")
    print("=" * 60)
    print(f"  Open in your browser:  {url}")
    print("  (it should open automatically)")
    print("  Press Ctrl+C in this window to stop.")
    print("=" * 60)
    try:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    except Exception:
        pass
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. You can close this window.")
        server.shutdown()


if __name__ == "__main__":
    main()
