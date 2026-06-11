"""
Deep quant knowledge corpus + ingestion engine.

Two halves:

1. `BUILTIN_LESSONS` — a dense, curated body of trading knowledge that goes well
   beyond retail surface-level material: microstructure, smart-money concepts,
   FX session edges, statistical anomalies, risk-of-ruin math, options & crypto
   specifics, execution, and the backtesting traps that kill most "edges".

2. `KnowledgeCorpus` — a lightweight, dependency-free retrieval engine. It holds
   the built-in lessons plus anything *you* ingest (your own notes, MyFxbook
   stats, articles you have the right to read, exported books), indexes it, and
   returns the most relevant passages as context for the LLM. It persists to
   JSON so the agent's knowledge grows over time.

Honesty note: there is no secret that guarantees profit. The real edge is the
boring stuff done relentlessly — costs, sizing, risk control, and not fooling
yourself in the backtest. This corpus encodes that, plus the genuinely useful
techniques most people skip.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class Lesson:
    topic: str
    level: str                 # "core" | "intermediate" | "advanced" | "edge"
    tags: List[str]
    content: str
    source: str = "builtin"


# ===========================================================================
# Curated knowledge. Each lesson is self-contained and tagged for retrieval.
# ===========================================================================
BUILTIN_LESSONS: List[Lesson] = [
    # ---- Market microstructure ----
    Lesson("Liquidity & the order book", "advanced",
           ["microstructure", "liquidity", "execution", "fx", "crypto"],
           "Price moves to where liquidity is. Resting limit orders cluster at round "
           "numbers, prior highs/lows and session extremes — these are liquidity pools. "
           "Large players need counterparties, so they push price into pools to fill size "
           "(a 'stop hunt'/liquidity sweep) then reverse. Watch for a sharp wick through an "
           "obvious level that immediately reverses: that is liquidity being taken, not a "
           "real breakout. Trade the reclaim, not the spike."),
    Lesson("Spread, slippage and the cost wall", "core",
           ["costs", "execution", "fx", "crypto", "risk"],
           "Most retail 'edges' die on costs. Round-trip cost = spread + commission + "
           "slippage. If your average winner is 8 ticks and your cost is 2 ticks, you need "
           "to be right far more often than you think. Rule: never trade a system whose edge "
           "per trade isn't at least 3x its round-trip cost. Trade fewer, higher-quality "
           "setups; frequency multiplies costs linearly but rarely multiplies edge."),
    Lesson("Iceberg & absorption", "edge",
           ["microstructure", "order-flow", "tape"],
           "When price hits a level and large volume trades but price barely moves, a hidden "
           "(iceberg) order is absorbing flow. Absorption at support that then holds is a "
           "high-quality long trigger; absorption at resistance that holds is a short. This "
           "is visible on the tape/footprint, not the candle."),

    # ---- Smart money / institutional concepts ----
    Lesson("Market structure: BOS vs CHoCH", "intermediate",
           ["smc", "structure", "trend", "fx", "crypto"],
           "Uptrend = higher highs (HH) and higher lows (HL). A Break of Structure (BOS) is "
           "continuation: price takes out the prior HH. A Change of Character (CHoCH) is the "
           "first sign of reversal: in an uptrend, price breaks the most recent HL. Trade "
           "with structure; treat the first CHoCH as a warning, the confirmed reversal as "
           "the second structure break."),
    Lesson("Order blocks & fair value gaps", "advanced",
           ["smc", "order-block", "fvg", "fx"],
           "An order block is the last opposing candle before an impulsive move — the "
           "footprint of institutional positioning; price often retraces to it before "
           "continuing. A Fair Value Gap (FVG) is a 3-candle imbalance where the wicks don't "
           "overlap, marking inefficient pricing that price tends to revisit. Confluence of "
           "an order block + FVG + a swept liquidity level is a classic high-probability "
           "entry zone. None of these are magic; they are simply where stops and unfilled "
           "orders sit."),
    Lesson("Wyckoff accumulation/distribution", "advanced",
           ["wyckoff", "structure", "volume", "reversal"],
           "Ranges before big moves follow a script: in accumulation, a Selling Climax, "
           "Automatic Rally, Secondary Test, then a Spring (false breakdown that traps "
           "shorts) before markup. Distribution mirrors it with a Buying Climax and Upthrust "
           "(false breakout). The Spring/Upthrust is the tell — a failed breakout on "
           "declining volume that snaps back into the range."),

    # ---- FX session & macro edges ----
    Lesson("FX sessions and the kill zones", "intermediate",
           ["fx", "sessions", "timing", "edge"],
           "Liquidity and volatility cluster by session. Tokyo (00–08 GMT) is range-bound; "
           "London (07–16 GMT) sets the daily range and often makes the day's high or low in "
           "its first 2–3 hours; New York (12–21 GMT) and the London–NY overlap (12–16 GMT) "
           "carry the most volume. Two repeatable patterns: the London-open breakout of the "
           "Asian range, and the 'Judas swing' — a false move at session open that sweeps "
           "liquidity before the real move."),
    Lesson("Carry, rates and the COT", "advanced",
           ["fx", "carry", "macro", "positioning"],
           "FX trends are driven by interest-rate differentials: long the high-yielder, short "
           "the low-yielder earns positive swap, but the trade is short volatility — it "
           "unwinds violently in risk-off. The CFTC Commitments of Traders (COT) report shows "
           "positioning; crowded extremes (commercials vs large specs) often precede "
           "reversals. Use rates for direction, COT for crowding, price for timing."),
    Lesson("Trade the calendar, not the surprise", "intermediate",
           ["macro", "news", "events", "risk"],
           "Scheduled catalysts (FOMC, CPI, NFP, central-bank meetings) spike volatility and "
           "spreads. The edge is rarely guessing the number; it is (a) being flat or small "
           "into the print, (b) trading the *reaction* — the first clean retest after the "
           "spike — and (c) knowing that the initial move is often faded ('buy the rumor, "
           "sell the fact'). Never hold a tight stop through a red-folder release."),

    # ---- Trend following ----
    Lesson("The Turtle rules, distilled", "intermediate",
           ["trend", "breakout", "donchian", "risk"],
           "Donchian breakout: enter on a 20-day high, exit on a 10-day low (and vice versa). "
           "Size every market to the same risk using N (=ATR): units = (1% of equity) / "
           "(N × point value). Pyramid into winners every 0.5N, hard-stop at 2N. The genius "
           "wasn't the entry — it was identical volatility-normalized risk across markets and "
           "the discipline to take every signal. Trend systems win ~35–45% of trades and make "
           "money via fat right-tail winners; cutting winners short is the cardinal sin."),
    Lesson("ATR trailing & letting winners run", "core",
           ["trend", "exits", "atr", "risk"],
           "Your exit matters more than your entry. A Chandelier/ATR trailing stop (highest "
           "high − 3×ATR for longs) keeps you in trends while adapting to volatility. Fixed "
           "profit targets cap the fat tail that pays for all the small losers. If you must "
           "take partials, trail the remainder — don't fully exit a working trend."),

    # ---- Mean reversion ----
    Lesson("Connors RSI(2) reversion", "intermediate",
           ["mean-reversion", "rsi", "equities", "edge"],
           "In an uptrend (price > 200-SMA), buy short-term oversold (2-period RSI < 5–10) and "
           "exit on strength (close > 5-SMA or RSI > 70). Works because pullbacks in uptrends "
           "are bought. It is a high-win-rate, low-payoff profile — the opposite of trend "
           "following — so it must be married to strict stops or a regime filter, since the "
           "rare large loss can erase many small wins."),
    Lesson("VWAP and the opening range", "advanced",
           ["intraday", "vwap", "opening-range", "execution"],
           "Institutions benchmark to VWAP, so intraday price gravitates to it; fades back to "
           "VWAP from extremes are a staple. The opening range (first 15–30 min) sets the "
           "day's reference: a breakout-and-hold above the ORH with VWAP rising is "
           "continuation; a failed break that reclaims VWAP is a fade. Combine ORB direction "
           "with VWAP slope to avoid chop."),

    # ---- Statistical / seasonal edges ----
    Lesson("Documented calendar anomalies", "edge",
           ["seasonality", "statistical", "equities", "edge"],
           "Persistent (if decaying) anomalies: turn-of-month strength (last + first few "
           "trading days), overnight drift (most equity-index return accrues close-to-open, "
           "not intraday), the day-after-a-down-Friday tendency, and pre-holiday drift. None "
           "are huge and all need cost-aware testing, but stacked as filters they tilt odds. "
           "Treat them as confluence, never as standalone systems."),
    Lesson("Volatility mean-reverts; price trends", "advanced",
           ["volatility", "regime", "statistical"],
           "Returns have weak autocorrelation but volatility clusters and mean-reverts "
           "(GARCH). Practical uses: after a volatility spike, expect compression — size up "
           "mean-reversion, size down trend; after prolonged low vol (Bollinger squeeze), "
           "expect expansion — prepare for breakouts. Regime is the hidden variable behind "
           "'why did my system stop working': it didn't, the regime changed."),

    # ---- Risk & money management (the real edge) ----
    Lesson("Risk of ruin & why sizing dominates", "core",
           ["risk", "position-sizing", "ruin", "math"],
           "Two traders with the same 55% edge can have opposite outcomes purely from size. "
           "Risk of ruin rises sharply as risk-per-trade increases: risking 1% you can "
           "survive a 20-loss streak; risking 10% a 7-streak can end you, and streaks are "
           "longer than intuition says. Survival is non-negotiable: you cannot compound an "
           "account you blew up. Position sizing, not entries, is where most money is made and "
           "lost."),
    Lesson("Kelly and fractional Kelly", "advanced",
           ["risk", "kelly", "sizing", "math"],
           "Kelly fraction f* = edge/odds = (p·b − q)/b maximizes long-run growth but is "
           "brutally volatile and assumes you know your true edge (you don't). Real desks use "
           "fractional Kelly (¼–½) to cut variance dramatically for a small growth haircut. "
           "If Kelly says risk 8%, risking 2% is the sane translation. Over-betting a real "
           "edge still ruins you — that's the cruel part."),
    Lesson("Expectancy, R-multiples and Monte Carlo", "intermediate",
           ["risk", "expectancy", "r-multiple", "validation"],
           "Express every trade in R (multiples of initial risk). Expectancy = avg R per "
           "trade = win% × avgWinR − loss% × avgLossR; trade only positive-expectancy "
           "systems. Then Monte-Carlo-shuffle your R sequence to see the distribution of "
           "drawdowns and equity paths — your single backtest is one draw from that "
           "distribution. Plan position size around the 95th-percentile drawdown, not the "
           "one you happened to get."),

    # ---- Options ----
    Lesson("IV vs HV and the variance premium", "advanced",
           ["options", "volatility", "iv", "edge"],
           "Implied vol is usually richer than subsequently-realized vol — the variance risk "
           "premium — which is why systematically *selling* options (defined-risk: credit "
           "spreads, iron condors, the wheel) has a structural tailwind. The catch: it's a "
           "short-vol bet that pays steadily then loses big in shocks, so position size for "
           "the tail and avoid earnings/event gamma unless that's the trade."),
    Lesson("Greeks that actually drive P&L", "intermediate",
           ["options", "greeks", "theta", "gamma"],
           "Theta (time decay) pays the option seller daily and accelerates into expiry; "
           "gamma is the risk that turns a calm short-option position into a fast loser near "
           "the strike. Long options are long gamma/short theta (bleed unless the move comes "
           "fast); short options are the reverse. Skew (puts pricier than calls) reflects "
           "crash insurance demand and is itself tradable via risk reversals."),

    # ---- Crypto-specific ----
    Lesson("Funding rates & the basis trade", "advanced",
           ["crypto", "funding", "basis", "arbitrage", "edge"],
           "Perpetual futures use a funding rate to track spot: when funding is strongly "
           "positive, longs pay shorts — crowded longs, a contrarian warning and a fade/short "
           "signal at extremes. The cash-and-carry (long spot, short perp) harvests positive "
           "funding/basis as a market-neutral yield. Extreme funding + open-interest spikes "
           "frequently precede long/short squeezes; watch liquidation cascades."),
    Lesson("On-chain & exchange flows", "edge",
           ["crypto", "on-chain", "flows"],
           "Large inflows to exchanges often precede selling (coins moved to sell); sustained "
           "outflows to cold storage suggest accumulation. Stablecoin supply growth is dry "
           "powder. Realized price, MVRV and long-term-holder behavior frame cycle position. "
           "These are slow, contextual edges — they shape bias and risk, not entries."),

    # ---- Execution ----
    Lesson("Execute like a desk, not a gambler", "intermediate",
           ["execution", "twap", "vwap", "costs"],
           "Don't market-buy size into a thin book. Work orders: split into clips, use limit "
           "orders to earn rather than pay the spread, and lean on TWAP/VWAP for larger size. "
           "Avoid the first/last minutes and scheduled news when spreads blow out. Saving 1 "
           "tick per trade across thousands of trades dwarfs most 'strategy improvements'."),

    # ---- Backtesting traps (where edges go to die) ----
    Lesson("The seven deadly backtest sins", "advanced",
           ["backtest", "validation", "overfitting", "research"],
           "1) Lookahead (using data you wouldn't have had). 2) Survivorship (testing only "
           "today's winners). 3) Overfitting (too many parameters, curve-fit to noise). "
           "4) Ignoring costs/slippage. 5) Data-snooping (trying 1000 ideas, keeping the "
           "lucky one). 6) Regime blindness (a 2017 crypto system in 2022). 7) No "
           "out-of-sample. Defenses: walk-forward, purged/embargoed cross-validation, the "
           "deflated Sharpe ratio, and brutally few parameters."),
    Lesson("Overfitting and the deflated Sharpe", "edge",
           ["backtest", "overfitting", "sharpe", "statistics"],
           "Every extra parameter and every extra backtest you run inflates the best Sharpe "
           "you'll find by luck alone. The Deflated Sharpe Ratio adjusts for the number of "
           "trials and the non-normality of returns. Practical rule: if you tried N variants, "
           "your headline result needs to clear a much higher bar than a single-shot test. A "
           "simple robust system beats a complex fragile one every time live."),

    # ---- Psychology & process ----
    Lesson("Process over outcome; tilt is the enemy", "core",
           ["psychology", "discipline", "process"],
           "A good decision can lose and a bad decision can win — judge process, not single "
           "outcomes. The account-killers are emotional: revenge-trading after a loss, "
           "moving stops, oversizing to 'make it back', and abandoning a tested system after "
           "a normal drawdown. Pre-commit rules, journal every trade with the reason and the "
           "emotion, and review weekly. Trading less and smaller when uncertain is itself an "
           "edge most people refuse to use."),
    Lesson("The edges retail actually overlooks", "edge",
           ["edge", "meta", "risk", "psychology"],
           "The genuinely underused edges aren't secret indicators: (1) costs and execution "
           "quality, (2) position sizing and survival, (3) the exit — letting winners run and "
           "cutting losers, (4) doing nothing in bad regimes, (5) journaling to fix your own "
           "leaks, (6) asymmetry — seek trades that risk 1 to make 3+. People hunt for a "
           "magic entry; the money is in everything around it."),
]


# ===========================================================================
# Retrieval engine
# ===========================================================================
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "is", "it", "for",
         "on", "with", "as", "at", "by", "be", "are", "this", "that", "you",
         "your", "not", "but", "if", "into", "than", "then", "they", "their"}


def _tokens(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP and len(t) > 1]


@dataclass
class Document:
    """An ingested unit of knowledge (a lesson or a chunk of user content)."""

    id: str
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    source: str = "user"


class KnowledgeCorpus:
    """Dependency-free TF-IDF-ish retrieval over built-in + ingested knowledge."""

    def __init__(self, include_builtin: bool = True):
        self.documents: List[Document] = []
        if include_builtin:
            for i, lsn in enumerate(BUILTIN_LESSONS):
                self.documents.append(Document(
                    id=f"builtin-{i}", title=lsn.topic, content=lsn.content,
                    tags=lsn.tags + [lsn.level], source="builtin"))
        self._dirty = True
        self._df: Dict[str, int] = {}

    # -- ingestion ---------------------------------------------------------
    def ingest_text(self, content: str, title: str = "note",
                    tags: Optional[List[str]] = None, source: str = "user",
                    chunk_chars: int = 1200) -> int:
        """Add free text, split into retrievable chunks. Returns #chunks added."""
        chunks = _chunk(content, chunk_chars)
        base = len([d for d in self.documents if d.source != "builtin"])
        for j, ch in enumerate(chunks):
            self.documents.append(Document(
                id=f"{source}-{base + j}-{len(self.documents)}",
                title=f"{title}" + (f" [{j+1}/{len(chunks)}]" if len(chunks) > 1 else ""),
                content=ch, tags=tags or [], source=source))
        self._dirty = True
        return len(chunks)

    def ingest_file(self, path: str, tags: Optional[List[str]] = None) -> int:
        with open(path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
        title = os.path.basename(path)
        return self.ingest_text(content, title=title, tags=tags,
                                source=f"file:{title}")

    def ingest_directory(self, directory: str, exts=(".txt", ".md", ".csv"),
                         tags: Optional[List[str]] = None) -> int:
        total = 0
        for root, _, files in os.walk(directory):
            for name in files:
                if name.lower().endswith(exts):
                    total += self.ingest_file(os.path.join(root, name), tags=tags)
        return total

    def ingest_url(self, url: str, fetcher: Callable[[str], str],
                   tags: Optional[List[str]] = None) -> int:
        """Ingest a single URL the user points us at. `fetcher` does the HTTP/
        readability (e.g. a WebFetch wrapper) so this stays dependency-free and
        so the caller controls what gets fetched. We do not crawl or bulk-scrape."""
        text = fetcher(url)
        return self.ingest_text(text, title=url, tags=(tags or []) + ["url"],
                                source=f"url:{url}")

    # -- retrieval ---------------------------------------------------------
    def _build_index(self) -> None:
        self._df = {}
        for doc in self.documents:
            for tok in set(_tokens(doc.title + " " + " ".join(doc.tags) + " " + doc.content)):
                self._df[tok] = self._df.get(tok, 0) + 1
        self._dirty = False

    def retrieve(self, query: str, k: int = 4) -> List[Tuple[Document, float]]:
        if self._dirty:
            self._build_index()
        n = max(len(self.documents), 1)
        q_tokens = _tokens(query)
        scored: List[Tuple[Document, float]] = []
        for doc in self.documents:
            doc_tokens = _tokens(doc.title + " " + " ".join(doc.tags) + " " + doc.content)
            if not doc_tokens:
                continue
            tf: Dict[str, int] = {}
            for t in doc_tokens:
                tf[t] = tf.get(t, 0) + 1
            score = 0.0
            for qt in q_tokens:
                if qt in tf:
                    idf = math.log(1 + n / (1 + self._df.get(qt, 0)))
                    # tag/title hits weigh more
                    boost = 2.0 if qt in (doc.title + " " + " ".join(doc.tags)).lower() else 1.0
                    score += (tf[qt] / len(doc_tokens)) * idf * boost
            if score > 0:
                scored.append((doc, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def as_prompt_context(self, query: str, k: int = 4, max_chars: int = 2400) -> str:
        hits = self.retrieve(query, k)
        if not hits:
            return ""
        out = ["RELEVANT TRADING KNOWLEDGE:"]
        budget = max_chars
        for doc, _ in hits:
            snippet = doc.content[:budget]
            out.append(f"- {doc.title} ({doc.source}): {snippet}")
            budget -= len(snippet)
            if budget <= 0:
                break
        return "\n".join(out)

    # -- persistence -------------------------------------------------------
    def save(self, path: str) -> str:
        user_docs = [asdict(d) for d in self.documents if d.source != "builtin"]
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"documents": user_docs}, f, indent=2)
        return path

    def load(self, path: str) -> int:
        if not os.path.isfile(path):
            return 0
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        added = 0
        for d in data.get("documents", []):
            self.documents.append(Document(**d))
            added += 1
        self._dirty = True
        return added

    def stats(self) -> str:
        builtin = sum(d.source == "builtin" for d in self.documents)
        user = len(self.documents) - builtin
        sources = sorted({d.source.split(":")[0] for d in self.documents if d.source != "builtin"})
        return (f"Knowledge corpus: {len(self.documents)} documents "
                f"({builtin} built-in lessons, {user} ingested). "
                f"Ingested sources: {', '.join(sources) or 'none yet'}.")


def _chunk(text: str, size: int) -> List[str]:
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    # split on paragraph boundaries where possible
    paras = re.split(r"\n\s*\n", text)
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 2 <= size:
            cur += (("\n\n" if cur else "") + p)
        else:
            if cur:
                chunks.append(cur)
            if len(p) <= size:
                cur = p
            else:
                for i in range(0, len(p), size):
                    chunks.append(p[i:i + size])
                cur = ""
    if cur:
        chunks.append(cur)
    return chunks
