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
from .autotune import AutoTuner, TuneProposal, CodeProposal
from .backtest import Backtester, BacktestResult
from .bot import BotConfig
from .brokers import Broker, Order, OrderSide, OrderType, get_broker
from .forecast import Forecast
from .guardian import RiskGuardian, RiskLimits, GuardedBroker, attach_sl_tp
from .journal import TradeJournal, PerformanceReport
from .knowledge_base import KnowledgeBase
from .knowledge_corpus import KnowledgeCorpus
from .market_data import _looks_like_crypto
from .mtf import MultiTimeframeAnalyzer, MTFAnalysis
from .optimize import grid_search, walk_forward, GridResult, WalkForwardResult, DEFAULT_GRIDS
from .patterns import analyze_patterns, MarketInsights
from .prompts import TRADING_SYSTEM_PROMPT, build_analysis_prompt
from .regime import detect_regime, RegimeResult
from .risk import TradePlan


class TradingAgent:
    """High-level entry point: 'analyze any symbol, reason about any move'."""

    def __init__(self, model: Optional[str] = None,
                 account_equity: float = 10_000.0, risk_pct: float = 1.0,
                 risk_limits: Optional[RiskLimits] = None,
                 corpus_path: Optional[str] = None,
                 real_data_only: bool = False):
        self.engine = AnalysisEngine()
        if real_data_only:
            self.engine.md.strict = True
        self.kb = KnowledgeBase()
        self.corpus = KnowledgeCorpus()
        if corpus_path:
            self.corpus.load(corpus_path)
        self.account_equity = account_equity
        self.risk_pct = risk_pct
        self.guardian = RiskGuardian(account_equity, risk_limits)
        self.tuner = AutoTuner(market_data=self.engine.md)
        self.mtf_analyzer = MultiTimeframeAnalyzer(self.engine.md)
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

    def insights(self, symbol: str, timeframe: str = "1d") -> MarketInsights:
        """Side-by-side co-pilot: highlight patterns, levels and key insights."""
        data = self.engine.md.get_ohlcv(symbol, timeframe)
        return analyze_patterns(symbol, data.as_bars())

    def regime(self, symbol: str, timeframe: str = "1d") -> RegimeResult:
        """Classify the current market regime (trending/ranging/high-vol) and
        return a recommended position-size multiplier."""
        data = self.engine.md.get_ohlcv(symbol, timeframe)
        return detect_regime(symbol, data.as_bars())

    def mtf(self, symbol: str, timeframes=None, limit: int = 300) -> MTFAnalysis:
        """Multi-timeframe analysis: run ensemble strategy across timeframes and
        report alignment. Fully aligned = high conviction; conflicting = wait."""
        return self.mtf_analyzer.analyze(symbol, timeframes=timeframes, limit=limit)

    def ask(self, symbol: str, question: Optional[str] = None,
            timeframe: str = "1d", horizon: int = 5) -> str:
        """Full pipeline: compute the report + patterns, ground it in the deep
        knowledge corpus, then have the LLM reason over all of it."""
        report = self.analyze(symbol, timeframe, horizon)
        insights = self.insights(symbol, timeframe)
        asset_class = "crypto" if _looks_like_crypto(symbol) else "stocks"

        # Retrieve the most relevant deep-knowledge passages for this situation.
        query = " ".join(filter(None, [question, asset_class, insights.regime,
                                       " ".join(p.name for p in insights.patterns)]))
        corpus_context = self.corpus.as_prompt_context(query or symbol, k=4)
        kb_context = self.kb.as_prompt_context(asset_class)
        if corpus_context:
            kb_context = corpus_context + "\n\n" + kb_context

        grounded = report.to_text() + "\n\n" + insights.to_text()
        prompt = build_analysis_prompt(grounded, kb_context, question)

        loader = self._get_loader()
        if not loader:
            return (grounded +
                    "\n\n[LLM narration unavailable — Ollama not running. "
                    "Showing computed analysis + co-pilot insights only.]")
        try:
            return loader.generate(prompt, system_prompt=TRADING_SYSTEM_PROMPT)
        except Exception as e:  # noqa: BLE001
            return grounded + f"\n\n[LLM error: {e}. Computed analysis above.]"

    # -- execution (paper by default, risk-firewalled) --------------------
    def execute_plan(self, plan: TradePlan, broker: str = "paper",
                     live: bool = False, credentials: Optional[dict] = None) -> str:
        """Turn a TradePlan into an order, run it through the risk guardian
        (SL required, size/loss/drawdown limits), then PAPER unless live=True."""
        if plan is None:
            return "No actionable trade plan (ensemble was flat)."
        order = Order(
            symbol=plan.symbol,
            side=OrderSide.BUY if plan.direction == "long" else OrderSide.SELL,
            qty=round(plan.position_size, 6),
            order_type=OrderType.MARKET,
            price=plan.entry,
            stop_loss=plan.stop,
            take_profit=plan.take_profit,
        )
        bkr: Broker = get_broker(broker, live=live, credentials=credentials)
        guarded = GuardedBroker(bkr, self.guardian)
        guarded.connect()
        decision, result = guarded.place_order(order)
        if not decision.allowed:
            return ("ORDER BLOCKED BY GUARDIAN — protecting your account:\n"
                    + decision.explain())
        mode = "LIVE" if (live and result and not result.simulated) else "PAPER"
        return f"[{mode}] {result.message} (broker={result.broker})\n{self.guardian.status()}"

    def guardian_status(self) -> str:
        return self.guardian.status()

    # -- performance review (your past trading data) ----------------------
    def review_performance(self, source) -> PerformanceReport:
        """Analyze past trades. `source` may be a CSV path, JSON path, a list of
        TradeRecord, or a BacktestResult."""
        if isinstance(source, str):
            journal = (TradeJournal.from_csv(source) if source.lower().endswith(".csv")
                       else TradeJournal.from_json(source))
        elif isinstance(source, list):
            journal = TradeJournal.from_records(source)
        elif hasattr(source, "trades"):
            journal = TradeJournal.from_backtest(source)
        else:
            raise TypeError("Unsupported performance source.")
        return journal.analyze()

    # -- bot improvement: parameters AND code -----------------------------
    def tune_bot(self, bot: BotConfig, metric: str = "calmar",
                 apply: bool = False, path: Optional[str] = None) -> TuneProposal:
        """Re-optimize a bot's parameters with walk-forward guardrails; apply only
        robust, improving changes when apply=True."""
        proposal = self.tuner.propose_params(bot, metric=metric)
        if apply:
            self.tuner.apply_params(bot, proposal, path=path)
        return proposal

    def improve_bot_code(self, bot: BotConfig, performance_source=None,
                         apply: bool = False) -> CodeProposal:
        """LLM-propose edits to the bot's strategy source file (dry-run by default;
        original backed up when apply=True)."""
        perf_text = ""
        if performance_source is not None:
            try:
                perf_text = self.review_performance(performance_source).to_text()
            except Exception:  # noqa: BLE001
                perf_text = ""
        return self.tuner.improve_code(bot, performance_text=perf_text,
                                       loader=self._get_loader(), apply=apply)

    def monitor_bots(self, bots, path_for: Optional[dict] = None,
                     metric: str = "calmar", apply: bool = False) -> str:
        """Live tuning sweep — call on a schedule to keep bots optimized."""
        return self.tuner.monitor(bots, path_for=path_for, metric=metric, apply=apply)

    # -- knowledge ---------------------------------------------------------
    def knowledge(self, asset_class: Optional[str] = None) -> str:
        return self.kb.as_prompt_context(asset_class)

    def learn(self, query: str, k: int = 5) -> str:
        """Retrieve deep knowledge (built-in + ingested) for a question/topic."""
        return self.corpus.as_prompt_context(query, k=k) or "No matching knowledge."

    def ingest_knowledge(self, *, text: Optional[str] = None, file: Optional[str] = None,
                         directory: Optional[str] = None, url: Optional[str] = None,
                         title: str = "note", tags: Optional[list] = None,
                         save_path: Optional[str] = None) -> str:
        """Teach the agent: ingest your own notes / files / a folder / a URL."""
        added = 0
        if text:
            added += self.corpus.ingest_text(text, title=title, tags=tags)
        if file:
            added += self.corpus.ingest_file(file, tags=tags)
        if directory:
            added += self.corpus.ingest_directory(directory, tags=tags)
        if url:
            added += self.corpus.ingest_url(url, fetcher=self._fetch_url, tags=tags)
        if save_path:
            self.corpus.save(save_path)
        return f"Ingested {added} chunk(s). {self.corpus.stats()}"

    def _fetch_url(self, url: str) -> str:
        """Fetch URL text via the project's model loader / WebFetch, or urllib."""
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "TradingAgent/2.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read().decode("utf-8", errors="ignore")
            # Strip HTML tags crudely
            import re
            raw = re.sub(r"<[^>]+>", " ", raw)
            raw = re.sub(r"\s{2,}", " ", raw)
            return raw[:50_000]
        except Exception as e:
            return f"[fetch error: {e}]"

    def monitor_bots_daemon(self, bots, path_for: Optional[dict] = None,
                            metric: str = "calmar", apply: bool = False,
                            interval_minutes: float = 60.0) -> None:
        """Run the bot-tuning sweep once immediately, then on a schedule.
        Blocks the calling thread — run in a subprocess or background thread."""
        import time
        interval_sec = interval_minutes * 60
        while True:
            try:
                summary = self.monitor_bots(bots, path_for=path_for,
                                            metric=metric, apply=apply)
                print(summary, flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[monitor_bots_daemon] error: {e}", flush=True)
            time.sleep(interval_sec)
