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
import os
from dataclasses import dataclass
from typing import Dict, List, Optional


class MarketDataError(RuntimeError):
    """Raised in strict 'real data only' mode when no real provider returns data."""


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


# ISO 4217 codes for the major/minor currencies the agent treats as FX.
_FX_CURRENCIES = {
    "USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD", "CNH", "CNY",
    "SEK", "NOK", "DKK", "SGD", "HKD", "ZAR", "MXN", "TRY", "PLN", "HUF",
}


def _looks_like_fx(symbol: str) -> bool:
    """Detect a spot FX pair like EURUSD or EUR/USD (two known currency codes)."""
    s = symbol.upper().replace("/", "").replace("=X", "")
    if len(s) != 6:
        return False
    return s[:3] in _FX_CURRENCIES and s[3:] in _FX_CURRENCIES


def _fx_to_yahoo(symbol: str) -> str:
    """Map an FX pair to Yahoo's ticker (EURUSD / EUR/USD -> EURUSD=X)."""
    s = symbol.upper().replace("/", "")
    return s if s.endswith("=X") else f"{s}=X"


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
    """Facade over optional data providers.

    `strict=True` ('real data only') means: if no real provider returns data we
    raise MarketDataError instead of fabricating a synthetic series. This is the
    right mode for live decisions. Strict can also be turned on globally with the
    env var OMNI_REAL_DATA_ONLY=1. Default is non-strict so the offline test
    suite and demos still work.
    """

    def __init__(self, crypto_exchange: str = "binance",
                 strict: Optional[bool] = None):
        self.crypto_exchange = crypto_exchange
        if strict is None:
            strict = os.environ.get("OMNI_REAL_DATA_ONLY", "").lower() in (
                "1", "true", "yes", "on")
        self.strict = strict

    def get_ohlcv(self, symbol: str, timeframe: str = "1d",
                  limit: int = 300) -> OHLCV:
        # FX is checked first: 'EUR/USD' contains a slash and would otherwise be
        # misread as crypto. Yahoo serves FX under the 'EURUSD=X' ticker.
        if _looks_like_fx(symbol):
            for provider in (
                lambda: self._try_alpaca(symbol, timeframe, limit, asset="fx"),
                lambda: self._try_yfinance(_fx_to_yahoo(symbol), timeframe, limit),
                lambda: self._try_stooq(symbol, timeframe, limit, asset="fx"),
            ):
                data = provider()
                if data:
                    data.symbol = symbol
                    return data
        elif _looks_like_crypto(symbol):
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
            for provider in (
                lambda: self._try_polygon(symbol, timeframe, limit),
                lambda: self._try_alpaca(symbol, timeframe, limit, asset="stock"),
                lambda: self._try_finnhub(symbol, timeframe, limit),
                lambda: self._try_yfinance(symbol, timeframe, limit),
                lambda: self._try_stooq(symbol, timeframe, limit, asset="stock"),
            ):
                data = provider()
                if data:
                    data.symbol = symbol
                    return data
        if self.strict:
            raise MarketDataError(
                f"No REAL market data available for '{symbol}' ({timeframe}). "
                "Real-data-only mode is on, so synthetic data is refused. "
                "Check: (1) internet connection, (2) the symbol uses your "
                "provider's exact format (BTC/USDT, AAPL, EURUSD), and "
                "(3) yfinance/ccxt are installed.")
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

    def _try_stooq(self, symbol: str, timeframe: str, limit: int,
                   asset: str = "stock") -> Optional[OHLCV]:
        """Keyless real daily data from Stooq (a reliable Yahoo backup).

        Only daily bars are served over the free CSV endpoint, so this is used
        as a resilience fallback for 1d requests on stocks/FX/indices."""
        if timeframe not in ("1d", "1day", "d", "1w"):
            return None
        try:
            import urllib.request
            s = symbol.upper().replace("/", "")
            if asset == "fx":
                code = s.lower()                       # eurusd
            else:
                code = symbol.lower()
                if "." not in code:                    # default US listing
                    code = code + ".us"
            url = f"https://stooq.com/q/d/l/?s={code}&i=d"
            req = urllib.request.Request(url, headers={"User-Agent": "OmniAgent/1.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                text = r.read().decode("utf-8", errors="ignore")
            lines = [ln for ln in text.strip().splitlines() if ln]
            if len(lines) < 2 or not lines[0].lower().startswith("date"):
                return None
            o, h, l, c, v = [], [], [], [], []
            for ln in lines[1:]:
                parts = ln.split(",")
                if len(parts) < 5:
                    continue
                try:
                    o.append(float(parts[1])); h.append(float(parts[2]))
                    l.append(float(parts[3])); c.append(float(parts[4]))
                    v.append(float(parts[5]) if len(parts) > 5 and parts[5] else 0.0)
                except ValueError:
                    continue
            if len(c) < 2:
                return None
            sl = slice(-limit, None)
            return OHLCV(symbol, timeframe, o[sl], h[sl], l[sl], c[sl], v[sl],
                         source="stooq")
        except Exception:
            return None

    def _try_alpaca(self, symbol: str, timeframe: str, limit: int,
                    asset: str = "stock") -> Optional[OHLCV]:
        """Real-time-grade bars from Alpaca, used automatically if API keys are
        set in env (APCA_API_KEY_ID / APCA_API_SECRET_KEY). No key -> skipped."""
        key = os.environ.get("APCA_API_KEY_ID")
        sec = os.environ.get("APCA_API_SECRET_KEY")
        if not key or not sec:
            return None
        try:
            import json as _json
            import urllib.request
            tf = {"1d": "1Day", "1h": "1Hour", "15m": "15Min", "5m": "5Min"}.get(timeframe, "1Day")
            if asset == "fx":
                return None  # FX via other providers; Alpaca FX is separate API
            base = "https://data.alpaca.markets/v2/stocks"
            url = f"{base}/{symbol.upper()}/bars?timeframe={tf}&limit={min(limit,10000)}"
            req = urllib.request.Request(url, headers={
                "APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec})
            with urllib.request.urlopen(req, timeout=12) as r:
                data = _json.loads(r.read().decode("utf-8"))
            bars = data.get("bars") or []
            if not bars:
                return None
            o = [b["o"] for b in bars]; h = [b["h"] for b in bars]
            l = [b["l"] for b in bars]; c = [b["c"] for b in bars]
            v = [b.get("v", 0) for b in bars]
            return OHLCV(symbol, timeframe, o, h, l, c, v, source="alpaca")
        except Exception:
            return None

    def _try_polygon(self, symbol: str, timeframe: str, limit: int) -> Optional[OHLCV]:
        """Polygon.io aggregates, used automatically if POLYGON_API_KEY is set."""
        key = os.environ.get("POLYGON_API_KEY")
        if not key:
            return None
        try:
            import json as _json
            import urllib.request
            from datetime import datetime, timedelta
            mult, span = {"1d": (1, "day"), "1h": (1, "hour"),
                          "15m": (15, "minute"), "5m": (5, "minute")}.get(timeframe, (1, "day"))
            end = datetime.utcnow().date()
            start = end - timedelta(days=900 if span == "day" else 30)
            url = (f"https://api.polygon.io/v2/aggs/ticker/{symbol.upper()}/range/"
                   f"{mult}/{span}/{start}/{end}?adjusted=true&sort=asc&limit=50000&apiKey={key}")
            with urllib.request.urlopen(url, timeout=12) as r:
                data = _json.loads(r.read().decode("utf-8"))
            res = data.get("results") or []
            if not res:
                return None
            res = res[-limit:]
            o = [b["o"] for b in res]; h = [b["h"] for b in res]
            l = [b["l"] for b in res]; c = [b["c"] for b in res]
            v = [b.get("v", 0) for b in res]
            return OHLCV(symbol, timeframe, o, h, l, c, v, source="polygon")
        except Exception:
            return None

    def _try_finnhub(self, symbol: str, timeframe: str, limit: int) -> Optional[OHLCV]:
        """Finnhub candles, used automatically if FINNHUB_API_KEY is set."""
        key = os.environ.get("FINNHUB_API_KEY")
        if not key:
            return None
        try:
            import json as _json
            import urllib.request
            from datetime import datetime, timedelta
            res = {"1d": "D", "1h": "60", "15m": "15", "5m": "5"}.get(timeframe, "D")
            now = int(datetime.utcnow().timestamp())
            span_days = 900 if res == "D" else 30
            frm = int((datetime.utcnow() - timedelta(days=span_days)).timestamp())
            url = (f"https://finnhub.io/api/v1/stock/candle?symbol={symbol.upper()}"
                   f"&resolution={res}&from={frm}&to={now}&token={key}")
            with urllib.request.urlopen(url, timeout=12) as r:
                data = _json.loads(r.read().decode("utf-8"))
            if data.get("s") != "ok":
                return None
            o, h, l, c = data["o"], data["h"], data["l"], data["c"]
            v = data.get("v", [0] * len(c))
            sl = slice(-limit, None)
            return OHLCV(symbol, timeframe, o[sl], h[sl], l[sl], c[sl], v[sl],
                         source="finnhub")
        except Exception:
            return None
