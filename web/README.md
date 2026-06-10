# CoinScope — Crypto Analytics & Screener

A single-page crypto analytics platform inspired by [altFINS](https://altfins.com).
No build step, no framework — just open it or serve the folder.

## Features

- **Live crypto screener** — top coins with price, 1h/24h/7d change, RSI(14),
  momentum signal, detected chart pattern, market cap and an inline 7-day sparkline.
  Sortable columns and filters (search, signal, market cap, trend).
- **Real technical analysis** — RSI, SMA/EMA and a composite Buy/Sell signal are
  computed client-side in `assets/indicators.js` from each coin's 7-day price series.
- **AI chart patterns** — heuristic pattern detection (bull flag, ascending triangle,
  double bottom, breakout, …) with projected price targets.
- **Trade setups** — auto-generated entry / stop-loss / targets with risk-reward.
- **AI Copilot** — type a strategy in plain English ("oversold large caps in an
  uptrend") and it parses the intent into screener filters.
- **Live data** via the free [CoinGecko API](https://www.coingecko.com/en/api),
  with an offline fallback dataset so the page always works.

## Run it

```bash
cd web
python3 -m http.server 8000
# open http://localhost:8000
```

Or just open `web/index.html` directly in a browser.

## Structure

```
web/
├── index.html              # markup + sections
└── assets/
    ├── styles.css          # dark theme
    ├── indicators.js       # RSI / SMA / EMA / signal / pattern detection
    ├── data-fallback.js    # offline demo dataset
    └── app.js              # data fetching, rendering, filters, Copilot
```

## Notes

Demo / educational project. Not affiliated with altFINS. Market data is provided
by CoinGecko. Nothing here is financial advice.
