"""
Multi-timeframe (MTF) analysis.

Analyzes the same symbol across several timeframes and combines signals into
an aligned bias. The principle: use the higher timeframe to establish
directional context (trend), and the lower timeframe for precise entry timing.

Alignment = all timeframes agree → high-conviction. Conflict → wait or reduce size.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

from .strategies import run_all, ensemble, Direction

if TYPE_CHECKING:
    from .market_data import MarketData

# Ordered from highest to lowest timeframe for display / weighting
DEFAULT_TIMEFRAMES = ["1w", "1d", "4h", "1h"]

_TF_WEIGHT = {
    "1w":  2.0,
    "1d":  1.5,
    "4h":  1.0,
    "1h":  0.7,
    "15m": 0.5,
    "5m":  0.3,
}


@dataclass
class MTFSignal:
    timeframe: str
    direction: str   # "long" | "short" | "flat"
    strength: float  # 0..1
    rationale: str


@dataclass
class MTFAnalysis:
    symbol: str
    timeframes: Dict[str, MTFSignal]
    alignment: str          # "aligned_long" | "aligned_short" | "mixed" | "conflicting"
    net_bias: str           # "long" | "short" | "flat"
    alignment_score: float  # -1..1  (positive = long, negative = short, near 0 = mixed)
    size_recommendation: float  # 0..1.5 multiplier vs base
    recommendations: List[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            f"=== MULTI-TIMEFRAME ANALYSIS: {self.symbol} ===",
            f"Net bias: {self.net_bias.upper()}  |  Alignment: {self.alignment}  "
            f"|  Score: {self.alignment_score:+.2f}",
            f"Size recommendation: {self.size_recommendation:.2f}× base",
            "",
            "Timeframe breakdown:",
        ]
        for tf, sig in self.timeframes.items():
            arrow = "↑" if sig.direction == "long" else "↓" if sig.direction == "short" else "→"
            lines.append(f"  {tf:>4s}  {arrow} {sig.direction.upper():<5s} "
                         f"({sig.strength:.0%}) — {sig.rationale}")
        if self.recommendations:
            lines.append("")
            lines.append("Recommendations:")
            for r in self.recommendations:
                lines.append(f"  • {r}")
        return "\n".join(lines)


class MultiTimeframeAnalyzer:
    """Fetches bars for multiple timeframes and runs the ensemble strategy on each."""

    def __init__(self, market_data: "MarketData"):
        self.md = market_data

    def analyze(self, symbol: str,
                timeframes: Optional[List[str]] = None,
                limit: int = 300) -> MTFAnalysis:
        tfs = timeframes or DEFAULT_TIMEFRAMES
        tf_signals: Dict[str, MTFSignal] = {}
        errors: List[str] = []

        for tf in tfs:
            try:
                data = self.md.get_ohlcv(symbol, tf, limit=limit)
                bars = data.as_bars()
                sigs = run_all(bars)
                net = ensemble(sigs)
                tf_signals[tf] = MTFSignal(
                    timeframe=tf,
                    direction=net.direction.value,
                    strength=net.strength,
                    rationale=net.rationale,
                )
            except Exception as e:  # noqa: BLE001
                errors.append(f"{tf}: {e}")
                tf_signals[tf] = MTFSignal(tf, "flat", 0.0, f"data unavailable ({e})")

        # Weighted net score
        total_weight = 0.0
        weighted_score = 0.0
        for tf, sig in tf_signals.items():
            w = _TF_WEIGHT.get(tf, 1.0)
            if sig.direction == "long":
                weighted_score += sig.strength * w
            elif sig.direction == "short":
                weighted_score -= sig.strength * w
            total_weight += w

        alignment_score = weighted_score / total_weight if total_weight > 0 else 0.0
        alignment_score = max(-1.0, min(1.0, alignment_score))

        longs = sum(1 for s in tf_signals.values() if s.direction == "long")
        shorts = sum(1 for s in tf_signals.values() if s.direction == "short")
        n = len(tf_signals)

        if longs == n:
            alignment = "aligned_long"
            net_bias = "long"
        elif shorts == n:
            alignment = "aligned_short"
            net_bias = "short"
        elif abs(alignment_score) > 0.4:
            alignment = "mixed"
            net_bias = "long" if alignment_score > 0 else "short"
        else:
            alignment = "conflicting"
            net_bias = "flat"

        # Size recommendation based on alignment
        size_map = {
            "aligned_long": 1.25,
            "aligned_short": 1.25,
            "mixed": 0.75,
            "conflicting": 0.25,
        }
        size_recommendation = size_map[alignment]

        recommendations: List[str] = []
        if alignment == "aligned_long":
            recommendations.append("All timeframes agree: look for a pullback entry on the LTF.")
        elif alignment == "aligned_short":
            recommendations.append("All timeframes agree short: look for a rally entry on the LTF.")
        elif alignment == "conflicting":
            recommendations.append("Timeframes conflict — stay flat or wait for HTF to resolve first.")
        else:
            ht = tfs[0] if tfs else "HTF"
            ht_sig = tf_signals.get(ht)
            if ht_sig:
                recommendations.append(
                    f"Higher timeframe ({ht}) says {ht_sig.direction.upper()} — "
                    "only trade in that direction on lower timeframes.")

        if errors:
            recommendations.append(f"Note: {len(errors)} timeframe(s) returned no data.")

        # Highest-conviction note
        strongest = max(tf_signals.values(), key=lambda s: s.strength)
        if strongest.strength > 0.7:
            recommendations.append(
                f"Strongest signal on {strongest.timeframe} ({strongest.direction}, "
                f"{strongest.strength:.0%}) — high conviction on that timeframe.")

        return MTFAnalysis(
            symbol=symbol,
            timeframes=tf_signals,
            alignment=alignment,
            net_bias=net_bias,
            alignment_score=round(alignment_score, 3),
            size_recommendation=size_recommendation,
            recommendations=recommendations,
        )
