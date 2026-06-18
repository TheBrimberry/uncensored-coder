# Market data sources

The agent is **real-data-only** by default. It tries providers in priority order
and uses the first that returns real data; if none do, it refuses (no synthetic
data) so you never act on fabricated numbers.

## Works out of the box (no setup, free)
- **Yahoo Finance** (`yfinance`) — stocks, ETFs, FX, indices, major crypto.
- **ccxt** — exchange-native crypto (order-level feeds) when reachable.
- **Stooq** — keyless daily backup for stocks/FX/indices (resilience if Yahoo
  hiccups).

## Optional premium real-time feeds (auto-on if you set a key)
Set any of these as environment variables and the agent uses them automatically,
ahead of the free sources. No code changes needed.

| Provider | Env variables | Covers |
|---|---|---|
| Alpaca   | `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY` | US stocks |
| Polygon  | `POLYGON_API_KEY` | US stocks/indices |
| Finnhub  | `FINNHUB_API_KEY` | US stocks |

### Setting a key on Windows (example, Finnhub)
PowerShell (persists for your user):
```
setx FINNHUB_API_KEY "your_key_here"
```
Close and reopen the terminal (and restart `serve.py`) so it picks up the key.

## Forcing / relaxing real-data-only
- It's ON by default in `serve.py` and `trade.py`.
- To allow the synthetic fallback for offline UI testing only:
  - server: set `OMNI_ALLOW_SYNTHETIC=1`
  - CLI: `python trade.py SYMBOL --allow-synthetic`
- To force strict everywhere (library included): `OMNI_REAL_DATA_ONLY=1`.

## Symbol formats
- Stocks: `AAPL`, `MSFT`, `TSLA`
- FX: `EURUSD` or `EUR/USD`
- Crypto: `BTC/USDT`, `ETH/USDT` (or `BTC-USD`)
- Indices/ETF: `SPY`, `QQQ`, `^GSPC`
