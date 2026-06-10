"""
Backtesting harness.

A lightweight, dependency-free event-driven backtester so the agent can validate
a strategy on historical bars before risking capital. Inspired by backtrader /
backtesting.py but kept minimal and transparent.

It walks bars chronologically, asks a strategy for a signal on each bar using
*only* data up to that point (no lookahead), manages a single position with
ATR-based stops/targets, and reports the standard performance metrics
(return, win rate, profit factor, max drawdown, Sharpe).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from . import indicators as ind
from . import strategies as strat


@dataclass
class Trade:
    direction: str
    entry_index: int
    entry_price: float
    stop_frac: float = 0.0          # |entry-stop|/entry, used to convert % move -> R
    exit_index: Optional[int] = None
    exit_price: Optional[float] = None
    pnl_pct: float = 0.0
    r_multiple: float = 0.0
    reason: str = ""


@dataclass
class BacktestResult:
    symbol: str
    strategy: str
    n_trades: int
    win_rate: float
    total_return_pct: float
    avg_trade_pct: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe: float
    final_equity: float
    trades: List[Trade] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"=== BACKTEST: {self.symbol} | {self.strategy} ===\n"
            f"Trades: {self.n_trades} | Win rate: {self.win_rate:.1%} | "
            f"Profit factor: {self.profit_factor:.2f}\n"
            f"Total return: {self.total_return_pct:+.2f}% | "
            f"Avg trade: {self.avg_trade_pct:+.2f}% | "
            f"Max DD: {self.max_drawdown_pct:.2f}%\n"
            f"Sharpe: {self.sharpe:.2f} | Final equity: {self.final_equity:.2f}"
        )


# A strategy here maps a *window* of bars to a Signal (same shape as strategies.py).
StrategyFn = Callable[[Dict[str, List[float]]], "strat.Signal"]


class Backtester:
    def __init__(self, starting_equity: float = 10_000.0, risk_pct: float = 1.0,
                 atr_period: int = 14, atr_stop_mult: float = 2.0, rr: float = 2.0,
                 fee_pct: float = 0.05, warmup: int = 200):
        self.starting_equity = starting_equity
        self.risk_pct = risk_pct
        self.atr_period = atr_period
        self.atr_stop_mult = atr_stop_mult
        self.rr = rr
        self.fee_pct = fee_pct          # round-trip fee+slippage as % of notional
        self.warmup = warmup

    def run(self, bars: Dict[str, List[float]], strategy: StrategyFn | str = "ensemble",
            symbol: str = "?") -> BacktestResult:
        strat_fn, strat_name = self._resolve_strategy(strategy)
        close = bars["close"]
        high, low = bars["high"], bars["low"]
        n = len(close)
        atr_series = ind.atr(high, low, close, self.atr_period)

        equity = self.starting_equity
        equity_curve: List[float] = [equity]
        trades: List[Trade] = []
        open_trade: Optional[Trade] = None
        stop = target = 0.0

        start = max(self.warmup, self.atr_period + 2)
        for i in range(start, n):
            price = close[i]

            # --- manage an open position (check stop/target on this bar) ---
            if open_trade is not None:
                hit_stop = (low[i] <= stop) if open_trade.direction == "long" else (high[i] >= stop)
                hit_tp = (high[i] >= target) if open_trade.direction == "long" else (low[i] <= target)
                exit_price = None
                reason = ""
                if hit_stop:
                    exit_price, reason = stop, "stop"
                elif hit_tp:
                    exit_price, reason = target, "target"
                if exit_price is not None:
                    equity = self._close_trade(open_trade, i, exit_price, reason, equity, trades)
                    open_trade = None

            # --- look for a new entry (window has no lookahead) ------------
            if open_trade is None:
                window = {k: v[: i + 1] for k, v in bars.items()}
                sig = strat_fn(window)
                atr_val = atr_series[i]
                if sig.direction != strat.Direction.FLAT and atr_val:
                    direction = sig.direction.value
                    stop_dist = self.atr_stop_mult * atr_val
                    if direction == "long":
                        stop, target = price - stop_dist, price + stop_dist * self.rr
                    else:
                        stop, target = price + stop_dist, price - stop_dist * self.rr
                    open_trade = Trade(direction, i, price,
                                       stop_frac=stop_dist / price if price else 0.0)

            equity_curve.append(equity if open_trade is None else equity)

        # close any dangling position at the last price
        if open_trade is not None:
            equity = self._close_trade(open_trade, n - 1, close[-1], "eod", equity, trades)

        return self._metrics(symbol, strat_name, trades, equity, equity_curve)

    # -- helpers -----------------------------------------------------------
    def _resolve_strategy(self, strategy):
        if callable(strategy):
            return strategy, getattr(strategy, "__name__", "custom")
        if strategy == "ensemble":
            return (lambda w: strat.ensemble(strat.run_all(w))), "ensemble"
        if strategy in strat.STRATEGIES:
            return strat.STRATEGIES[strategy], strategy
        raise ValueError(f"Unknown strategy: {strategy}")

    def _close_trade(self, trade: Trade, i: int, exit_price: float, reason: str,
                     equity: float, trades: List[Trade]) -> float:
        # Raw directional return, then net of round-trip costs.
        if trade.direction == "long":
            gross = (exit_price - trade.entry_price) / trade.entry_price
        else:
            gross = (trade.entry_price - exit_price) / trade.entry_price
        net = gross - self.fee_pct / 100.0

        # Convert the % move into R multiples (move / stop distance), then apply
        # the fixed fractional risk budget: P&L = risk_amount * R.
        stop_frac = max(trade.stop_frac, 1e-9)
        r_multiple = net / stop_frac
        equity += equity * (self.risk_pct / 100.0) * r_multiple

        trade.exit_index = i
        trade.exit_price = exit_price
        trade.pnl_pct = net * 100.0
        trade.r_multiple = r_multiple
        trade.reason = reason
        trades.append(trade)
        return equity

    def _metrics(self, symbol, strat_name, trades: List[Trade], equity, curve):
        n = len(trades)
        if n == 0:
            return BacktestResult(symbol, strat_name, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                  equity, trades)
        wins = [t for t in trades if t.pnl_pct > 0]
        losses = [t for t in trades if t.pnl_pct <= 0]
        gross_win = sum(t.pnl_pct for t in wins)
        gross_loss = abs(sum(t.pnl_pct for t in losses))
        profit_factor = gross_win / gross_loss if gross_loss else float("inf")
        total_return = (equity - self.starting_equity) / self.starting_equity * 100
        avg_trade = sum(t.pnl_pct for t in trades) / n

        # max drawdown on equity curve
        peak = curve[0]
        max_dd = 0.0
        for v in curve:
            peak = max(peak, v)
            dd = (peak - v) / peak * 100 if peak else 0.0
            max_dd = max(max_dd, dd)

        # Sharpe on per-trade returns (annualization-agnostic, unitless)
        rets = [t.pnl_pct for t in trades]
        mean = sum(rets) / n
        var = sum((r - mean) ** 2 for r in rets) / n
        std = math.sqrt(var)
        sharpe = (mean / std * math.sqrt(n)) if std else 0.0

        return BacktestResult(
            symbol, strat_name, n, len(wins) / n, total_return, avg_trade,
            profit_factor, max_dd, sharpe, equity, trades,
        )
