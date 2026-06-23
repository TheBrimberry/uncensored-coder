"""
Analysis engine.

The deterministic core that gathers everything about a symbol — market data,
indicators, strategy signals, an ensemble view, a probabilistic forecast, a
risk-managed trade plan, and news/event context — into a single `AnalysisReport`.

The LLM agent (agent.py) narrates this report; the engine here does the math so
the agent's reasoning is grounded in real numbers rather than vibes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import indicators as ind
from . import strategies as strat
from .forecast import Forecaster, Forecast
from .market_data import MarketData, OHLCV, _looks_like_crypto
from .news import NewsFeed, NewsReport
from .risk import build_trade_plan, TradePlan


@dataclass
class AnalysisReport:
    symbol: str
    timeframe: str
    last_price: float
    data_source: str
    synthetic: bool
    indicators: Dict[str, Optional[float]]
    signals: List[dict]
    ensemble: dict
    forecast: Forecast
    trade_plan: Optional[TradePlan]
    news: NewsReport
    warnings: List[str] = field(default_factory=list)

    def to_text(self) -> str:
        """Human-readable digest (also used as LLM context)."""
        lines = [
            f"=== ANALYSIS: {self.symbol} ({self.timeframe}) ===",
            f"Last price: {self.last_price:.4f}  | source: {self.data_source}"
            + ("  [SYNTHETIC DATA — install ccxt/yfinance for real data]"
               if self.synthetic else ""),
            "",
            "Indicators:",
        ]
        for k, v in self.indicators.items():
            lines.append(f"  {k}: {v:.4f}" if isinstance(v, (int, float)) else f"  {k}: n/a")
        lines.append("\nStrategy signals:")
        for s in self.signals:
            lines.append(f"  [{s['direction']:>5}] {s['strategy']} "
                         f"({s['strength']:.2f}) — {s['rationale']}")
        lines.append(f"\nEnsemble: {self.ensemble['direction'].upper()} "
                     f"({self.ensemble['strength']:.2f}) — {self.ensemble['rationale']}")
        lines.append(f"\nForecast: {self.forecast.summary()}")
        if self.trade_plan:
            lines.append(f"\nProposed plan: {self.trade_plan.summary()}")
        lines.append(f"\nNews/Events: {self.news.summary()}")
        if self.warnings:
            lines.append("\nWarnings: " + "; ".join(self.warnings))
        return "\n".join(lines)


class AnalysisEngine:
    def __init__(self, market_data: Optional[MarketData] = None,
                 news_feed: Optional[NewsFeed] = None,
                 forecaster: Optional[Forecaster] = None):
        self.md = market_data or MarketData()
        self.news = news_feed or NewsFeed()
        self.forecaster = forecaster or Forecaster()

    def analyze(self, symbol: str, timeframe: str = "1d",
                account_equity: float = 10_000.0, risk_pct: float = 1.0,
                horizon: int = 5) -> AnalysisReport:
        data: OHLCV = self.md.get_ohlcv(symbol, timeframe)
        bars = data.as_bars()
        c = bars["close"]
        warnings: List[str] = []
        if data.synthetic:
            warnings.append("Using synthetic data — not real market prices.")

        # indicator snapshot
        snapshot = {
            "EMA20": ind.last(ind.ema(c, 20)),
            "EMA50": ind.last(ind.ema(c, 50)),
            "EMA200": ind.last(ind.ema(c, 200)),
            "RSI14": ind.last(ind.rsi(c, 14)),
            "ATR14": ind.last(ind.atr(bars["high"], bars["low"], c, 14)),
            "MACD_hist": ind.last(ind.macd(c)["hist"]),
        }

        signals = strat.run_all(bars)
        net = strat.ensemble(signals)
        forecast = self.forecaster.forecast(symbol, bars, horizon)

        # trade plan from ensemble direction + ATR
        plan: Optional[TradePlan] = None
        atr_val = snapshot["ATR14"]
        if net.direction != strat.Direction.FLAT and atr_val:
            plan = build_trade_plan(
                symbol, net.direction.value, entry=c[-1], atr_value=atr_val,
                account_equity=account_equity, risk_pct=risk_pct,
            )

        news = self.news.get_news(symbol, is_crypto=_looks_like_crypto(symbol))

        return AnalysisReport(
            symbol=symbol, timeframe=timeframe, last_price=c[-1],
            data_source=data.source, synthetic=data.synthetic,
            indicators=snapshot,
            signals=[s.as_dict() for s in signals],
            ensemble=net.as_dict(), forecast=forecast,
            trade_plan=plan, news=news, warnings=warnings,
        )
