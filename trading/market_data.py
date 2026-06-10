"""
Multi-asset market data layer.

Unifies several optional providers behind one `MarketData.get_ohlcv()` call:
  * crypto  -> ccxt   (any of 100+ exchanges)
  * stocks/etf/fx/indices -> yfinance

Every provider is optional. If a dependency is missing we fall back to a
deterministic synthetic series so the rest of the pipeline (indicators,
strategies, agent) is always testable offline — clearly flagged as synthetic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class OHLCV:
    """Container of parallel OHLCV lists plus provenance metadata."""

    symbol: str
    timeframe: str
    open: List[float]
    high: List[float]
    low: List[float]
    close: List[float]
    volume: List[float]
    source: str
    synthetic: bool = False

    def as_bars(self) -> Dict[str, List[float]]:
        return {"open": self.open, "high": self.high, "low": self.low,
                "close": self.close, "volume": self.volume}

    def __len__(self) -> int:
        return len(self.close)


def _looks_like_crypto(symbol: str) -> bool:
    s = symbol.upper()
    return "/" in s or s.endswith(("USDT", "USDC", "PERP")) or s in {"BTC", "ETH"}


def _crypto_to_yahoo(symbol: str) -> str:
    """Map an exchange-style crypto symbol to Yahoo's ticker (BTC/USDT -> BTC-USD)."""
    s = symbol.upper().replace("PERP", "")
    base = s.split("/")[0] if "/" in s else s
    for quote in ("USDT", "USDC", "USD"):
        if base.endswith(quote) and base != quote:
            base = base[: -len(quote)]
            break
    return f"{base}-USD"


def _synthetic_series(symbol: str, limit: int, seed_price: float = 100.0) -> OHLCV:
    """Deterministic pseudo-random walk so offline runs still produce signals."""
    seed = sum(ord(c) for c in symbol)
    o, h, l, c, v = [], [], [], [], []
    price = seed_price + seed % 50
    for i in range(limit):
        # Reproducible "noise" without importing random.
        drift = math.sin((i + seed) / 9.0) * 0.6
        noise = math.cos((i * 1.7 + seed) / 5.0) * 1.1
        change = drift + noise
        open_p = price
        close_p = max(0.01, price + change)
        high_p = max(open_p, close_p) + abs(noise) * 0.5
        low_p = min(open_p, close_p) - abs(noise) * 0.5
        o.append(round(open_p, 4)); h.append(round(high_p, 4))
        l.append(round(low_p, 4)); c.append(round(close_p, 4))
        v.append(round(1000 + abs(noise) * 500, 2))
        price = close_p
    return OHLCV(symbol, "synthetic", o, h, l, c, v, source="synthetic", synthetic=True)


class MarketData:
    """Facade over optional data providers with synthetic fallback."""

    def __init__(self, crypto_exchange: str = "binance"):
        self.crypto_exchange = crypto_exchange

    def get_ohlcv(self, symbol: str, timeframe: str = "1d",
                  limit: int = 300) -> OHLCV:
        if _looks_like_crypto(symbol):
            # Prefer a real exchange; if blocked/unavailable, fall back to
            # Yahoo's crypto feed (BTC/USDT -> BTC-USD) before going synthetic.
            data = self._try_ccxt(symbol, timeframe, limit)
            if data:
                return data
            data = self._try_yfinance(_crypto_to_yahoo(symbol), timeframe, limit)
            if data:
                data.symbol = symbol
                return data
        else:
            data = self._try_yfinance(symbol, timeframe, limit)
            if data:
                return data
        return _synthetic_series(symbol, limit)

    # -- providers ---------------------------------------------------------
    def _try_ccxt(self, symbol: str, timeframe: str, limit: int) -> Optional[OHLCV]:
        try:
            import ccxt  # type: ignore
        except Exception:
            return None
        try:
            exchange = getattr(ccxt, self.crypto_exchange)()
            market_symbol = symbol if "/" in symbol else f"{symbol[:-4]}/{symbol[-4:]}" \
                if symbol.upper().endswith("USDT") else f"{symbol}/USDT"
            raw = exchange.fetch_ohlcv(market_symbol, timeframe=timeframe, limit=limit)
            if not raw:
                return None
            o = [r[1] for r in raw]; h = [r[2] for r in raw]
            l = [r[3] for r in raw]; c = [r[4] for r in raw]
            v = [r[5] for r in raw]
            return OHLCV(symbol, timeframe, o, h, l, c, v, source=f"ccxt:{self.crypto_exchange}")
        except Exception:
            return None

    def _try_yfinance(self, symbol: str, timeframe: str, limit: int) -> Optional[OHLCV]:
        try:
            import yfinance as yf  # type: ignore
        except Exception:
            return None
        try:
            interval = {"1d": "1d", "1h": "1h", "15m": "15m", "5m": "5m"}.get(timeframe, "1d")
            period = "2y" if interval == "1d" else "60d"
            df = yf.download(symbol, period=period, interval=interval,
                             progress=False, auto_adjust=True)
            if df is None or df.empty:
                return None
            df = df.tail(limit)
            col = lambda name: [float(x) for x in df[name].values.flatten()]
            return OHLCV(symbol, timeframe, col("Open"), col("High"), col("Low"),
                         col("Close"), col("Volume"), source="yfinance")
        except Exception:
            return None
