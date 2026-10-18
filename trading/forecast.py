"""
Probabilistic forecasting.

Honest forecasting: markets are not deterministic, so we never output "price will
be X". Instead we estimate a **direction probability**, an **expected move band**
(scaled by recent volatility), and a **confidence** that degrades with horizon.

Method (transparent, no black box):
  * Direction probability from blended momentum (trend slope + strategy ensemble).
  * Expected move band from ATR / realized volatility, widened by sqrt(horizon).
  * Confidence shrinks as horizon grows and as signals disagree.

This is upgradable: drop in qlib/FinRL/FinGPT models behind the same interface.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List

from . import indicators as ind
from . import strategies as strat


@dataclass
class Forecast:
    symbol: str
    horizon: int                 # bars ahead
    direction: str               # up | down | sideways
    prob_up: float               # 0..1
    expected_return_pct: float   # central estimate
    low_band_pct: float          # ~1 sigma lower
    high_band_pct: float         # ~1 sigma upper
    confidence: float            # 0..1
    notes: str

    def summary(self) -> str:
        return (
            f"{self.symbol} {self.horizon}-bar outlook: {self.direction.upper()} "
            f"(P(up)={self.prob_up:.0%}). Expected {self.expected_return_pct:+.2f}% "
            f"in [{self.low_band_pct:+.2f}%, {self.high_band_pct:+.2f}%]. "
            f"Confidence {self.confidence:.0%}. {self.notes}"
        )


class Forecaster:
    def forecast(self, symbol: str, bars: Dict[str, List[float]],
                 horizon: int = 5) -> Forecast:
        c = bars["close"]
        if len(c) < 30:
            return Forecast(symbol, horizon, "sideways", 0.5, 0.0, 0.0, 0.0, 0.1,
                            "Insufficient history for a reliable forecast.")

        # --- directional bias from strategy ensemble + trend slope -------
        signals = strat.run_all(bars)
        net = strat.ensemble(signals)
        bias = {"long": 1.0, "short": -1.0, "flat": 0.0}[net.direction.value] * net.strength

        ema_fast = ind.last(ind.ema(c, 20)) or c[-1]
        ema_slow = ind.last(ind.ema(c, 50)) or c[-1]
        slope = (ema_fast - ema_slow) / ema_slow if ema_slow else 0.0
        trend_bias = max(-1.0, min(1.0, slope * 25))

        combined = 0.6 * bias + 0.4 * trend_bias            # -1..1
        prob_up = 0.5 + combined * 0.5                       # 0..1
        prob_up = min(0.95, max(0.05, prob_up))

        # --- volatility band ---------------------------------------------
        atr_val = ind.last(ind.atr(bars["high"], bars["low"], c, 14)) or 0.0
        atr_pct = (atr_val / c[-1] * 100) if c[-1] else 0.0
        horizon_scale = math.sqrt(max(horizon, 1))
        band = atr_pct * horizon_scale

        center = combined * band * 0.5                       # central drift estimate
        low = center - band
        high = center + band

        # --- confidence ---------------------------------------------------
        agreement = abs(combined)                            # signals aligned?
        horizon_penalty = 1.0 / (1.0 + horizon / 10.0)
        confidence = min(0.9, agreement * horizon_penalty)

        direction = "up" if prob_up > 0.55 else "down" if prob_up < 0.45 else "sideways"
        notes = (f"Built from {len(signals)} strategies (net {net.direction.value}, "
                 f"slope {slope:+.4f}). Band scaled by ATR {atr_pct:.2f}%."
                 " Probabilistic estimate — not a guarantee.")
        return Forecast(symbol, horizon, direction, round(prob_up, 3),
                        round(center, 3), round(low, 3), round(high, 3),
                        round(confidence, 3), notes)
