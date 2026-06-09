"""
Tests for the trading agent. All run fully offline using the synthetic data
fallback, so no network / Ollama / API keys are required.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading import indicators as ind
from trading import strategies as strat
from trading.market_data import MarketData, _looks_like_crypto
from trading.forecast import Forecaster
from trading.analysis import AnalysisEngine
from trading.risk import build_trade_plan, position_size
from trading.brokers import get_broker, Order, OrderSide
from trading.knowledge_base import KnowledgeBase
from trading.news import score_sentiment
from trading.agent import TradingAgent


# --- indicators ----------------------------------------------------------
def test_sma_basic():
    assert ind.last(ind.sma([1, 2, 3, 4, 5], 5)) == 3.0


def test_ema_warmup_none():
    vals = ind.ema([1, 2, 3], 5)
    assert all(v is None for v in vals)


def test_rsi_bounds():
    series = [i % 7 + 1 for i in range(60)]
    r = ind.last(ind.rsi(series, 14))
    assert r is not None and 0 <= r <= 100


def test_atr_positive():
    h = [10 + i for i in range(40)]
    l = [9 + i for i in range(40)]
    c = [9.5 + i for i in range(40)]
    assert ind.last(ind.atr(h, l, c, 14)) > 0


# --- strategies ----------------------------------------------------------
def test_strategies_emit_signals():
    bars = MarketData().get_ohlcv("TEST", limit=300).as_bars()
    signals = strat.run_all(bars)
    assert len(signals) == len(strat.STRATEGIES)
    net = strat.ensemble(signals)
    assert net.direction in (strat.Direction.LONG, strat.Direction.SHORT, strat.Direction.FLAT)


# --- market data ---------------------------------------------------------
def test_synthetic_fallback_is_deterministic():
    a = MarketData().get_ohlcv("FOO", limit=50)
    b = MarketData().get_ohlcv("FOO", limit=50)
    assert a.close == b.close
    assert len(a) == 50


def test_crypto_detection():
    assert _looks_like_crypto("BTC/USDT")
    assert _looks_like_crypto("ETHUSDT")
    assert not _looks_like_crypto("AAPL")


# --- forecast ------------------------------------------------------------
def test_forecast_probabilities_sane():
    bars = MarketData().get_ohlcv("BTC/USDT", limit=200).as_bars()
    fc = Forecaster().forecast("BTC/USDT", bars, horizon=5)
    assert 0.0 <= fc.prob_up <= 1.0
    assert 0.0 <= fc.confidence <= 1.0
    assert fc.low_band_pct <= fc.high_band_pct


# --- risk ----------------------------------------------------------------
def test_position_size_respects_risk():
    size = position_size(10_000, 1.0, entry=100, stop=98)
    assert abs(size * 2 - 100) < 1e-6  # risk 100 over 2-wide stop -> 50 units


def test_trade_plan_rr():
    plan = build_trade_plan("X", "long", entry=100, atr_value=2.0, rr=2.0)
    assert plan is not None
    assert plan.stop < plan.entry < plan.take_profit
    assert abs(plan.risk_reward - 2.0) < 1e-9


# --- brokers -------------------------------------------------------------
def test_paper_broker_simulates():
    bkr = get_broker("paper")
    bkr.connect()
    res = bkr.place_order(Order("BTC/USDT", OrderSide.BUY, 1.0, price=100))
    assert res.accepted and res.simulated
    assert bkr.positions()[0].qty == 1.0


def test_unknown_broker_falls_back_to_paper():
    bkr = get_broker("does-not-exist")
    assert bkr.name == "base"


# --- knowledge base ------------------------------------------------------
def test_kb_recommends_stack():
    kb = KnowledgeBase()
    stack = kb.recommend_stack("crypto")
    assert "data" in stack
    assert any("ccxt" in v for v in stack.values())


def test_sentiment_lexicon():
    assert score_sentiment("massive rally and record gains") > 0
    assert score_sentiment("market crash and hack lawsuit") < 0
    assert score_sentiment("the meeting is at noon") == 0


# --- agent end-to-end (no LLM) ------------------------------------------
def test_agent_analyze_offline():
    agent = TradingAgent()
    report = agent.analyze("BTC/USDT")
    text = report.to_text()
    assert "ANALYSIS" in text
    assert report.forecast is not None


def test_agent_ask_degrades_without_llm():
    # No Ollama in CI -> should return computed report, not crash.
    answer = TradingAgent().ask("AAPL")
    assert isinstance(answer, str) and len(answer) > 0


def test_agent_execute_paper_plan():
    agent = TradingAgent()
    plan = agent.trade_plan("BTC/USDT")
    msg = agent.execute_plan(plan, broker="paper")
    assert "PAPER" in msg or "flat" in msg
