"""
Omniscient Trading Agent
========================

A knowledge-dense, multi-asset trading agent that fuses the best ideas from the
open-source trading ecosystem (freqtrade, ccxt, backtrader, vectorbt, OpenBB,
qlib, FinRL, pandas-ta, TradeLocker, MetaTrader5, alpaca, and more) into a
single reasoning engine driven by a local LLM.

Design principles
-----------------
* **Honest, not magical.** No software can guarantee a market prediction.
  Forecasts here are *probabilistic* with explicit confidence, never promises.
* **Multi-asset.** Forex (FX/"4X"), crypto, stocks, indices, futures, options.
* **Pluggable.** Every external integration (data, brokers, news) degrades
  gracefully if its optional dependency or API key is missing.
* **Composable.** Indicators -> strategies -> signals -> analysis -> agent.

Public surface
--------------
>>> from trading import TradingAgent
>>> agent = TradingAgent()
>>> print(agent.analyze("BTC/USDT"))
"""

from .agent import TradingAgent
from .knowledge_base import KnowledgeBase, TRADING_REPOS
from .analysis import AnalysisEngine, AnalysisReport
from .forecast import Forecaster, Forecast

__all__ = [
    "TradingAgent",
    "KnowledgeBase",
    "TRADING_REPOS",
    "AnalysisEngine",
    "AnalysisReport",
    "Forecaster",
    "Forecast",
]

__version__ = "1.0.0"
