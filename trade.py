#!/usr/bin/env python3
"""
Omniscient Trading Agent — CLI entry point.

Examples
--------
    python trade.py BTC/USDT                 # full LLM-narrated analysis
    python trade.py AAPL --timeframe 1h      # intraday
    python trade.py EURUSD --no-llm          # computed report only (no Ollama)
    python trade.py ETH/USDT --forecast 10   # 10-bar probabilistic forecast
    python trade.py --interactive            # chat loop over symbols
    python trade.py --knowledge crypto       # dump the trading knowledge base
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    from rich.console import Console
    from rich.panel import Panel
    _console = Console()
    def out(text, title=None, style="cyan"):
        _console.print(Panel(text, title=title, border_style=style) if title else text)
except Exception:  # rich is optional
    def out(text, title=None, style=None):
        if title:
            print(f"\n=== {title} ===")
        print(text)

from trading import TradingAgent


def _banner():
    out("📈  OMNISCIENT TRADING AGENT  📈\n"
        "Multi-asset analysis · forecasts · risk-managed plans · FX/crypto/stocks\n"
        "Honest by design: probabilities, not promises.", style="green")


def run_once(args):
    agent = TradingAgent(model=args.model, account_equity=args.equity,
                         risk_pct=args.risk)
    if args.backtest:
        result = agent.backtest(args.symbol, strategy=args.backtest,
                                timeframe=args.timeframe)
        out(result.summary(), title=f"Backtest: {args.symbol}", style="yellow")
    elif args.optimize:
        result = agent.optimize(args.symbol, strategy=args.optimize,
                                timeframe=args.timeframe, metric=args.metric)
        out(result.summary(), title=f"Optimize: {args.symbol}", style="yellow")
    elif args.walk_forward:
        result = agent.walk_forward(args.symbol, strategy=args.walk_forward,
                                    timeframe=args.timeframe, metric=args.metric)
        out(result.summary(), title=f"Walk-forward: {args.symbol}", style="yellow")
    elif args.insights:
        out(agent.insights(args.symbol, timeframe=args.timeframe).to_text(),
            title=f"Co-pilot: {args.symbol}", style="cyan")
    elif args.regime:
        out(agent.regime(args.symbol, timeframe=args.timeframe).to_text(),
            title=f"Regime: {args.symbol}", style="yellow")
    elif args.mtf:
        tfs = [t.strip() for t in args.mtf.split(",")] if args.mtf != "default" else None
        out(agent.mtf(args.symbol, timeframes=tfs).to_text(),
            title=f"Multi-TF: {args.symbol}", style="cyan")
    elif args.no_llm:
        report = agent.analyze(args.symbol, timeframe=args.timeframe,
                               horizon=args.forecast)
        out(report.to_text(), title=f"Analysis: {args.symbol}")
    else:
        answer = agent.ask(args.symbol, question=args.question,
                           timeframe=args.timeframe, horizon=args.forecast)
        out(answer, title=f"Trading read: {args.symbol}", style="magenta")


def run_interactive(args):
    agent = TradingAgent(model=args.model, account_equity=args.equity,
                         risk_pct=args.risk)
    out("Interactive mode. Type a symbol (e.g. BTC/USDT, AAPL, EURUSD), "
        "'kb <asset>' for knowledge, or 'exit'.", style="cyan")
    while True:
        try:
            line = input("\n📈 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.lower() in ("exit", "quit"):
            break
        if line.lower().startswith("kb"):
            parts = line.split()
            out(agent.knowledge(parts[1] if len(parts) > 1 else None),
                title="Knowledge base")
            continue
        # "SYMBOL ? question" syntax, optional
        symbol, _, question = line.partition("?")
        symbol = symbol.strip()
        question = question.strip() or None
        if args.no_llm:
            out(agent.analyze(symbol, timeframe=args.timeframe).to_text(),
                title=f"Analysis: {symbol}")
        else:
            out(agent.ask(symbol, question=question, timeframe=args.timeframe),
                title=f"Trading read: {symbol}", style="magenta")


def main():
    p = argparse.ArgumentParser(description="Omniscient multi-asset trading agent")
    p.add_argument("symbol", nargs="?", help="Symbol to analyze (BTC/USDT, AAPL, EURUSD)")
    p.add_argument("--timeframe", "-t", default="1d", help="Bar timeframe (1d,1h,15m,5m)")
    p.add_argument("--forecast", "-f", type=int, default=5, help="Forecast horizon in bars")
    p.add_argument("--question", "-q", help="Specific question about the symbol")
    p.add_argument("--equity", type=float, default=10_000.0, help="Account equity for sizing")
    p.add_argument("--risk", type=float, default=1.0, help="Risk %% per trade")
    p.add_argument("--model", "-m", help="Override Ollama model")
    p.add_argument("--no-llm", action="store_true", help="Skip LLM, show computed report")
    p.add_argument("--backtest", "-b", nargs="?", const="ensemble",
                   help="Backtest a strategy (default: ensemble) on historical bars")
    p.add_argument("--optimize", "-o", nargs="?", const="ma_crossover",
                   help="Grid-search a strategy's parameters (default: ma_crossover)")
    p.add_argument("--walk-forward", "-w", nargs="?", const="ma_crossover",
                   help="Out-of-sample walk-forward validation (default: ma_crossover)")
    p.add_argument("--metric", default="calmar",
                   help="Optimization metric: calmar|profit_factor|sharpe|total_return|win_rate")
    p.add_argument("--insights", action="store_true",
                   help="Co-pilot: highlight patterns, key levels and insights")
    p.add_argument("--interactive", "-i", action="store_true", help="Interactive loop")
    p.add_argument("--knowledge", "-k", nargs="?", const="", help="Dump knowledge base")
    p.add_argument("--learn", help="Retrieve deep knowledge for a topic/question")
    p.add_argument("--ingest", help="Teach the agent: ingest a file or directory of notes")
    p.add_argument("--ingest-url", help="Fetch and ingest a URL into the knowledge corpus")
    p.add_argument("--review", help="Review past trading data (CSV or JSON of trades)")
    p.add_argument("--tune", help="Tune a bot's parameters from its JSON config file")
    p.add_argument("--apply", action="store_true",
                   help="With --tune/--monitor-bots: apply changes if robust (else dry-run)")
    p.add_argument("--regime", action="store_true",
                   help="Detect and report the current market regime (trending/ranging/high-vol)")
    p.add_argument("--mtf", nargs="?", const="default",
                   help="Multi-timeframe analysis; optionally pass comma-separated TFs "
                        "(e.g. '1w,1d,4h') or omit for defaults (1w,1d,4h,1h)")
    p.add_argument("--monitor-bots", metavar="BOT_CONFIGS",
                   help="Comma-separated paths to BotConfig JSON files to sweep on a schedule")
    p.add_argument("--monitor-interval", type=float, default=60.0,
                   help="Interval in minutes between monitor-bots sweeps (default: 60)")
    args = p.parse_args()

    _banner()

    if args.knowledge is not None:
        out(TradingAgent().knowledge(args.knowledge or None), title="Knowledge base")
        return
    if args.learn:
        out(TradingAgent().learn(args.learn), title=f"Knowledge: {args.learn}")
        return
    if args.ingest:
        agent = TradingAgent()
        path = args.ingest
        kind = "directory" if os.path.isdir(path) else "file"
        msg = agent.ingest_knowledge(**{kind: path},
                                     save_path=os.path.expanduser("~/.trading_corpus.json"))
        out(msg, title="Ingest")
        return
    if args.ingest_url:
        agent = TradingAgent()
        msg = agent.ingest_knowledge(url=args.ingest_url,
                                     save_path=os.path.expanduser("~/.trading_corpus.json"))
        out(msg, title=f"Ingest URL: {args.ingest_url}")
        return
    if args.review:
        out(TradingAgent().review_performance(args.review).to_text(),
            title=f"Performance: {args.review}", style="magenta")
        return
    if args.tune:
        from trading import BotConfig
        agent = TradingAgent()
        bot = BotConfig.load(args.tune)
        proposal = agent.tune_bot(bot, metric=args.metric, apply=args.apply,
                                  path=args.tune if args.apply else None)
        out(proposal.summary(), title=f"Tune: {bot.name}", style="yellow")
        return
    if args.monitor_bots:
        from trading import BotConfig
        agent = TradingAgent()
        bots = [BotConfig.load(p) for p in args.monitor_bots.split(",")]
        interval = args.monitor_interval
        out(f"Starting monitor daemon — sweeping {len(bots)} bot(s) every {interval}min.",
            style="cyan")
        agent.monitor_bots_daemon(bots, metric=args.metric, apply=args.apply,
                                  interval_minutes=interval)
        return  # blocks until Ctrl-C
    if args.interactive:
        run_interactive(args)
        return
    if not args.symbol:
        p.print_help()
        sys.exit(0)
    run_once(args)


if __name__ == "__main__":
    main()
