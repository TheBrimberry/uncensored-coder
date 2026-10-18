"""
Parameter optimization & walk-forward validation.

Two tools that sit on top of the backtester:

* `grid_search` — exhaustively scores a parameter grid for a strategy on one
  dataset and returns the ranked table + best params for a chosen metric.

* `walk_forward` — the honest version: it rolls a train/test window across the
  series, re-optimizing on each *in-sample* slice and recording performance on
  the following *out-of-sample* slice. Out-of-sample aggregates are what you
  should trust; in-sample-only optimization is how backtests lie.

Strategies are the parameterized functions in `strategies.py`; a param grid is a
dict of `{param_name: [values...]}`.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from . import strategies as strat
from .backtest import Backtester, BacktestResult

Bars = Dict[str, List[float]]
Params = Dict[str, object]

# Metric extractors: higher is better.
METRICS: Dict[str, Callable[[BacktestResult], float]] = {
    "profit_factor": lambda r: r.profit_factor if r.profit_factor != float("inf") else 1e6,
    "total_return": lambda r: r.total_return_pct,
    "sharpe": lambda r: r.sharpe,
    "win_rate": lambda r: r.win_rate,
    # return penalized by drawdown — a sane default objective
    "calmar": lambda r: (r.total_return_pct / r.max_drawdown_pct) if r.max_drawdown_pct > 0 else r.total_return_pct,
}


@dataclass
class GridResult:
    strategy: str
    metric: str
    best_params: Params
    best_score: float
    table: List[Tuple[Params, float, int]] = field(default_factory=list)  # (params, score, n_trades)

    def summary(self, top: int = 5) -> str:
        lines = [f"=== GRID SEARCH: {self.strategy} (metric={self.metric}) ===",
                 f"Best: {self.best_params} -> {self.best_score:.3f}", "Top results:"]
        for params, score, n in self.table[:top]:
            lines.append(f"  {score:8.3f} | trades={n:3d} | {params}")
        return "\n".join(lines)


@dataclass
class WalkForwardResult:
    strategy: str
    metric: str
    n_folds: int
    oos_mean_return: float
    oos_mean_score: float
    oos_total_return: float
    fold_params: List[Params]
    fold_scores: List[float]
    robust: bool          # positive OOS on a majority of folds?

    def summary(self) -> str:
        verdict = "ROBUST (generalizes out-of-sample)" if self.robust else \
                  "FRAGILE (likely overfit — OOS does not hold up)"
        lines = [f"=== WALK-FORWARD: {self.strategy} (metric={self.metric}) ===",
                 f"Folds: {self.n_folds} | Verdict: {verdict}",
                 f"OOS mean return/fold: {self.oos_mean_return:+.2f}% | "
                 f"OOS compounded: {self.oos_total_return:+.2f}%",
                 f"OOS mean {self.metric}: {self.oos_mean_score:.3f}",
                 "Per-fold chosen params:"]
        for i, (p, s) in enumerate(zip(self.fold_params, self.fold_scores)):
            lines.append(f"  fold {i+1}: {p} -> {self.metric}={s:.3f}")
        return "\n".join(lines)


def _bind(strategy_name: str, params: Params) -> Callable[[Bars], "strat.Signal"]:
    """Return a no-arg-over-bars strategy callable with params baked in."""
    if strategy_name == "ensemble":
        # ensemble has no tunable params here; ignore the grid.
        return lambda w: strat.ensemble(strat.run_all(w))
    fn = strat.STRATEGIES[strategy_name]
    return lambda w, _p=params: fn(w, **_p)


def _expand_grid(param_grid: Dict[str, List]) -> List[Params]:
    if not param_grid:
        return [{}]
    keys = list(param_grid.keys())
    return [dict(zip(keys, combo)) for combo in itertools.product(*param_grid.values())]


def _slice(bars: Bars, a: int, b: int) -> Bars:
    return {k: v[a:b] for k, v in bars.items()}


def grid_search(bars: Bars, strategy_name: str, param_grid: Dict[str, List],
                metric: str = "calmar", symbol: str = "?",
                min_trades: int = 3, **backtester_kwargs) -> GridResult:
    """Exhaustively score every parameter combination on `bars`."""
    if metric not in METRICS:
        raise ValueError(f"Unknown metric '{metric}'. Choose from {list(METRICS)}")
    score_of = METRICS[metric]
    warmup = backtester_kwargs.pop("warmup", min(150, max(30, len(bars["close"]) // 4)))

    table: List[Tuple[Params, float, int]] = []
    for params in _expand_grid(param_grid):
        bt = Backtester(warmup=warmup, **backtester_kwargs)
        result = bt.run(bars, strategy=_bind(strategy_name, params), symbol=symbol)
        # discourage params that barely trade (overfit to a handful of bars)
        score = score_of(result) if result.n_trades >= min_trades else -1e6
        table.append((params, score, result.n_trades))

    table.sort(key=lambda x: x[1], reverse=True)
    best_params, best_score, _ = table[0]
    return GridResult(strategy_name, metric, best_params, best_score, table)


def walk_forward(bars: Bars, strategy_name: str, param_grid: Dict[str, List],
                 n_folds: int = 4, train_frac: float = 0.4, metric: str = "calmar",
                 symbol: str = "?", **backtester_kwargs) -> WalkForwardResult:
    """Anchored walk-forward: reserve an initial training span, then partition the
    remainder into out-of-sample test segments. Each fold re-optimizes on all data
    *before* its test window and evaluates on the test window only — with full
    history preserved so slow indicators can warm up (no degenerate zero-trade
    folds). Out-of-sample aggregates are the honest robustness signal.
    """
    if metric not in METRICS:
        raise ValueError(f"Unknown metric '{metric}'. Choose from {list(METRICS)}")
    score_of = METRICS[metric]
    n = len(bars["close"])

    train_min = max(int(n * train_frac), 60)
    remaining = n - train_min
    if remaining < 60:                       # too little data for OOS testing
        return WalkForwardResult(strategy_name, metric, 0, 0.0, 0.0, 0.0, [], [], False)
    test_size = max(remaining // n_folds, 30)

    fold_params: List[Params] = []
    fold_scores: List[float] = []
    oos_returns: List[float] = []
    compounded = 1.0

    for f in range(n_folds):
        test_start = train_min + f * test_size
        test_end = n if f == n_folds - 1 else test_start + test_size
        if test_start >= n or test_end - test_start < 20:
            break

        # Optimize on everything before the test window (anchored/expanding).
        train = _slice(bars, 0, test_start)
        grid = grid_search(train, strategy_name, param_grid, metric=metric,
                           symbol=symbol, **backtester_kwargs)

        # Evaluate OOS on full history up to test_end, trading only from test_start.
        oos_data = _slice(bars, 0, test_end)
        bt = Backtester(**backtester_kwargs)
        oos = bt.run(oos_data, strategy=_bind(strategy_name, grid.best_params),
                     symbol=symbol, start=test_start)

        fold_params.append(grid.best_params)
        fold_scores.append(score_of(oos))
        oos_returns.append(oos.total_return_pct)
        compounded *= (1 + oos.total_return_pct / 100.0)

    folds_done = len(oos_returns)
    if folds_done == 0:
        return WalkForwardResult(strategy_name, metric, 0, 0.0, 0.0, 0.0, [], [], False)

    mean_ret = sum(oos_returns) / folds_done
    mean_score = sum(fold_scores) / folds_done
    positive = sum(1 for r in oos_returns if r > 0)
    robust = positive > folds_done / 2 and mean_ret > 0
    return WalkForwardResult(
        strategy_name, metric, folds_done, mean_ret, mean_score,
        (compounded - 1) * 100, fold_params, fold_scores, robust,
    )


# Sensible default search spaces per strategy (used by the CLI/agent).
DEFAULT_GRIDS: Dict[str, Dict[str, List]] = {
    "ma_crossover": {"fast": [10, 20, 50], "slow": [100, 150, 200]},
    "rsi_reversion": {"period": [7, 14, 21], "low": [20, 30], "high": [70, 80]},
    "bollinger_breakout": {"period": [14, 20, 30], "num_std": [1.5, 2.0, 2.5]},
    "macd_momentum": {},
    "supertrend_follow": {"period": [7, 10, 14], "multiplier": [2.0, 3.0, 4.0]},
    "ensemble": {},
    "donchian_breakout": {"period": [10, 20, 40, 55]},
    "stochastic_cross": {"k_period": [9, 14, 21], "d_period": [3, 5]},
    "mean_reversion_zscore": {"period": [10, 20, 30], "threshold": [1.5, 2.0, 2.5]},
    "cci_reversal": {"period": [14, 20], "threshold": [100.0, 150.0]},
    "volume_momentum": {},
    "keltner_breakout": {"ema_period": [14, 20], "atr_period": [7, 10], "multiplier": [1.5, 2.0, 2.5]},
    "adx_trend_strength": {"period": [10, 14], "threshold": [20.0, 25.0, 30.0]},
}
