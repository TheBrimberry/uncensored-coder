"""
Omniscient Trading Agent
========================

A knowledge-dense, multi-asset trading agent that fuses the best ideas from the
open-source trading ecosystem (freqtrade, ccxt, backtrader, vectorbt, OpenBB,
qlib, FinRL, pandas-ta, TradeLocker, MetaTrader5, alpaca, and more) into a
single reasoning engine driven by a local LLM.

Capabilities
------------
* Analyze/forecast any symbol (FX, crypto, stocks, futures) — probabilistically.
* Backtest, grid-optimize and walk-forward-validate strategies.
* Review your past trading data and diagnose weaknesses.
* Auto-tune bot parameters AND propose code edits — safely, with guardrails.
* Side-by-side co-pilot: highlight patterns, key levels and insights.
* Account guardian: enforce stops, size/loss/drawdown limits — don't blow up.
* Deep, growable knowledge corpus you can teach with your own sources.

>>> from trading import TradingAgent
>>> agent = TradingAgent()
>>> print(agent.analyze("BTC/USDT").to_text())
"""

from .agent import TradingAgent
from .knowledge_base import KnowledgeBase, TRADING_REPOS
from .knowledge_corpus import KnowledgeCorpus, BUILTIN_LESSONS, Lesson
from .analysis import AnalysisEngine, AnalysisReport
from .forecast import Forecaster, Forecast
from .backtest import Backtester, BacktestResult
from .optimize import grid_search, walk_forward, GridResult, WalkForwardResult, DEFAULT_GRIDS
from .journal import TradeJournal, TradeRecord, PerformanceReport, Insight
from .bot import BotConfig
from .autotune import AutoTuner, TuneProposal, CodeProposal
from .guardian import RiskGuardian, RiskLimits, GuardedBroker, GuardianState, attach_sl_tp
from .patterns import analyze_patterns, MarketInsights, Pattern
from .regime import detect_regime, RegimeResult, MarketRegime
from .mtf import MultiTimeframeAnalyzer, MTFAnalysis, MTFSignal

__all__ = [
    "TradingAgent",
    "KnowledgeBase",
    "TRADING_REPOS",
    "KnowledgeCorpus",
    "BUILTIN_LESSONS",
    "Lesson",
    "AnalysisEngine",
    "AnalysisReport",
    "Forecaster",
    "Forecast",
    "Backtester",
    "BacktestResult",
    "grid_search",
    "walk_forward",
    "GridResult",
    "WalkForwardResult",
    "DEFAULT_GRIDS",
    "TradeJournal",
    "TradeRecord",
    "PerformanceReport",
    "Insight",
    "BotConfig",
    "AutoTuner",
    "TuneProposal",
    "CodeProposal",
    "RiskGuardian",
    "RiskLimits",
    "GuardedBroker",
    "GuardianState",
    "attach_sl_tp",
    "analyze_patterns",
    "MarketInsights",
    "Pattern",
    "detect_regime",
    "RegimeResult",
    "MarketRegime",
    "MultiTimeframeAnalyzer",
    "MTFAnalysis",
    "MTFSignal",
]

__version__ = "3.0.0"
