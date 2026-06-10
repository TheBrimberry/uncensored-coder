"""
TradingAgent — the orchestrator.

Ties the deterministic analysis engine + knowledge base to the local LLM
(reusing the project's existing Ollama ModelLoader) to produce a grounded,
narrated trading read. Also exposes the lower-level building blocks (analyze,
forecast, trade plan, broker) so it can be used programmatically or from a CLI.

The LLM step is OPTIONAL: if Ollama isn't available the agent still returns the
full quantitative report, so it is always useful offline.
"""

from __future__ import annotations

from typing import Optional

from .analysis import AnalysisEngine, AnalysisReport
from .backtest import Backtester, BacktestResult
from .brokers import Broker, Order, OrderSide, OrderType, get_broker
from .forecast import Forecast
from .knowledge_base import KnowledgeBase
from .market_data import _looks_like_crypto
from .optimize import grid_search, walk_forward, GridResult, WalkForwardResult, DEFAULT_GRIDS
from .prompts import TRADING_SYSTEM_PROMPT, build_analysis_prompt
from .risk import TradePlan


class TradingAgent:
    """High-level entry point: 'analyze any symbol, reason about any move'."""

    def __init__(self, model: Optional[str] = None,
                 account_equity: float = 10_000.0, risk_pct: float = 1.0):
        self.engine = AnalysisEngine()
        self.kb = KnowledgeBase()
        self.account_equity = account_equity
        self.risk_pct = risk_pct
        self._model_name = model
        self._loader = None  # lazily initialized

    # -- LLM wiring (lazy, optional) --------------------------------------
    def _get_loader(self):
        if self._loader is not None:
            return self._loader
        try:
            from core.model_loader import ModelLoader  # reuse project's Ollama wrapper
            self._loader = ModelLoader(self._model_name)
        except Exception:
            self._loader = False  # sentinel: LLM unavailable
        return self._loader

    # -- core capabilities -------------------------------------------------
    def analyze(self, symbol: str, timeframe: str = "1d",
                horizon: int = 5) -> AnalysisReport:
        """Deterministic, computed analysis of a symbol (no LLM required)."""
        return self.engine.analyze(
            symbol, timeframe=timeframe, account_equity=self.account_equity,
            risk_pct=self.risk_pct, horizon=horizon,
        )

    def forecast(self, symbol: str, timeframe: str = "1d", horizon: int = 5) -> Forecast:
        return self.analyze(symbol, timeframe, horizon).forecast

    def trade_plan(self, symbol: str, timeframe: str = "1d") -> Optional[TradePlan]:
        return self.analyze(symbol, timeframe).trade_plan

    def backtest(self, symbol: str, strategy: str = "ensemble", timeframe: str = "1d",
                 limit: int = 500, **kwargs) -> BacktestResult:
        """Validate a strategy on historical bars before risking capital."""
        data = self.engine.md.get_ohlcv(symbol, timeframe, limit=limit)
        bt = Backtester(starting_equity=self.account_equity, risk_pct=self.risk_pct,
                        warmup=min(200, max(50, len(data) // 3)), **kwargs)
        return bt.run(data.as_bars(), strategy=strategy, symbol=symbol)

    def optimize(self, symbol: str, strategy: str = "ma_crossover",
                 timeframe: str = "1d", limit: int = 600, metric: str = "calmar",
                 param_grid: Optional[dict] = None) -> "GridResult":
        """Grid-search a strategy's parameters on historical bars."""
        data = self.engine.md.get_ohlcv(symbol, timeframe, limit=limit)
        grid = param_grid if param_grid is not None else DEFAULT_GRIDS.get(strategy, {})
        return grid_search(data.as_bars(), strategy, grid, metric=metric, symbol=symbol)

    def walk_forward(self, symbol: str, strategy: str = "ma_crossover",
                     timeframe: str = "1d", limit: int = 800, n_folds: int = 4,
                     metric: str = "calmar",
                     param_grid: Optional[dict] = None) -> "WalkForwardResult":
        """Out-of-sample walk-forward validation — the honest robustness check."""
        data = self.engine.md.get_ohlcv(symbol, timeframe, limit=limit)
        grid = param_grid if param_grid is not None else DEFAULT_GRIDS.get(strategy, {})
        return walk_forward(data.as_bars(), strategy, grid, n_folds=n_folds,
                            metric=metric, symbol=symbol)

    def ask(self, symbol: str, question: Optional[str] = None,
            timeframe: str = "1d", horizon: int = 5) -> str:
        """Full pipeline: compute the report, then have the LLM reason over it."""
        report = self.analyze(symbol, timeframe, horizon)
        asset_class = "crypto" if _looks_like_crypto(symbol) else "stocks"
        kb_context = self.kb.as_prompt_context(asset_class)
        prompt = build_analysis_prompt(report.to_text(), kb_context, question)

        loader = self._get_loader()
        if not loader:
            return (report.to_text() +
                    "\n\n[LLM narration unavailable — Ollama not running. "
                    "Showing computed analysis only.]")
        try:
            return loader.generate(prompt, system_prompt=TRADING_SYSTEM_PROMPT)
        except Exception as e:  # noqa: BLE001
            return report.to_text() + f"\n\n[LLM error: {e}. Computed analysis above.]"

    # -- execution (paper by default) -------------------------------------
    def execute_plan(self, plan: TradePlan, broker: str = "paper",
                     live: bool = False, credentials: Optional[dict] = None) -> str:
        """Turn a TradePlan into an order. PAPER unless live=True + creds given."""
        if plan is None:
            return "No actionable trade plan (ensemble was flat)."
        bkr: Broker = get_broker(broker, live=live, credentials=credentials)
        bkr.connect()
        order = Order(
            symbol=plan.symbol,
            side=OrderSide.BUY if plan.direction == "long" else OrderSide.SELL,
            qty=round(plan.position_size, 6),
            order_type=OrderType.MARKET,
            price=plan.entry,
            stop_loss=plan.stop,
            take_profit=plan.take_profit,
        )
        result = bkr.place_order(order)
        mode = "LIVE" if (live and not result.simulated) else "PAPER"
        return f"[{mode}] {result.message} (broker={result.broker})"

    # -- knowledge ---------------------------------------------------------
    def knowledge(self, asset_class: Optional[str] = None) -> str:
        return self.kb.as_prompt_context(asset_class)
