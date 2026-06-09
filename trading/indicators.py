"""
Technical indicators.

Pure-python implementations (no hard dependency on numpy/pandas/TA-Lib) so the
agent can compute signals anywhere. If pandas is available the helpers also
accept/return pandas Series transparently. Mirrors the families found in TA-Lib
and pandas-ta but kept lean and dependency-free.

All functions take a list (or Series) of floats and return a list aligned to the
input length, with `None` for warm-up periods that cannot be computed yet.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

Number = float


def _to_list(values: Sequence) -> List[float]:
    return [float(v) for v in values]


def sma(values: Sequence[Number], period: int) -> List[Optional[float]]:
    """Simple moving average."""
    vals = _to_list(values)
    out: List[Optional[float]] = [None] * len(vals)
    if period <= 0:
        return out
    running = 0.0
    for i, v in enumerate(vals):
        running += v
        if i >= period:
            running -= vals[i - period]
        if i >= period - 1:
            out[i] = running / period
    return out


def ema(values: Sequence[Number], period: int) -> List[Optional[float]]:
    """Exponential moving average (seeded with the first SMA)."""
    vals = _to_list(values)
    out: List[Optional[float]] = [None] * len(vals)
    if period <= 0 or len(vals) < period:
        return out
    k = 2 / (period + 1)
    seed = sum(vals[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(vals)):
        prev = vals[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(values: Sequence[Number], period: int = 14) -> List[Optional[float]]:
    """Relative Strength Index (Wilder's smoothing)."""
    vals = _to_list(values)
    out: List[Optional[float]] = [None] * len(vals)
    if len(vals) <= period:
        return out
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        delta = vals[i] - vals[i - 1]
        gains += max(delta, 0.0)
        losses += max(-delta, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    out[period] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    for i in range(period + 1, len(vals)):
        delta = vals[i] - vals[i - 1]
        gain, loss = max(delta, 0.0), max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return out


def macd(values: Sequence[Number], fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD line, signal line, histogram."""
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    macd_line = [
        (f - s) if (f is not None and s is not None) else None
        for f, s in zip(ema_fast, ema_slow)
    ]
    clean = [m for m in macd_line if m is not None]
    sig_clean = ema(clean, signal)
    # re-align signal to original index
    signal_line: List[Optional[float]] = [None] * len(macd_line)
    j = 0
    for i, m in enumerate(macd_line):
        if m is not None:
            signal_line[i] = sig_clean[j]
            j += 1
    hist = [
        (m - s) if (m is not None and s is not None) else None
        for m, s in zip(macd_line, signal_line)
    ]
    return {"macd": macd_line, "signal": signal_line, "hist": hist}


def bollinger_bands(values: Sequence[Number], period: int = 20, num_std: float = 2.0):
    """Bollinger Bands (middle SMA, upper, lower)."""
    vals = _to_list(values)
    middle = sma(vals, period)
    upper: List[Optional[float]] = [None] * len(vals)
    lower: List[Optional[float]] = [None] * len(vals)
    for i in range(len(vals)):
        if i >= period - 1:
            window = vals[i - period + 1: i + 1]
            mean = sum(window) / period
            var = sum((x - mean) ** 2 for x in window) / period
            std = var ** 0.5
            upper[i] = mean + num_std * std
            lower[i] = mean - num_std * std
    return {"middle": middle, "upper": upper, "lower": lower}


def true_range(high: Sequence[Number], low: Sequence[Number], close: Sequence[Number]) -> List[Optional[float]]:
    h, l, c = _to_list(high), _to_list(low), _to_list(close)
    out: List[Optional[float]] = [None] * len(c)
    for i in range(len(c)):
        if i == 0:
            out[i] = h[i] - l[i]
        else:
            out[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    return out


def atr(high: Sequence[Number], low: Sequence[Number], close: Sequence[Number], period: int = 14):
    """Average True Range (Wilder smoothing) — the agent's volatility unit."""
    tr = true_range(high, low, close)
    tr_clean = [t for t in tr if t is not None]
    out: List[Optional[float]] = [None] * len(tr)
    if len(tr_clean) < period:
        return out
    first = sum(tr_clean[:period]) / period
    out[period - 1] = first
    prev = first
    for i in range(period, len(tr)):
        prev = (prev * (period - 1) + tr[i]) / period
        out[i] = prev
    return out


def stochastic(high, low, close, k_period: int = 14, d_period: int = 3):
    """Stochastic oscillator (%K, %D)."""
    h, l, c = _to_list(high), _to_list(low), _to_list(close)
    k: List[Optional[float]] = [None] * len(c)
    for i in range(len(c)):
        if i >= k_period - 1:
            hh = max(h[i - k_period + 1: i + 1])
            ll = min(l[i - k_period + 1: i + 1])
            k[i] = 50.0 if hh == ll else (c[i] - ll) / (hh - ll) * 100
    k_clean = [x for x in k if x is not None]
    d_clean = sma(k_clean, d_period)
    d: List[Optional[float]] = [None] * len(c)
    j = 0
    for i in range(len(c)):
        if k[i] is not None:
            d[i] = d_clean[j]
            j += 1
    return {"k": k, "d": d}


def supertrend(high, low, close, period: int = 10, multiplier: float = 3.0):
    """Supertrend trend-following indicator. Returns line + direction (+1/-1)."""
    h, l, c = _to_list(high), _to_list(low), _to_list(close)
    atr_vals = atr(h, l, c, period)
    line: List[Optional[float]] = [None] * len(c)
    direction: List[Optional[int]] = [None] * len(c)
    prev_line = None
    prev_dir = 1
    for i in range(len(c)):
        if atr_vals[i] is None:
            continue
        hl2 = (h[i] + l[i]) / 2
        upper = hl2 + multiplier * atr_vals[i]
        lower = hl2 - multiplier * atr_vals[i]
        if prev_line is None:
            prev_line, prev_dir = lower, 1
        else:
            if c[i] > prev_line:
                prev_dir = 1
            elif c[i] < prev_line:
                prev_dir = -1
            prev_line = lower if prev_dir == 1 else upper
        line[i], direction[i] = prev_line, prev_dir
    return {"line": line, "direction": direction}


def last(values: Sequence[Optional[float]]) -> Optional[float]:
    """Most recent non-None value (convenience for signal logic)."""
    for v in reversed(list(values)):
        if v is not None:
            return v
    return None
