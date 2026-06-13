# CoinScope — Crypto Analytics, Screener, Arbitrage & Predictions

A multi-page crypto analytics platform inspired by [altFINS](https://altfins.com),
[CoinArbitrageBot](https://coinarbitragebot.com) and [CoinCodex](https://coincodex.com).
No build step, no framework — open it or serve the folder.

## Pages

| Page | What it does |
|------|--------------|
| `index.html` | Home — hero, explore cards, market overview (Fear & Greed, trending, heatmap) |
| `pulse.html` | Market Pulse — gainers, losers, volume, bullish/bearish, RSI extremes |
| `screener.html` | Live screener over the **top 1,000 coins** + AI Copilot |
| `arbitrage.html` | Market-wide arbitrage opportunities board + live per-coin deep scan |
| `predictions.html` | Price predictions (5-day → 1-year) with technical sentiment |
| `converter.html` | Convert any coin to any coin / USD at live prices |
| `smart.html` | Smart Picks — undervalued / overvalued / most likely to explode |
| `picks.html` | Top Picks of the Day / Week / Month |
| `discover.html` | New listings, upcoming launches, airdrops |
| `news.html` | Crypto news feed |
| `portfolio.html` | Portfolio tracker (value, 24h, allocation) — stored in your browser |
| `coin.html` | Full coin page — chart, prediction, technicals, stats (`coin.html?id=bitcoin`) |
| `learn.html` | Articles & knowledge base |
| `pricing.html` | Plans |

## How it's built

- **`assets/layout.js`** injects shared chrome (nav, ticker, global stats bar, footer,
  coin drawer, toasts) into every page, so markup isn't duplicated.
- **`assets/app.js`** is loaded on every page and renders only the sections that exist
  on the current page (every renderer is null-safe). Handles data fetching, indicators,
  predictions, converter, portfolio, arbitrage, alerts and the AI Copilot.
- **`assets/indicators.js`** — RSI, SMA/EMA, composite signal, pattern detection.
- **`assets/extras.js`** — curated sample data (new/upcoming coins, airdrops, news, articles).
- **`assets/data-fallback.js`** — offline market snapshot so pages always render.

### Data

Live market data comes from the free [CoinGecko API](https://www.coingecko.com/en/api)
(top 1,000 coins via 4 paginated requests), Fear & Greed from
[alternative.me](https://alternative.me/crypto/fear-and-greed-index/). Every call
degrades to bundled/synthetically-generated data if the API is unavailable or rate-limited.

## Run it

```bash
cd web
python3 -m http.server 8000
# open http://localhost:8000
```

## Notes

Demo / educational project. Not affiliated with altFINS, CoinArbitrageBot or CoinCodex.
Predictions are model-based and **not financial advice**.
