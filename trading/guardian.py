"""
Account guardian — the "don't blow up the account" layer.

A hard risk firewall that sits in front of every order. It refuses trades that
would breach your rules, enforces that every position carries a stop-loss, and
trips a circuit breaker when losses pile up (per-trade, daily, or total
drawdown). Survival first: when in doubt, it blocks.

Wrap any broker with `GuardedBroker` (or call `RiskGuardian.check()` directly).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Tuple

from .brokers import Broker, Order, OrderResult, OrderSide
from .risk import build_trade_plan


@dataclass
class RiskLimits:
    max_risk_pct_per_trade: float = 2.0       # reject oversized single-trade risk
    max_daily_loss_pct: float = 5.0           # halt trading after this daily loss
    max_total_drawdown_pct: float = 20.0      # kill switch from equity peak
    max_open_positions: int = 10              # cap concurrent exposure
    require_stop_loss: bool = True            # every order must define a stop
    max_position_pct: float = 25.0            # single position notional cap


@dataclass
class GuardianState:
    starting_equity: float
    equity: float
    peak_equity: float
    day: date
    realized_today: float = 0.0
    open_positions: int = 0
    halted: bool = False
    halt_reason: str = ""


@dataclass
class RiskDecision:
    allowed: bool
    reasons: List[str] = field(default_factory=list)
    adjustments: List[str] = field(default_factory=list)

    def explain(self) -> str:
        verdict = "ALLOWED" if self.allowed else "BLOCKED"
        out = [f"Risk check: {verdict}"]
        out += [f"  ✗ {r}" for r in self.reasons]
        out += [f"  ~ {a}" for a in self.adjustments]
        return "\n".join(out)


class RiskGuardian:
    """Stateful pre-trade risk checks + circuit breaker."""

    def __init__(self, starting_equity: float = 10_000.0,
                 limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
        self.state = GuardianState(
            starting_equity=starting_equity, equity=starting_equity,
            peak_equity=starting_equity, day=date.today(),
        )

    # -- equity / pnl tracking --------------------------------------------
    def record_fill(self, realized_pnl: float) -> None:
        """Feed realized P&L back so the circuit breaker can react live."""
        self._roll_day()
        self.state.equity += realized_pnl
        self.state.realized_today += realized_pnl
        self.state.peak_equity = max(self.state.peak_equity, self.state.equity)
        self._evaluate_circuit_breaker()

    def _roll_day(self) -> None:
        if date.today() != self.state.day:
            self.state.day = date.today()
            self.state.realized_today = 0.0
            if self.state.halted and "daily" in self.state.halt_reason:
                self.state.halted = False        # new day clears daily halt
                self.state.halt_reason = ""

    def _evaluate_circuit_breaker(self) -> None:
        s, lim = self.state, self.limits
        daily_loss_pct = -s.realized_today / s.starting_equity * 100
        if daily_loss_pct >= lim.max_daily_loss_pct:
            s.halted, s.halt_reason = True, (
                f"daily loss {daily_loss_pct:.1f}% ≥ {lim.max_daily_loss_pct}% limit")
        dd_pct = (s.peak_equity - s.equity) / s.peak_equity * 100 if s.peak_equity else 0
        if dd_pct >= lim.max_total_drawdown_pct:
            s.halted, s.halt_reason = True, (
                f"drawdown {dd_pct:.1f}% ≥ {lim.max_total_drawdown_pct}% kill-switch")

    # -- pre-trade checks --------------------------------------------------
    def check(self, order: Order) -> RiskDecision:
        self._roll_day()
        self._evaluate_circuit_breaker()
        reasons: List[str] = []

        if self.state.halted:
            return RiskDecision(False, [f"Trading halted: {self.state.halt_reason}"])

        if self.limits.require_stop_loss and order.stop_loss is None:
            reasons.append("No stop-loss attached (required by guardian).")

        if order.stop_loss is not None and order.price:
            risk_per_unit = abs(order.price - order.stop_loss)
            trade_risk = risk_per_unit * order.qty
            risk_pct = trade_risk / self.state.equity * 100
            if risk_pct > self.limits.max_risk_pct_per_trade:
                reasons.append(
                    f"Trade risks {risk_pct:.1f}% > {self.limits.max_risk_pct_per_trade}% "
                    "per-trade cap.")
            notional_pct = (order.price * order.qty) / self.state.equity * 100
            if notional_pct > self.limits.max_position_pct:
                reasons.append(
                    f"Position notional {notional_pct:.0f}% > "
                    f"{self.limits.max_position_pct}% cap.")
            # stop on the wrong side?
            if order.side == OrderSide.BUY and order.stop_loss >= order.price:
                reasons.append("Long stop-loss is at/above entry.")
            if order.side == OrderSide.SELL and order.stop_loss <= order.price:
                reasons.append("Short stop-loss is at/below entry.")

        if self.state.open_positions >= self.limits.max_open_positions:
            reasons.append(
                f"Already at max {self.limits.max_open_positions} open positions.")

        return RiskDecision(allowed=not reasons, reasons=reasons)

    def status(self) -> str:
        s, lim = self.state, self.limits
        dd = (s.peak_equity - s.equity) / s.peak_equity * 100 if s.peak_equity else 0
        flag = f"HALTED — {s.halt_reason}" if s.halted else "OK"
        return (f"Guardian [{flag}] equity {s.equity:.2f} (peak {s.peak_equity:.2f}, "
                f"dd {dd:.1f}%/{lim.max_total_drawdown_pct}%), "
                f"today {s.realized_today:+.2f} "
                f"({-s.realized_today / s.starting_equity * 100:.1f}%/"
                f"{lim.max_daily_loss_pct}% loss limit), "
                f"open {s.open_positions}/{lim.max_open_positions}")


def attach_sl_tp(order: Order, atr_value: float, direction: str,
                 atr_stop_mult: float = 2.0, rr: float = 2.0) -> Order:
    """Ensure an order has a sensible ATR-based stop-loss and take-profit."""
    if order.price and atr_value > 0:
        plan = build_trade_plan(order.symbol, direction, order.price, atr_value,
                                atr_stop_mult=atr_stop_mult, rr=rr)
        if plan:
            if order.stop_loss is None:
                order.stop_loss = round(plan.stop, 6)
            if order.take_profit is None:
                order.take_profit = round(plan.take_profit, 6)
    return order


class GuardedBroker:
    """Decorator that runs every order through the guardian before the broker."""

    def __init__(self, broker: Broker, guardian: RiskGuardian):
        self.broker = broker
        self.guardian = guardian

    def connect(self) -> bool:
        return self.broker.connect()

    def place_order(self, order: Order) -> Tuple[RiskDecision, Optional[OrderResult]]:
        decision = self.guardian.check(order)
        if not decision.allowed:
            return decision, None
        result = self.broker.place_order(order)
        if result.accepted:
            self.guardian.state.open_positions += 1
        return decision, result

    def status(self) -> str:
        return self.guardian.status()
