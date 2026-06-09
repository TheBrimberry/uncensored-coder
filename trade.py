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
    if args.no_llm:
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
    p.add_argument("--interactive", "-i", action="store_true", help="Interactive loop")
    p.add_argument("--knowledge", "-k", nargs="?", const="", help="Dump knowledge base")
    args = p.parse_args()

    _banner()

    if args.knowledge is not None:
        out(TradingAgent().knowledge(args.knowledge or None), title="Knowledge base")
        return
    if args.interactive:
        run_interactive(args)
        return
    if not args.symbol:
        p.print_help()
        sys.exit(0)
    run_once(args)


if __name__ == "__main__":
    main()
