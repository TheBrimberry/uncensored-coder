# Omniscient Trading Agent — MetaTrader 5 Expert Advisor

`OmniscientTradingAgent.mq5` is the **tradeable core** of the Python agent, ported
to MQL5 so it runs directly inside MetaTrader 5. It bundles a 7-signal ensemble,
a regime filter, ATR-based stops/targets, risk-based position sizing, and the
account guardian (daily-loss circuit breaker + total-drawdown kill switch).

> ⚠️ Trading involves risk of loss. Test on a **DEMO** account first. This EA is
> a disciplined rules engine, not a profit guarantee.

## How to install

1. Open **MetaTrader 5**.
2. Menu: **File → Open Data Folder**.
3. Go into **MQL5 → Experts**.
4. Copy `OmniscientTradingAgent.mq5` into that `Experts` folder.
5. Back in MT5, open **MetaEditor** (the toolbar icon, or press F4).
6. In MetaEditor's Navigator, find the file under **Experts**, open it, and
   click **Compile** (F7). It should compile with 0 errors.
7. Back in MT5, the EA now appears in the **Navigator → Expert Advisors** list.

## How to run

1. Open a chart for the symbol/timeframe you want (e.g. EURUSD, H1).
2. Drag **OmniscientTradingAgent** from the Navigator onto the chart.
3. In the settings window, on the **Common** tab, tick **Allow Algo Trading**.
4. Set your inputs (see below), click **OK**.
5. Make sure the **Algo Trading** button in the MT5 toolbar is green/enabled.

## Test it first (Strategy Tester)

1. MT5 menu: **View → Strategy Tester** (Ctrl+R).
2. Choose **OmniscientTradingAgent**, pick a symbol, timeframe, and date range.
3. Run a backtest before ever putting it on a live or demo chart.

## Key inputs

| Input | Meaning | Default |
|---|---|---|
| `InpRiskPct` | % of equity risked per trade | 1.0 |
| `InpMaxDailyLossPct` | Daily loss that halts trading until next day | 5.0 |
| `InpMaxDrawdownPct` | Total drawdown that triggers the permanent kill switch | 20.0 |
| `InpMaxOpenPositions` | Max simultaneous positions from this EA | 1 |
| `InpAtrStopMult` | Stop-loss distance = ATR × this | 2.0 |
| `InpRewardRisk` | Take-profit = stop distance × this | 2.0 |
| `InpSignalThreshold` | Net ensemble bias needed to trade (0–1) | 0.20 |
| `InpUseRegimeFilter` | Reduce/skip size in dangerous regimes | true |

## What's inside the ensemble

Each bar, seven strategies vote and the EA acts only on the strength-weighted net:

1. EMA crossover (trend)
2. RSI mean-reversion
3. MACD momentum (histogram sign + slope)
4. Bollinger breakout
5. Stochastic cross from extremes
6. ADX trend-strength with +DI/−DI direction
7. Donchian (Turtle) breakout

The **regime filter** (ATR% + ADX) scales size down in high volatility and ranges,
up in strong trends. Every order ships with a **stop-loss and take-profit** — the
guardian never lets a naked position sit on your account.

## What it does NOT include

The Python project's LLM narration, 52-lesson knowledge corpus, news ingestion,
walk-forward optimizer and web dashboard stay in Python — MT5 can't host those.
Use the Python agent for research and this EA for execution.
