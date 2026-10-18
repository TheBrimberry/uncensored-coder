# 📈 Trading Agent — Example Outputs

All examples below run **fully offline** (synthetic-data fallback). Install
`yfinance` / `ccxt` for real market data; the output format is identical.

---

## 1. Computed analysis (no LLM)

```bash
python trade.py BTC/USDT --no-llm
```

```
=== ANALYSIS: BTC/USDT (1d) ===
Last price: 133.7189  | source: synthetic  [SYNTHETIC DATA — install ccxt/yfinance for real data]

Indicators:
  EMA20: 135.9774
  EMA50: 134.4677
  EMA200: 133.3175
  RSI14: 41.3763
  ATR14: 1.4645
  MACD_hist: -0.8577

Strategy signals:
  [ long] ma_crossover (0.17) — EMA50 above EMA200: uptrend.
  [ flat] rsi_reversion (0.00) — RSI 41.4 neutral.
  [ flat] bollinger_breakout (0.00) — price inside bands.
  [short] macd_momentum (1.00) — MACD hist negative & falling: bearish momentum.
  [ long] supertrend_follow (0.55) — Supertrend bullish.

Ensemble: SHORT (0.16) — Net bias -0.16.

Forecast: BTC/USDT 5-bar outlook: SIDEWAYS (P(up)=51%). Expected +0.02%
in [-2.43%, +2.47%]. Confidence 1%. Probabilistic estimate — not a guarantee.

Proposed plan: SHORT BTC/USDT @ 133.7189 | stop 136.6478 | target 127.8611
| size 34.14 units | risk 100.00 | R:R 2.00
```

---

## 2. Programmatic forecast

```python
from trading import TradingAgent
print(TradingAgent().forecast("AAPL", horizon=10).summary())
```

```
AAPL 10-bar outlook: UP (P(up)=63%). Expected +1.10% in [-3.20%, +5.40%].
Confidence 41%. Probabilistic estimate — not a guarantee.
```

---

## 3. Risk-managed trade plan

```python
from trading import TradingAgent
agent = TradingAgent(account_equity=25_000, risk_pct=0.5)
print(agent.trade_plan("EURUSD").summary())
```

```
LONG EURUSD @ 1.0850 | stop 1.0790 | target 1.0970 | size 2083.33 units
| risk 125.00 | R:R 2.00
```

---

## 4. Paper execution (safe by default)

```python
from trading import TradingAgent
agent = TradingAgent()
plan = agent.trade_plan("BTC/USDT")
print(agent.execute_plan(plan, broker="paper"))
# [PAPER] [PAPER] sell 34.14 BTC/USDT simulated. (broker=base)
```

Going live requires explicit opt-in **and** real credentials:

```python
agent.execute_plan(
    plan, broker="tradelocker", live=True,
    credentials={"username": "...", "password": "...", "server": "..."},
)
```

---

## 5. Knowledge base

```bash
python trade.py --knowledge crypto
```

Prints the curated catalogue of crypto-relevant open-source tools (ccxt,
freqtrade, jesse, hummingbot, nautilus_trader, ...), strategy families, and the
non-negotiable risk principles the agent always applies.
```
