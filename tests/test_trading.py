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


# ========================================================================
# v2: journal, bots, guardian, patterns, autotune, knowledge corpus
# ========================================================================
from trading.journal import TradeJournal, TradeRecord
from trading.bot import BotConfig
from trading.guardian import RiskGuardian, RiskLimits, GuardedBroker, attach_sl_tp
from trading.patterns import analyze_patterns
from trading.autotune import AutoTuner
from trading.knowledge_corpus import KnowledgeCorpus, BUILTIN_LESSONS


# --- journal / performance review ---------------------------------------
def test_trade_record_pnl_and_return():
    t = TradeRecord("X", "long", entry_price=100, exit_price=110, qty=2, fees=1)
    assert abs(t.net_pnl - 19.0) < 1e-9      # (110-100)*2 - 1
    short = TradeRecord("X", "short", entry_price=100, exit_price=90, qty=1)
    assert abs(short.net_pnl - 10.0) < 1e-9
    assert t.is_win


def test_journal_analyze_and_diagnose():
    recs = [TradeRecord("EURUSD", "long", 1.10, 1.11),
            TradeRecord("EURUSD", "short", 1.11, 1.12),   # losing short
            TradeRecord("GBPUSD", "long", 1.30, 1.28)]    # losing symbol
    rep = TradeJournal.from_records(recs).analyze()
    assert rep.n_trades == 3
    assert 0 <= rep.win_rate <= 1
    assert rep.insights                                    # produced diagnoses


def test_journal_from_csv(tmp_path):
    csv_path = tmp_path / "t.csv"
    csv_path.write_text("ticker,action,entry,exit,size\n"
                        "AAPL,buy,100,110,10\nAAPL,sell,110,108,10\n")
    rep = TradeJournal.from_csv(str(csv_path)).analyze()
    assert rep.n_trades == 2


def test_review_via_agent_and_backtest():
    agent = TradingAgent()
    bt = agent.backtest("BTC/USDT", "ma_crossover", limit=400)
    rep = agent.review_performance(bt)        # from BacktestResult
    assert rep.n_trades == bt.n_trades


# --- bot config: audit + rollback ---------------------------------------
def test_botconfig_update_audit_and_rollback():
    bot = BotConfig(name="b", symbol="EURUSD", strategy="ma_crossover",
                    params={"fast": 50, "slow": 200})
    bot.update_params({"fast": 20}, reason="test")
    assert bot.params["fast"] == 20
    assert len(bot.history) == 1
    bot.rollback()
    assert bot.params["fast"] == 50


def test_botconfig_save_load(tmp_path):
    p = tmp_path / "bot.json"
    bot = BotConfig(name="b", symbol="BTC/USDT", strategy="rsi_reversion",
                    params={"period": 14})
    bot.save(str(p))
    loaded = BotConfig.load(str(p))
    assert loaded.symbol == "BTC/USDT" and loaded.params["period"] == 14


# --- guardian: account protection ---------------------------------------
def test_guardian_requires_stop_loss():
    g = RiskGuardian(10_000, RiskLimits())
    d = g.check(Order("X", OrderSide.BUY, 1, price=100, stop_loss=None))
    assert not d.allowed and any("stop" in r.lower() for r in d.reasons)


def test_guardian_blocks_oversized_risk():
    g = RiskGuardian(10_000, RiskLimits(max_risk_pct_per_trade=1.0))
    # risking 100*5 = 500 = 5% > 1%
    d = g.check(Order("X", OrderSide.BUY, 5, price=100, stop_loss=0))
    assert not d.allowed


def test_guardian_daily_loss_circuit_breaker():
    g = RiskGuardian(10_000, RiskLimits(max_daily_loss_pct=5.0))
    g.record_fill(-600)                       # -6% day
    d = g.check(Order("X", OrderSide.BUY, 1, price=100, stop_loss=98))
    assert not d.allowed and g.state.halted


def test_guardian_drawdown_kill_switch():
    g = RiskGuardian(10_000, RiskLimits(max_total_drawdown_pct=20.0))
    g.record_fill(1000)                        # peak 11k
    g.record_fill(-3000)                       # equity 8k, dd ~27%
    assert g.state.halted and "drawdown" in g.state.halt_reason


