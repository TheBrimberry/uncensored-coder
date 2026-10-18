"""
Market regime detection.

Identifies the current market state — trending, ranging, or high-volatility —
and outputs a recommended position-size multiplier. Regime is the hidden
variable behind 'why did my system stop working': the regime changed.

Uses ADX (trend strength), ATR% (volatility), BB width and EMA alignment as
orthogonal inputs so no single indicator dominates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from . import indicators as ind


class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    UNKNOWN = "unknown"


@dataclass
class RegimeResult:
    symbol: str
    regime: MarketRegime
    confidence: float           # 0..1
    adx: Optional[float]
    atr_pct: float              # ATR as % of price
    bb_width_pct: float         # Bollinger width as % of mid
    ema_alignment: str          # "bull" | "bear" | "mixed"
    size_factor: float          # Recommended multiplier vs your base size
    notes: List[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            f"=== REGIME: {self.symbol} ===",
            f"Regime      : {self.regime.value}  (confidence {self.confidence:.0%})",
            f"ADX         : {self.adx:.1f}" if self.adx is not None else "ADX: n/a",
            f"ATR%        : {self.atr_pct:.2f}%",
            f"BB width%   : {self.bb_width_pct:.2f}%",
            f"EMA alignment: {self.ema_alignment}",
            f"Size factor : {self.size_factor:.2f}× your base position size",
            "Notes:",
        ]
        for n in self.notes:
            lines.append(f"  • {n}")
        return "\n".join(lines)


def detect_regime(symbol: str, bars: Dict[str, List[float]]) -> RegimeResult:
    """Classify the current market regime from OHLCV bars."""
    h, l, c = bars["high"], bars["low"], bars["close"]
    price = c[-1]

    # --- indicators ---
    adx_data = ind.adx(h, l, c, 14)
    adx_val = ind.last(adx_data["adx"])
    pdi = ind.last(adx_data["plus_di"])
    ndi = ind.last(adx_data["minus_di"])

    atr_val = ind.last(ind.atr(h, l, c, 14))
    atr_pct = (atr_val / price * 100) if (atr_val and price) else 0.0

    bb = ind.bollinger_bands(c, 20, 2.0)
    bb_up = ind.last(bb["upper"])
    bb_lo = ind.last(bb["lower"])
    bb_mid = (bb_up + bb_lo) / 2 if (bb_up and bb_lo) else price
    bb_width_pct = ((bb_up - bb_lo) / bb_mid * 100) if (bb_up and bb_lo and bb_mid) else 0.0

    ema20 = ind.last(ind.ema(c, 20))
    ema50 = ind.last(ind.ema(c, 50))
    ema200 = ind.last(ind.ema(c, 200))

    # EMA alignment
    if ema20 and ema50 and ema200:
        if ema20 > ema50 > ema200:
            ema_alignment = "bull"
        elif ema20 < ema50 < ema200:
            ema_alignment = "bear"
        else:
            ema_alignment = "mixed"
    elif ema20 and ema50:
        ema_alignment = "bull" if ema20 > ema50 else "bear"
    else:
        ema_alignment = "unknown"

    notes: List[str] = []

    # --- regime classification ---
    # High-volatility: ATR% very elevated or BB extremely wide
    # This takes priority — even trending markets can be dangerously volatile
    typical_atr_pct = 1.5  # approximate baseline for daily bars
    is_high_vol = atr_pct > typical_atr_pct * 2.5 or bb_width_pct > 8.0

    if is_high_vol:
        regime = MarketRegime.HIGH_VOLATILITY
        confidence = min((atr_pct / (typical_atr_pct * 2.5)), 1.0)
        size_factor = 0.5
        notes.append(f"ATR {atr_pct:.1f}% is very elevated — half-size, widen stops.")
        notes.append("High-vol regimes punish tight stops and high frequency.")

    elif adx_val is not None and adx_val >= 25:
        # Trending — direction from DI crossover and EMA alignment
        if (pdi is not None and ndi is not None and pdi > ndi) or ema_alignment == "bull":
            regime = MarketRegime.TRENDING_UP
        else:
            regime = MarketRegime.TRENDING_DOWN
        confidence = min((adx_val - 25) / 25.0, 1.0)  # 50 ADX → confidence=1
        size_factor = 1.0 + 0.25 * confidence          # up to 1.25× in strong trend
        strength = "strong" if adx_val > 40 else "moderate"
        notes.append(f"ADX {adx_val:.1f} — {strength} trend. Ride it; use ATR trailing stops.")
        if ema_alignment in ("bull", "bear"):
            notes.append(f"EMA stack {ema_alignment}ish: all three EMAs aligned.")

    else:
        # Ranging — mean-reversion favoured
        regime = MarketRegime.RANGING
        confidence = (25 - (adx_val or 0)) / 25.0 if adx_val is not None else 0.5
        confidence = max(0.0, min(confidence, 1.0))
        size_factor = 0.8  # slightly smaller — ranges can break violently
        notes.append("Low ADX — range-bound. Fade extremes, don't chase breakouts.")
        if bb_width_pct < 3.0:
            notes.append("Bollinger bands compressed: coiled spring. Breakout may be imminent.")

    # Bonus notes
    if adx_val is not None and adx_val > 50:
        notes.append(f"ADX {adx_val:.1f} > 50: exceptionally strong trend — "
                     "momentum strategies outperform, mean-reversion will bleed.")
    if atr_pct < 0.5:
        notes.append("Very low ATR: illiquid or compressed; spreads eat into edge.")
    if ema_alignment == "mixed":
        notes.append("EMAs tangled — avoid breakout trades until they re-align.")

    return RegimeResult(
        symbol=symbol,
        regime=regime,
        confidence=round(confidence, 3),
        adx=round(adx_val, 2) if adx_val is not None else None,
        atr_pct=round(atr_pct, 3),
        bb_width_pct=round(bb_width_pct, 3),
        ema_alignment=ema_alignment,
        size_factor=round(size_factor, 2),
        notes=notes,
    )
