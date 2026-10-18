"""
Risk management & position sizing.

Survival-first sizing the agent applies to every trade idea. Sizes come from the
*stop distance* and account risk budget, normalized by volatility (ATR), never
from gut feel. Mirrors the discipline in pysystemtrade / freqtrade risk modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TradePlan:
    symbol: str
    direction: str
    entry: float
    stop: float
    take_profit: float
    position_size: float
    risk_amount: float
    risk_reward: float

    def summary(self) -> str:
        return (
            f"{self.direction.upper()} {self.symbol} @ {self.entry:.4f} | "
            f"stop {self.stop:.4f} | target {self.take_profit:.4f} | "
            f"size {self.position_size:.4f} units | risk {self.risk_amount:.2f} "
            f"| R:R {self.risk_reward:.2f}"
        )


def position_size(account_equity: float, risk_pct: float,
                  entry: float, stop: float) -> float:
    """Units to trade so that hitting the stop loses exactly risk_pct of equity."""
    risk_amount = account_equity * (risk_pct / 100.0)
    per_unit_risk = abs(entry - stop)
    if per_unit_risk <= 0:
        return 0.0
    return risk_amount / per_unit_risk


def build_trade_plan(symbol: str, direction: str, entry: float, atr_value: float,
                     account_equity: float = 10_000.0, risk_pct: float = 1.0,
                     atr_stop_mult: float = 2.0, rr: float = 2.0) -> Optional[TradePlan]:
    """Construct a full, ATR-normalized trade plan with sane stops/targets."""
    if entry <= 0 or atr_value <= 0 or direction not in ("long", "short"):
        return None
    stop_dist = atr_stop_mult * atr_value
    if direction == "long":
        stop = entry - stop_dist
        target = entry + stop_dist * rr
    else:
        stop = entry + stop_dist
        target = entry - stop_dist * rr
    size = position_size(account_equity, risk_pct, entry, stop)
    risk_amount = account_equity * (risk_pct / 100.0)
    return TradePlan(symbol, direction, entry, stop, target, size, risk_amount, rr)
