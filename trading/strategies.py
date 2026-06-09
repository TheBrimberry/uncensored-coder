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


# ---------------------------------------------------------------------------
# Registry + ensemble
# ---------------------------------------------------------------------------
STRATEGIES: Dict[str, StrategyFn] = {
    "ma_crossover": ma_crossover,
    "rsi_reversion": rsi_reversion,
    "bollinger_breakout": bollinger_breakout,
    "macd_momentum": macd_momentum,
    "supertrend_follow": supertrend_follow,
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
