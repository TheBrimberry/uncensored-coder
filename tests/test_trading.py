"""
Tests for the trading agent. All run fully offline using the synthetic data
fallback, so no network / Ollama / API keys are required.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading import indicators as ind
from trading import strategies as strat
from trading.market_data import (
    MarketData, _looks_like_crypto, _looks_like_fx, _fx_to_yahoo,
)
from trading.brokers import OrderType
from trading.forecast import Forecaster
from trading.analysis import AnalysisEngine
from trading.risk import build_trade_plan, position_size
from trading.brokers import get_broker, Order, OrderSide
from trading.knowledge_base import KnowledgeBase
from trading.news import score_sentiment
from trading.agent import TradingAgent
from trading.backtest import Backtester
from trading.optimize import grid_search, walk_forward, DEFAULT_GRIDS, METRICS


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


# --- backtest ------------------------------------------------------------
def test_backtest_runs_and_reports():
    bars = MarketData().get_ohlcv("BTC/USDT", limit=500).as_bars()
    result = Backtester(warmup=200).run(bars, strategy="ma_crossover", symbol="BTC/USDT")
    assert result.n_trades >= 0
    assert 0.0 <= result.win_rate <= 1.0
    assert result.max_drawdown_pct >= 0.0
    assert result.final_equity > 0
    # closed trades must have an exit
    assert all(t.exit_index is not None for t in result.trades)


def test_backtest_no_lookahead_window_grows():
    # ensemble strategy across the whole series should produce a valid result
    bars = MarketData().get_ohlcv("ETH/USDT", limit=400).as_bars()
    result = Backtester(warmup=150).run(bars, strategy="ensemble", symbol="ETH/USDT")
    assert "BACKTEST" in result.summary()


def test_agent_backtest_helper():
    result = TradingAgent().backtest("AAPL", strategy="ensemble", limit=400)
    assert isinstance(result.summary(), str)


def test_backtest_unknown_strategy_raises():
    import pytest
    bars = MarketData().get_ohlcv("X", limit=300).as_bars()
    with pytest.raises(ValueError):
        Backtester().run(bars, strategy="nope")


# --- optimization & walk-forward ----------------------------------------
def test_grid_search_picks_best():
    bars = MarketData().get_ohlcv("BTC/USDT", limit=600).as_bars()
    grid = grid_search(bars, "ma_crossover", DEFAULT_GRIDS["ma_crossover"],
                       metric="total_return", symbol="BTC/USDT")
    assert grid.best_params in [p for p, _, _ in grid.table]
    # table is sorted best-first
    scores = [s for _, s, _ in grid.table]
    assert scores == sorted(scores, reverse=True)
    assert grid.best_score == scores[0]


def test_grid_search_unknown_metric_raises():
    import pytest
    bars = MarketData().get_ohlcv("X", limit=300).as_bars()
    with pytest.raises(ValueError):
        grid_search(bars, "ma_crossover", {}, metric="nope")


def test_walk_forward_runs_oos():
    bars = MarketData().get_ohlcv("ETH/USDT", limit=900).as_bars()
    wf = walk_forward(bars, "rsi_reversion", DEFAULT_GRIDS["rsi_reversion"],
                      n_folds=3, metric="total_return", symbol="ETH/USDT")
    assert wf.n_folds >= 1
    assert len(wf.fold_params) == wf.n_folds
    assert isinstance(wf.robust, bool)
    assert "WALK-FORWARD" in wf.summary()


def test_agent_optimize_and_walk_forward():
    agent = TradingAgent()
    g = agent.optimize("AAPL", strategy="bollinger_breakout", limit=500)
    assert g.strategy == "bollinger_breakout"
    w = agent.walk_forward("AAPL", strategy="ma_crossover", limit=800, n_folds=3)
    assert "WALK-FORWARD" in w.summary()


def test_all_metrics_callable():
    bars = MarketData().get_ohlcv("BTC/USDT", limit=400).as_bars()
    res = Backtester(warmup=150).run(bars, strategy="ma_crossover")
    for name, fn in METRICS.items():
        assert isinstance(fn(res), (int, float)), name


# --- broker smoke test script -------------------------------------------
# --- review-fix regressions ---------------------------------------------
def test_fx_detection_and_yahoo_mapping():
    assert _looks_like_fx("EURUSD") and _looks_like_fx("EUR/USD")
    assert _looks_like_fx("GBPJPY")
    assert not _looks_like_fx("AAPL")
    assert not _looks_like_fx("BTCUSDT")     # crypto, not FX
    assert _fx_to_yahoo("EUR/USD") == "EURUSD=X"
    assert _fx_to_yahoo("EURUSD=X") == "EURUSD=X"


def test_paper_broker_weighted_average_price():
    bkr = get_broker("paper")
    bkr.connect()
    bkr.place_order(Order("X", OrderSide.BUY, 1.0, price=100))
    bkr.place_order(Order("X", OrderSide.BUY, 1.0, price=200))
    pos = bkr.positions()[0]
    assert pos.qty == 2.0
    assert abs(pos.avg_price - 150.0) < 1e-9   # was 100 before the fix


def test_paper_broker_reduce_keeps_avg_then_flips():
    bkr = get_broker("paper")
    bkr.connect()
    bkr.place_order(Order("X", OrderSide.BUY, 2.0, price=100))
    bkr.place_order(Order("X", OrderSide.SELL, 1.0, price=150))   # reduce
    pos = bkr.positions()[0]
    assert pos.qty == 1.0 and abs(pos.avg_price - 100.0) < 1e-9   # avg unchanged
    bkr.place_order(Order("X", OrderSide.SELL, 3.0, price=150))   # flip through 0
    pos = bkr.positions()[0]
    assert pos.qty == -2.0 and abs(pos.avg_price - 150.0) < 1e-9  # remainder reprices


def test_backtest_eod_close_counts_in_drawdown():
    # Strictly declining series; force long entries with a wide stop so the
    # position survives to the final bar and closes at a loss (EOD).
    n = 120
    close = [200.0 - i for i in range(n)]
    high = [c + 0.1 for c in close]
    low = [c - 0.1 for c in close]
    bars = {"open": close[:], "high": high, "low": low, "close": close,
            "volume": [1.0] * n}
    always_long = lambda w: strat.Signal("forced", strat.Direction.LONG, 1.0, "test")
    # huge stop multiplier -> stop never hit -> trade closes only at EOD
    bt = Backtester(warmup=30, atr_stop_mult=100.0, rr=2.0)
    res = bt.run(bars, strategy=always_long, symbol="DOWN")
    assert res.n_trades >= 1
    assert res.trades[-1].reason == "eod"
    assert res.max_drawdown_pct > 0.0       # was understated before the fix


def test_broker_smoke_test_is_safe_noop_without_creds():
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Ensure no broker creds leak in from the environment.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("MT5_", "TRADELOCKER_"))}
    proc = subprocess.run(
        [sys.executable, os.path.join(root, "scripts", "broker_smoke_test.py")],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert proc.returncode == 0
    assert "safe no-op" in proc.stdout
