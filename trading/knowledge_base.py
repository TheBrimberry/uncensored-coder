"""
Knowledge base of the open-source trading ecosystem.

This is the "all trading knowledge" core: a curated, opinionated catalogue of the
most relevant GitHub projects, the concepts they teach, and the strategies the
agent knows. It is consumed both as structured data (for routing/integration)
and as natural-language context that is injected into the LLM prompt.

Everything here is real, public, open-source software. The agent uses this map
to decide *which tool/library is appropriate for which job*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass(frozen=True)
class Repo:
    """A single open-source project the agent draws knowledge from."""

    name: str
    url: str
    category: str          # data | execution | backtest | strategy | ml | platform | broker
    asset_classes: List[str]
    summary: str
    teaches: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Curated catalogue. Grouped by what the agent actually does with each project.
# ---------------------------------------------------------------------------
TRADING_REPOS: List[Repo] = [
    # ---- Market data ----
    Repo("yfinance", "https://github.com/ranaroussi/yfinance", "data",
         ["stocks", "etf", "indices", "fx", "crypto"],
         "Free Yahoo Finance market data (OHLCV, fundamentals, options chains).",
         ["historical bars", "fundamentals", "options chains", "corporate actions"]),
    Repo("ccxt", "https://github.com/ccxt/ccxt", "data",
         ["crypto"],
         "Unified API to 100+ crypto exchanges for data and execution.",
         ["exchange normalization", "order books", "OHLCV", "trading endpoints"]),
    Repo("OpenBB", "https://github.com/OpenBB-finance/OpenBB", "data",
         ["stocks", "fx", "crypto", "futures", "options", "macro"],
         "Investment-research platform aggregating dozens of data providers.",
         ["fundamentals", "macro", "screeners", "alt-data", "news"]),
    Repo("pandas-datareader", "https://github.com/pydata/pandas-datareader", "data",
         ["stocks", "macro"], "Reader for FRED, Stooq, World Bank and more.",
         ["macro series", "economic data"]),
    Repo("alpha_vantage", "https://github.com/RomelTorres/alpha_vantage", "data",
         ["stocks", "fx", "crypto"], "Python wrapper for the Alpha Vantage API.",
         ["intraday bars", "fx rates", "technical endpoints"]),

    # ---- Technical analysis ----
    Repo("TA-Lib", "https://github.com/TA-Lib/ta-lib-python", "strategy",
         ["all"], "The canonical C technical-analysis library with 150+ indicators.",
         ["indicators", "candlestick patterns", "overlap studies"]),
    Repo("pandas-ta", "https://github.com/twopirllc/pandas-ta", "strategy",
         ["all"], "130+ indicators as pandas extensions, pure-python friendly.",
         ["indicators", "signal columns", "strategy DSL"]),

    # ---- Backtesting / research ----
    Repo("backtrader", "https://github.com/mementum/backtrader", "backtest",
         ["all"], "Mature event-driven backtesting + live trading framework.",
         ["event loop", "analyzers", "broker simulation", "sizers"]),
    Repo("backtesting.py", "https://github.com/kernc/backtesting.py", "backtest",
         ["all"], "Lightweight, fast, vectorized-ish backtester with nice plots.",
         ["fast backtests", "optimization", "equity curves"]),
    Repo("vectorbt", "https://github.com/polakowo/vectorbt", "backtest",
         ["all"], "Vectorized backtesting at scale on numpy/numba.",
         ["portfolio simulation", "parameter sweeps", "fast metrics"]),
    Repo("zipline-reloaded", "https://github.com/stefan-jansen/zipline-reloaded", "backtest",
         ["stocks"], "Quantopian's institutional backtester, community-maintained.",
         ["pipeline", "factor research", "calendars"]),
    Repo("bt", "https://github.com/pmorissette/bt", "backtest",
         ["stocks", "etf"], "Flexible portfolio/allocation backtesting.",
         ["weighting algos", "rebalancing", "tree strategies"]),

    # ---- Algo trading platforms / bots ----
    Repo("freqtrade", "https://github.com/freqtrade/freqtrade", "platform",
         ["crypto"], "Full-featured crypto algo-trading bot with hyperopt + dry-run.",
         ["strategy class", "hyperopt", "risk management", "dry/live run"]),
    Repo("jesse", "https://github.com/jesse-ai/jesse", "platform",
         ["crypto"], "Crypto trading framework focused on clean research-to-live.",
         ["clean strategy API", "backtest", "indicators"]),
    Repo("hummingbot", "https://github.com/hummingbot/hummingbot", "platform",
         ["crypto"], "Market-making and arbitrage bot across many venues.",
         ["market making", "arbitrage", "liquidity mining"]),
    Repo("nautilus_trader", "https://github.com/nautechsystems/nautilus_trader", "platform",
         ["all"], "High-performance, event-driven trading platform (Rust core).",
         ["low latency", "order management", "multi-venue"]),
    Repo("pysystemtrade", "https://github.com/robcarver17/pysystemtrade", "platform",
         ["futures"], "Rob Carver's systematic futures trading system.",
         ["risk parity", "trend following", "position sizing", "carry"]),
    Repo("StockSharp", "https://github.com/StockSharp/StockSharp", "platform",
         ["all"], "Algorithmic trading and quant platform (.NET).",
         ["strategy designer", "connectors", "backtest"]),

    # ---- Machine learning / quant research ----
    Repo("qlib", "https://github.com/microsoft/qlib", "ml",
         ["stocks"], "Microsoft's AI-oriented quant investment platform.",
         ["factor models", "ml pipelines", "alpha research", "supervised models"]),
    Repo("FinRL", "https://github.com/AI4Finance-Foundation/FinRL", "ml",
         ["all"], "Deep reinforcement learning for automated trading.",
         ["RL environments", "agents (PPO/A2C/DDPG)", "portfolio allocation"]),
    Repo("FinGPT", "https://github.com/AI4Finance-Foundation/FinGPT", "ml",
         ["all"], "Open financial LLMs for sentiment and forecasting research.",
         ["financial sentiment", "LLM fine-tuning", "news understanding"]),
    Repo("mlfinlab-ideas", "https://github.com/hudson-and-thames/mlfinlab", "ml",
         ["all"], "Implementations of 'Advances in Financial ML' (de Prado).",
         ["meta-labeling", "fractional differentiation", "triple-barrier", "purged CV"]),

    # ---- Brokers / execution APIs ----
    Repo("MetaTrader5", "https://github.com/MetaQuotes", "broker",
         ["fx", "cfd", "futures"], "Official MT5 Python integration for FX/CFD brokers.",
         ["MT5 orders", "tick data", "account info"]),
    Repo("tradelocker-python", "https://github.com/tradelocker", "broker",
         ["fx", "cfd", "crypto"], "TradeLocker REST API client for multi-asset brokers.",
         ["TradeLocker auth", "orders", "positions", "instruments"]),
    Repo("alpaca-py", "https://github.com/alpacahq/alpaca-py", "broker",
         ["stocks", "crypto", "options"], "Commission-free US stocks/crypto API.",
         ["paper trading", "market/limit orders", "streaming"]),
    Repo("ib_insync", "https://github.com/erdewit/ib_insync", "broker",
         ["all"], "Pythonic Interactive Brokers API (global multi-asset).",
         ["IB orders", "contracts", "realtime bars"]),
    Repo("ccxt-execution", "https://github.com/ccxt/ccxt", "broker",
         ["crypto"], "ccxt also handles live crypto order execution.",
         ["spot/margin/futures orders", "balances"]),
]


# ---------------------------------------------------------------------------
# Strategy & concept knowledge the agent reasons with.
# ---------------------------------------------------------------------------
STRATEGY_FAMILIES: Dict[str, str] = {
    "trend_following": "Trade in the direction of momentum (MA crossovers, Donchian "
                       "breakouts, Supertrend). Works in trending regimes, bleeds in chop.",
    "mean_reversion": "Fade extremes back to a mean (RSI/Bollinger reversion, pairs/"
                      "stat-arb). Works in ranging regimes, dangerous in trends.",
    "breakout": "Enter when price escapes a consolidation range/volatility squeeze "
                "(opening range, Bollinger squeeze, ATR channel).",
    "momentum": "Buy strength / sell weakness on a cross-sectional or time-series basis "
                "(ROC, relative strength rotation).",
    "carry": "Harvest yield/funding differentials (FX carry, crypto funding-rate, "
             "futures roll). Sensitive to volatility shocks.",
    "market_making": "Quote both sides of the book and earn the spread; manage "
                     "inventory and adverse selection.",
    "arbitrage": "Exploit price differences for the same/related asset (triangular, "
                 "cross-exchange, cash-and-carry).",
    "stat_arb": "Mean-reversion on a portfolio of correlated assets (cointegration, "
                "Kalman-filtered hedge ratios).",
    "event_driven": "Position around scheduled catalysts (earnings, FOMC, CPI, token "
                    "unlocks, halvings) and news surprises.",
    "smart_money_concepts": "Order blocks, liquidity sweeps, fair-value gaps and market "
                            "structure (BOS/CHoCH) popular in FX/crypto discretionary.",
}

RISK_PRINCIPLES: List[str] = [
    "Risk a small fixed fraction of equity per trade (commonly 0.5-2%).",
    "Always define invalidation (stop) BEFORE entry; size from stop distance, not gut.",
    "Use volatility (ATR) to normalize position size across symbols and regimes.",
    "Cap correlated exposure; many 'different' trades are one bet in disguise.",
    "Expectancy = win_rate*avg_win - loss_rate*avg_loss; edge must survive costs+slippage.",
    "Backtests lie via lookahead, survivorship, and overfitting; validate out-of-sample.",
    "Leverage multiplies variance, not edge. Survival first, returns second.",
]


class KnowledgeBase:
    """Queryable view over the trading knowledge catalogue."""

    def __init__(self, repos: List[Repo] | None = None):
        self.repos = repos or TRADING_REPOS

    def by_category(self, category: str) -> List[Repo]:
        return [r for r in self.repos if r.category == category]

    def by_asset_class(self, asset_class: str) -> List[Repo]:
        ac = asset_class.lower()
        return [r for r in self.repos
                if "all" in r.asset_classes or ac in r.asset_classes]

    def recommend_stack(self, asset_class: str) -> Dict[str, List[str]]:
        """Suggest a coherent data/backtest/execution stack for an asset class."""
        relevant = self.by_asset_class(asset_class)
        stack: Dict[str, List[str]] = {}
        for r in relevant:
            stack.setdefault(r.category, []).append(r.name)
        return stack

    def as_prompt_context(self, asset_class: str | None = None) -> str:
        """Render the knowledge base as compact context for the LLM."""
        repos = self.by_asset_class(asset_class) if asset_class else self.repos
        lines = ["KNOWN OPEN-SOURCE TRADING TOOLS (use the right tool for the job):"]
        for r in repos:
            lines.append(f"- {r.name} [{r.category}]: {r.summary}")
        lines.append("\nSTRATEGY FAMILIES:")
        for name, desc in STRATEGY_FAMILIES.items():
            lines.append(f"- {name}: {desc}")
        lines.append("\nNON-NEGOTIABLE RISK PRINCIPLES:")
        for p in RISK_PRINCIPLES:
            lines.append(f"- {p}")
        return "\n".join(lines)
