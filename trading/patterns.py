"""
Pattern & key-level detection — the side-by-side co-pilot layer.

Highlights what's happening on the chart in plain language: trend & regime,
support/resistance levels, candlestick patterns, volatility squeezes, RSI/price
divergences and recent breakouts. Feeds both the human (readable insights) and
the LLM (structured context) so the agent can point at patterns as they form.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import indicators as ind


@dataclass
class Pattern:
    name: str
    kind: str                # "candle" | "level" | "trend" | "volatility" | "divergence" | "breakout"
    bias: str                # "bullish" | "bearish" | "neutral"
    note: str


@dataclass
class MarketInsights:
    symbol: str
    regime: str
    key_levels: Dict[str, float]
    patterns: List[Pattern] = field(default_factory=list)
    highlights: List[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [f"=== MARKET CO-PILOT: {self.symbol} ===",
                 f"Regime: {self.regime}"]
        if self.key_levels:
            lines.append("Key levels: " + ", ".join(
                f"{k} {v:.4f}" for k, v in self.key_levels.items()))
        if self.patterns:
            lines.append("Patterns:")
            for p in self.patterns:
                lines.append(f"  • [{p.bias}] {p.name} ({p.kind}) — {p.note}")
        if self.highlights:
            lines.append("Key insights:")
            for h in self.highlights:
                lines.append(f"  → {h}")
        return "\n".join(lines)


def _swing_levels(high: List[float], low: List[float], lookback: int = 50):
    window_h = high[-lookback:] if len(high) >= lookback else high
    window_l = low[-lookback:] if len(low) >= lookback else low
    return max(window_h), min(window_l)


def _detect_candles(o, h, l, c) -> List[Pattern]:
    out: List[Pattern] = []
    if len(c) < 3:
        return out
    body = abs(c[-1] - o[-1])
    rng = (h[-1] - l[-1]) or 1e-9
    upper = h[-1] - max(c[-1], o[-1])
    lower = min(c[-1], o[-1]) - l[-1]

    # Doji
    if body <= 0.1 * rng:
        out.append(Pattern("Doji", "candle", "neutral", "indecision; potential reversal."))
    # Hammer / shooting star
    if lower > 2 * body and upper < body:
        out.append(Pattern("Hammer", "candle", "bullish", "long lower wick; buyers stepped in."))
    if upper > 2 * body and lower < body:
        out.append(Pattern("Shooting Star", "candle", "bearish", "long upper wick; sellers rejected highs."))
    # Engulfing (last two candles)
    prev_body_up = c[-2] > o[-2]
    cur_body_up = c[-1] > o[-1]
    if cur_body_up and not prev_body_up and c[-1] >= o[-2] and o[-1] <= c[-2]:
        out.append(Pattern("Bullish Engulfing", "candle", "bullish", "buyers overwhelmed prior down candle."))
    if not cur_body_up and prev_body_up and o[-1] >= c[-2] and c[-1] <= o[-2]:
        out.append(Pattern("Bearish Engulfing", "candle", "bearish", "sellers overwhelmed prior up candle."))
    return out


def _detect_divergence(close: List[float], rsi_vals: List[Optional[float]]) -> Optional[Pattern]:
    pts = [(i, close[i], rsi_vals[i]) for i in range(len(close)) if rsi_vals[i] is not None]
    if len(pts) < 12:
        return None
    recent = pts[-12:]
    (i1, p1, r1), (i2, p2, r2) = recent[0], recent[-1]
    if p2 > p1 and r2 < r1:
        return Pattern("Bearish RSI Divergence", "divergence", "bearish",
                       "price higher but momentum lower — uptrend weakening.")
    if p2 < p1 and r2 > r1:
        return Pattern("Bullish RSI Divergence", "divergence", "bullish",
                       "price lower but momentum higher — downtrend weakening.")
    return None


def analyze_patterns(symbol: str, bars: Dict[str, List[float]]) -> MarketInsights:
    o, h, l, c = bars["open"], bars["high"], bars["low"], bars["close"]
    patterns: List[Pattern] = []
    highlights: List[str] = []

    ema20 = ind.last(ind.ema(c, 20))
    ema50 = ind.last(ind.ema(c, 50))
    ema200 = ind.last(ind.ema(c, 200))
    rsi_series = ind.rsi(c, 14)
    rsi = ind.last(rsi_series)
    atr = ind.last(ind.atr(h, l, c, 14))
    price = c[-1]

    # --- regime ---
    if ema50 and ema200:
        if ema50 > ema200 and price > ema50:
            regime = "Uptrend (price > EMA50 > EMA200)"
        elif ema50 < ema200 and price < ema50:
            regime = "Downtrend (price < EMA50 < EMA200)"
        else:
            regime = "Transition / range (EMAs intertwined)"
    else:
        regime = "Indeterminate (insufficient history)"

    # --- key levels ---
    res, sup = _swing_levels(h, l, 50)
    key_levels = {"resistance": res, "support": sup}
    if ema200:
        key_levels["EMA200"] = ema200
    if atr:
        key_levels["ATR"] = atr

    # --- candles ---
    patterns += _detect_candles(o, h, l, c)

    # --- volatility squeeze (Bollinger width vs ATR) ---
    bb = ind.bollinger_bands(c, 20, 2.0)
    up, lo = ind.last(bb["upper"]), ind.last(bb["lower"])
    if up and lo and atr:
        width = up - lo
        if width < 1.5 * atr * 2:        # bands tight relative to ATR
            patterns.append(Pattern("Volatility Squeeze", "volatility", "neutral",
                                    "Bollinger bands compressed — breakout often follows."))

    # --- breakout of recent range ---
    if price >= res * 0.999:
        patterns.append(Pattern("Range Breakout (up)", "breakout", "bullish",
                                f"price testing/breaking resistance {res:.4f}."))
    elif price <= sup * 1.001:
        patterns.append(Pattern("Range Breakdown (down)", "breakout", "bearish",
                                f"price testing/breaking support {sup:.4f}."))

    # --- divergence ---
    div = _detect_divergence(c, rsi_series)
    if div:
        patterns.append(div)

    # --- highlights (key insights) ---
    if rsi is not None:
        if rsi > 70:
            highlights.append(f"RSI {rsi:.0f} overbought — chasing longs is risky here.")
        elif rsi < 30:
            highlights.append(f"RSI {rsi:.0f} oversold — watch for a bounce, not a falling knife.")
    if atr and price:
        highlights.append(f"Volatility ≈ {atr / price * 100:.1f}% ATR — "
                          f"size stops at least {2 * atr:.4f} away.")
    bulls = sum(p.bias == "bullish" for p in patterns)
    bears = sum(p.bias == "bearish" for p in patterns)
    if bulls or bears:
        lean = "bullish" if bulls > bears else "bearish" if bears > bulls else "mixed"
        highlights.append(f"Pattern balance leans {lean} ({bulls} bull / {bears} bear).")
    if not highlights:
        highlights.append("No strong signal — patience beats forcing a trade.")

    return MarketInsights(symbol, regime, key_levels, patterns, highlights)