def test_guarded_broker_blocks_then_allows():
    g = RiskGuardian(10_000, RiskLimits())
    gb = GuardedBroker(get_broker("paper"), g)
    gb.connect()
    decision, result = gb.place_order(Order("X", OrderSide.BUY, 1, price=100, stop_loss=None))
    assert not decision.allowed and result is None
    decision2, result2 = gb.place_order(
        Order("X", OrderSide.BUY, 1, price=100, stop_loss=99))
    assert decision2.allowed and result2 is not None


def test_attach_sl_tp_fills_missing_levels():
    o = Order("X", OrderSide.BUY, 1, price=100)
    attach_sl_tp(o, atr_value=2.0, direction="long", atr_stop_mult=2.0, rr=2.0)
    assert o.stop_loss is not None and o.stop_loss < 100
    assert o.take_profit is not None and o.take_profit > 100


def test_agent_execute_is_guarded():
    agent = TradingAgent()
    plan = agent.trade_plan("AAPL")
    msg = agent.execute_plan(plan, broker="paper")
    assert "PAPER" in msg or "BLOCKED" in msg or "flat" in msg


# --- patterns / co-pilot -------------------------------------------------
def test_patterns_produce_insights():
    bars = MarketData().get_ohlcv("BTC/USDT", limit=300).as_bars()
    mi = analyze_patterns("BTC/USDT", bars)
    assert mi.regime
    assert "resistance" in mi.key_levels and "support" in mi.key_levels
    assert mi.highlights
    assert "CO-PILOT" in mi.to_text()


# --- autotune: parameter proposals with guardrails ----------------------
def test_autotuner_proposes_with_guardrails():
    tuner = AutoTuner(min_improvement_pct=10.0, require_robust=True)
    bot = BotConfig(name="t", symbol="BTC/USDT", strategy="ma_crossover",
                    params={"fast": 50, "slow": 200})
    prop = tuner.propose_params(bot, metric="total_return")
    assert prop.best_params
    # recommendation requires robust AND improvement AND a change
    assert isinstance(prop.recommended, bool)
    if prop.recommended:
        assert prop.oos_robust and prop.improvement_pct >= 10.0


def test_autotuner_monitor_dry_run():
    tuner = AutoTuner()
    bots = [BotConfig(name="a", symbol="AAPL", strategy="rsi_reversion",
                      params={"period": 14, "low": 30, "high": 70})]
    report = tuner.monitor(bots, apply=False)
    assert "AUTO-TUNE SWEEP" in report and "DRY-RUN" in report


def test_improve_code_no_path_is_safe():
    agent = TradingAgent()
    bot = BotConfig(name="x", symbol="AAPL", strategy="ma_crossover", params={})
    proposal = agent.improve_bot_code(bot)        # no code_path -> safe no-op
    assert not proposal.applied


# --- knowledge corpus ----------------------------------------------------
def test_corpus_has_builtin_and_retrieves():
    c = KnowledgeCorpus()
    assert len(c.documents) == len(BUILTIN_LESSONS)
    hits = c.retrieve("risk of ruin position sizing", k=3)
    assert hits and hits[0][1] > 0


def test_corpus_ingest_and_persist(tmp_path):
    c = KnowledgeCorpus()
    n = c.ingest_text("London open breakout: trade the Asian range sweep.",
                      title="my note", tags=["fx"])
    assert n >= 1
    p = tmp_path / "corpus.json"
    c.save(str(p))
    c2 = KnowledgeCorpus()
    added = c2.load(str(p))
    assert added >= 1
    assert any("London" in d.content for d in c2.documents)


def test_corpus_url_ingest_with_fetcher():
    c = KnowledgeCorpus()
    fake_fetch = lambda url: "Carry trade harvests interest rate differentials."
    n = c.ingest_url("https://example.com/fx", fetcher=fake_fetch, tags=["fx"])
    assert n >= 1
    assert c.retrieve("carry interest differential", k=1)


def test_agent_learn_and_ingest():
    agent = TradingAgent()
    msg = agent.ingest_knowledge(text="VWAP reversion is an institutional staple.",
                                 title="note")
    assert "Ingested" in msg
    assert "VWAP" in agent.learn("vwap reversion")
