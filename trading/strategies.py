"""
Strategy library.

Each strategy consumes OHLCV bars and emits a `Signal` (direction, strength,
rationale). Strategies are intentionally small and transparent — the agent
combines them and the LLM narrates them, rather than hiding logic in a black box.

A `Bars` is a dict of parallel lists: {"open","high","low","close","volume"}.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List

from . import indicators as ind


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class Signal:
    name: str
    direction: Direction
    strength: float          # 0..1 confidence of *this* strategy
    rationale: str

    def as_dict(self) -> dict:
        return {
            "strategy": self.name,
            "direction": self.direction.value,
            "strength": round(self.strength, 3),
            "rationale": self.rationale,
        }


Bars = Dict[str, List[float]]
StrategyFn = Callable[[Bars], Signal]


def _closes(bars: Bars) -> List[float]:
    return bars["close"]


# ---------------------------------------------------------------------------
# Individual strategies
# ---------------------------------------------------------------------------
def ma_crossover(bars: Bars, fast: int = 50, slow: int = 200) -> Signal:
    """Classic trend-following golden/death cross."""
    c = _closes(bars)
    f, s = ind.last(ind.ema(c, fast)), ind.last(ind.ema(c, slow))
    if f is None or s is None:
        return Signal("ma_crossover", Direction.FLAT, 0.0, "insufficient history")
    spread = (f - s) / s if s else 0.0
    if f > s:
        return Signal("ma_crossover", Direction.LONG, min(abs(spread) * 20, 1.0),
                      f"EMA{fast} ({f:.4f}) above EMA{slow} ({s:.4f}): uptrend.")
    return Signal("ma_crossover", Direction.SHORT, min(abs(spread) * 20, 1.0),
                  f"EMA{fast} ({f:.4f}) below EMA{slow} ({s:.4f}): downtrend.")


def rsi_reversion(bars: Bars, period: int = 14, low: float = 30, high: float = 70) -> Signal:
    """Mean reversion from RSI extremes."""
    r = ind.last(ind.rsi(_closes(bars), period))
    if r is None:
        return Signal("rsi_reversion", Direction.FLAT, 0.0, "insufficient history")
    if r < low:
        return Signal("rsi_reversion", Direction.LONG, min((low - r) / low, 1.0),
                      f"RSI {r:.1f} oversold (<{low}): mean-reversion long.")
    if r > high:
        return Signal("rsi_reversion", Direction.SHORT, min((r - high) / (100 - high), 1.0),
                      f"RSI {r:.1f} overbought (>{high}): mean-reversion short.")
    return Signal("rsi_reversion", Direction.FLAT, 0.0, f"RSI {r:.1f} neutral.")


def bollinger_breakout(bars: Bars, period: int = 20, num_std: float = 2.0) -> Signal:
    """Breakout when price closes outside the bands."""
    c = _closes(bars)
    bb = ind.bollinger_bands(c, period, num_std)
    price, up, lo = c[-1], ind.last(bb["upper"]), ind.last(bb["lower"])
    if up is None or lo is None:
        return Signal("bollinger_breakout", Direction.FLAT, 0.0, "insufficient history")
    if price > up:
        return Signal("bollinger_breakout", Direction.LONG, 0.6,
                      f"Close {price:.4f} broke upper band {up:.4f}: volatility expansion up.")
    if price < lo:
        return Signal("bollinger_breakout", Direction.SHORT, 0.6,
                      f"Close {price:.4f} broke lower band {lo:.4f}: volatility expansion down.")
    return Signal("bollinger_breakout", Direction.FLAT, 0.0, "price inside bands.")


def macd_momentum(bars: Bars) -> Signal:
    """Momentum from MACD histogram sign + slope."""
    m = ind.macd(_closes(bars))
    hist = [h for h in m["hist"] if h is not None]
    if len(hist) < 2:
        return Signal("macd_momentum", Direction.FLAT, 0.0, "insufficient history")
    cur, prev = hist[-1], hist[-2]
    rising = cur > prev
    if cur > 0 and rising:
        return Signal("macd_momentum", Direction.LONG, min(abs(cur) * 5 + 0.3, 1.0),
                      f"MACD hist {cur:.4f} positive & rising: bullish momentum.")
    if cur < 0 and not rising:
        return Signal("macd_momentum", Direction.SHORT, min(abs(cur) * 5 + 0.3, 1.0),
                      f"MACD hist {cur:.4f} negative & falling: bearish momentum.")
    return Signal("macd_momentum", Direction.FLAT, 0.2, f"MACD hist {cur:.4f} mixed.")


def supertrend_follow(bars: Bars, period: int = 10, multiplier: float = 3.0) -> Signal:
    """Follow the Supertrend direction."""
    st = ind.supertrend(bars["high"], bars["low"], bars["close"], period, multiplier)
    d = ind.last(st["direction"])
    if d is None:
        return Signal("supertrend_follow", Direction.FLAT, 0.0, "insufficient history")
    if d > 0:
        return Signal("supertrend_follow", Direction.LONG, 0.55, "Supertrend bullish.")
    return Signal("supertrend_follow", Direction.SHORT, 0.55, "Supertrend bearish.")


def donchian_breakout(bars: Bars, period: int = 20) -> Signal:
    """Turtle-style Donchian channel breakout: buy 20-day high, sell 20-day low."""
    h, l, c = bars["high"], bars["low"], bars["close"]
    ch = ind.donchian(h, l, period)
    price = c[-1]
    up = ind.last(ch["upper"])
    lo = ind.last(ch["lower"])
    if up is None or lo is None:
        return Signal("donchian_breakout", Direction.FLAT, 0.0, "insufficient history")
    if price >= up:
        return Signal("donchian_breakout", Direction.LONG, 0.65,
                      f"Price {price:.4f} at {period}-bar high {up:.4f}: Turtle breakout long.")
    if price <= lo:
        return Signal("donchian_breakout", Direction.SHORT, 0.65,
                      f"Price {price:.4f} at {period}-bar low {lo:.4f}: Turtle breakout short.")
    mid = (up + lo) / 2
    if price > mid:
        return Signal("donchian_breakout", Direction.LONG, 0.25, f"In upper half of channel.")
    return Signal("donchian_breakout", Direction.SHORT, 0.25, f"In lower half of channel.")


def stochastic_cross(bars: Bars, k_period: int = 14, d_period: int = 3,
                     low_thresh: float = 20, high_thresh: float = 80) -> Signal:
    """Stochastic %K/%D crossover from oversold/overbought zones."""
    h, l, c = bars["high"], bars["low"], bars["close"]
    st = ind.stochastic(h, l, c, k_period, d_period)
    k, d = ind.last(st["k"]), ind.last(st["d"])
    if k is None or d is None:
        return Signal("stochastic_cross", Direction.FLAT, 0.0, "insufficient history")
    k_vals = [v for v in st["k"] if v is not None]
    d_vals = [v for v in st["d"] if v is not None]
    if len(k_vals) < 2 or len(d_vals) < 2:
        return Signal("stochastic_cross", Direction.FLAT, 0.0, "insufficient history")
    prev_k, prev_d = k_vals[-2], d_vals[-2]
    # Bullish cross from oversold
    if k > d and prev_k <= prev_d and k < high_thresh:
        return Signal("stochastic_cross", Direction.LONG, 0.6,
                      f"Stochastic bullish cross %K({k:.1f})>%D({d:.1f}) from oversold zone.")
    # Bearish cross from overbought
    if k < d and prev_k >= prev_d and k > low_thresh:
        return Signal("stochastic_cross", Direction.SHORT, 0.6,
                      f"Stochastic bearish cross %K({k:.1f})<%D({d:.1f}) from overbought zone.")
    if k < low_thresh:
        return Signal("stochastic_cross", Direction.LONG, 0.3, f"Stochastic {k:.1f} oversold.")
    if k > high_thresh:
        return Signal("stochastic_cross", Direction.SHORT, 0.3, f"Stochastic {k:.1f} overbought.")
    return Signal("stochastic_cross", Direction.FLAT, 0.0, f"Stochastic {k:.1f} neutral.")


def mean_reversion_zscore(bars: Bars, period: int = 20, threshold: float = 2.0) -> Signal:
    """Statistical mean-reversion when price is extreme on a rolling Z-score."""
    c = _closes(bars)
    z_series = ind.zscore(c, period)
    z = ind.last(z_series)
    if z is None:
        return Signal("mean_reversion_zscore", Direction.FLAT, 0.0, "insufficient history")
    if z <= -threshold:
        strength = min(abs(z) / (threshold * 2), 1.0)
        return Signal("mean_reversion_zscore", Direction.LONG, strength,
                      f"Z-score {z:.2f} extreme oversold — stat mean-reversion long.")
    if z >= threshold:
        strength = min(abs(z) / (threshold * 2), 1.0)
        return Signal("mean_reversion_zscore", Direction.SHORT, strength,
                      f"Z-score {z:.2f} extreme overbought — stat mean-reversion short.")
    return Signal("mean_reversion_zscore", Direction.FLAT, 0.0,
                  f"Z-score {z:.2f}: within normal range.")


def cci_reversal(bars: Bars, period: int = 20, threshold: float = 100.0) -> Signal:
    """CCI extreme reversal: >+100 overbought, <-100 oversold."""
    h, l, c = bars["high"], bars["low"], bars["close"]
    cci_series = ind.cci(h, l, c, period)
    val = ind.last(cci_series)
    if val is None:
        return Signal("cci_reversal", Direction.FLAT, 0.0, "insufficient history")
    if val < -threshold:
        return Signal("cci_reversal", Direction.LONG, min(abs(val) / 200, 1.0),
                      f"CCI {val:.0f} extreme oversold — reversal long.")
    if val > threshold:
        return Signal("cci_reversal", Direction.SHORT, min(abs(val) / 200, 1.0),
                      f"CCI {val:.0f} extreme overbought — reversal short.")
    return Signal("cci_reversal", Direction.FLAT, 0.0, f"CCI {val:.0f} neutral.")


def volume_momentum(bars: Bars) -> Signal:
    """OBV trend direction confirms or diverges from price momentum."""
    c = _closes(bars)
    v = bars.get("volume", [1.0] * len(c))
    obv_vals = ind.obv(c, v)
    if len(obv_vals) < 20:
        return Signal("volume_momentum", Direction.FLAT, 0.0, "insufficient history")
    obv_ema = ind.ema(obv_vals, 10)
    obv_slow = ind.ema(obv_vals, 30)
    fast_v = ind.last(obv_ema)
    slow_v = ind.last(obv_slow)
    if fast_v is None or slow_v is None:
        return Signal("volume_momentum", Direction.FLAT, 0.0, "insufficient history")
    price_up = c[-1] > c[-20]
    obv_up = fast_v > slow_v
    if price_up and obv_up:
        return Signal("volume_momentum", Direction.LONG, 0.55,
                      "OBV rising with price: volume confirms uptrend.")
    if not price_up and not obv_up:
        return Signal("volume_momentum", Direction.SHORT, 0.55,
                      "OBV falling with price: volume confirms downtrend.")
    if price_up and not obv_up:
        return Signal("volume_momentum", Direction.SHORT, 0.3,
                      "Price up but OBV diverging down: distribution, watch for reversal.")
    return Signal("volume_momentum", Direction.LONG, 0.3,
                  "Price down but OBV diverging up: accumulation, watch for reversal.")


def keltner_breakout(bars: Bars, ema_period: int = 20,
                     atr_period: int = 10, multiplier: float = 2.0) -> Signal:
    """Price outside Keltner Channel signals volatility breakout."""
    h, l, c = bars["high"], bars["low"], bars["close"]
    kc = ind.keltner_channels(h, l, c, ema_period, atr_period, multiplier)
    price = c[-1]
    up = ind.last(kc["upper"])
    lo = ind.last(kc["lower"])
    if up is None or lo is None:
        return Signal("keltner_breakout", Direction.FLAT, 0.0, "insufficient history")
    if price > up:
        return Signal("keltner_breakout", Direction.LONG, 0.6,
                      f"Price {price:.4f} above Keltner upper {up:.4f}: momentum breakout.")
    if price < lo:
        return Signal("keltner_breakout", Direction.SHORT, 0.6,
                      f"Price {price:.4f} below Keltner lower {lo:.4f}: momentum breakdown.")
    return Signal("keltner_breakout", Direction.FLAT, 0.0, "Price within Keltner channel.")


def adx_trend_strength(bars: Bars, period: int = 14,
                       threshold: float = 25.0) -> Signal:
    """ADX trend strength + DI direction. Only signals in trending regimes."""
    h, l, c = bars["high"], bars["low"], bars["close"]
    adx_data = ind.adx(h, l, c, period)
    adx_val = ind.last(adx_data["adx"])
    pdi = ind.last(adx_data["plus_di"])
    ndi = ind.last(adx_data["minus_di"])
    if adx_val is None or pdi is None or ndi is None:
        return Signal("adx_trend_strength", Direction.FLAT, 0.0, "insufficient history")
    if adx_val < threshold:
        return Signal("adx_trend_strength", Direction.FLAT, 0.0,
                      f"ADX {adx_val:.1f} below {threshold} — no trend, avoid breakout strategies.")
    strength = min((adx_val - threshold) / (50 - threshold), 1.0)
    if pdi > ndi:
        return Signal("adx_trend_strength", Direction.LONG, strength,
                      f"ADX {adx_val:.1f} strong trend, +DI({pdi:.1f}) > -DI({ndi:.1f}): bullish.")
    return Signal("adx_trend_strength", Direction.SHORT, strength,
                  f"ADX {adx_val:.1f} strong trend, -DI({ndi:.1f}) > +DI({pdi:.1f}): bearish.")


# ---------------------------------------------------------------------------
# Registry + ensemble
# ---------------------------------------------------------------------------
STRATEGIES: Dict[str, StrategyFn] = {
    "ma_crossover": ma_crossover,
    "rsi_reversion": rsi_reversion,
    "bollinger_breakout": bollinger_breakout,
    "macd_momentum": macd_momentum,
    "supertrend_follow": supertrend_follow,
    "donchian_breakout": donchian_breakout,
    "stochastic_cross": stochastic_cross,
    "mean_reversion_zscore": mean_reversion_zscore,
    "cci_reversal": cci_reversal,
    "volume_momentum": volume_momentum,
    "keltner_breakout": keltner_breakout,
    "adx_trend_strength": adx_trend_strength,
}


def run_all(bars: Bars) -> List[Signal]:
    """Run every registered strategy and collect their signals."""
    return [fn(bars) for fn in STRATEGIES.values()]


def ensemble(signals: List[Signal]) -> Signal:
    """Combine strategy signals into one net, strength-weighted view."""
    score = 0.0
    weight = 0.0
    for s in signals:
        if s.direction == Direction.LONG:
            score += s.strength
        elif s.direction == Direction.SHORT:
            score -= s.strength
        weight += s.strength
    if weight == 0:
        return Signal("ensemble", Direction.FLAT, 0.0, "no strategy had conviction.")
    net = score / weight  # -1..1
    direction = Direction.LONG if net > 0.15 else Direction.SHORT if net < -0.15 else Direction.FLAT
    longs = [s.name for s in signals if s.direction == Direction.LONG]
    shorts = [s.name for s in signals if s.direction == Direction.SHORT]
    rationale = f"Net bias {net:+.2f}. Long: {longs or '—'}. Short: {shorts or '—'}."
    return Signal("ensemble", direction, min(abs(net), 1.0), rationale)
