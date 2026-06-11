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

    # ---- Elliott Wave ----
    Lesson("Elliott Wave theory — practical use", "advanced",
           ["elliott-wave", "structure", "wave", "fibonacci"],
           "Markets move in 5-wave impulses (1-2-3-4-5) in the trend direction and 3-wave "
           "corrections (A-B-C) against it. Wave 3 is the longest and strongest (never the "
           "shortest); wave 2 can't retrace more than 100% of wave 1; wave 4 shouldn't "
           "overlap wave 1's price territory in a standard impulse. Fibonacci ratios govern "
           "expected retracements: wave 2 often retraces 61.8% of wave 1; wave 4 often "
           "retraces 38.2%. Extensions: wave 3 targets 1.618× wave 1; wave 5 often equals "
           "wave 1 or 0.618 × (1+3). Practical use: don't count waves obsessively — instead "
           "use the structure to frame whether a pullback is a corrective ABC (tradeable in "
           "trend direction) or the start of a reversal."),

    # ---- Market Profile & TPO ----
    Lesson("Market Profile & TPO charts", "advanced",
           ["market-profile", "tpo", "volume-profile", "intraday", "institutional"],
           "Market Profile organizes price by time spent at each level (Time Price "
           "Opportunities). The Point of Control (POC) is where most time/volume was spent — "
           "a fair value anchor. The Value Area (VA) holds 70% of the session's trades "
           "(±1 sigma around POC). Prices outside the VA tend to auction back toward it, "
           "while sustained acceptance outside VA signals trend extension. Key trade: "
           "rejection from VA High or VA Low back into range is a high-probability fade; "
           "a gap open outside the prior VA that holds signals a breakout and trend day. "
           "Single prints (gaps in the profile) act as magnets on revisit."),

    # ---- Volume Profile ----
    Lesson("Volume Profile: POC, VAH, VAL and low-volume nodes", "advanced",
           ["volume-profile", "poc", "vah", "val", "institutional"],
           "Volume Profile shows how much volume traded at each price (not time). High-Volume "
           "Nodes (HVN/POC) are price magnets: market slows down here because both sides are "
           "comfortable. Low-Volume Nodes (LVN) are air pockets: price travels through them "
           "quickly because there's little two-sided business. Trade plan: "
           "(1) longs at LVN above a HVN with price holding the HVN as support, "
           "(2) shorts at LVN below a HVN with price rejecting from the HVN, "
           "(3) stop below/above the HVN. The Visible Range POC (VPOC) of the prior "
           "session/week is a must-watch level for overnight/opening gaps."),

    # ---- Options flow & dealer gamma ----
    Lesson("Dealer gamma exposure and market pinning", "edge",
           ["options", "gamma", "dealer", "pinning", "flow"],
           "Market makers (dealers) who sell options must delta-hedge: when you buy a call, "
           "the dealer is short that call and buys the underlying to stay delta-neutral. "
           "Near expiry with large open interest at a strike, dealers chase price up AND "
           "down ('gamma pinning') — price gets sucked to the max-pain / peak-OI strike. "
           "When dealers are short gamma (net long puts/calls in the market), their hedging "
           "amplifies moves — they buy as price rises and sell as it falls (procyclical). "
           "When long gamma, they dampen moves (countercyclical). Track GEX (gamma exposure) "
           "at major option strikes via CBOE data or SpotGamma; low-GEX environments see "
           "larger, faster moves. Key: options expiry (OpEx) Fridays can see large reversals "
           "as gamma is repriced."),

    # ---- Pairs trading / statistical arbitrage ----
    Lesson("Pairs trading and cointegration", "advanced",
           ["pairs-trading", "statistical-arb", "cointegration", "hedge"],
           "Two assets are cointegrated if their spread (ratio or difference) is stationary "
           "— it mean-reverts. Test with the Engle-Granger two-step: regress asset A on B, "
           "test residuals for stationarity (ADF test). If stationary (ADF p < 0.05), trade "
           "the spread: go long the underperformer, short the outperformer when Z-score of "
           "spread > 2; close at Z-score < 0.5. Classic pairs: BTC/ETH, Gold/Silver, "
           "ES/NQ, similar-sector stocks (KO/PEP). Risk: the pair 'breaks down' during "
           "regime changes — always use stops on the spread itself (e.g. 3σ adverse move). "
           "Cointegrated pairs profit from the reversion, not direction, so returns are "
           "uncorrelated to market beta."),

    # ---- Dark pool / block prints ----
    Lesson("Dark pools and off-exchange block prints", "edge",
           ["dark-pool", "block-trade", "institutional", "flow"],
           "Over 40% of US equity volume is executed off-exchange (dark pools, ATS) to "
           "minimize market impact. A 'dark pool print' appearing on the tape is a large "
           "block trade that typically represents institutional conviction. Bullish signals: "
           "large block prints at or near the offer, especially on down-days; aggressive "
           "size on upticks. Bearish: large prints at the bid on up-days. Services like "
           "Cheddar Flow, Unusual Whales and Dark Pool Levels track these. The key insight: "
           "institutions use dark pools to enter quietly — when a block finally prints on "
           "tape, they are already positioned and the street is starting to notice. That "
           "flow tends to persist for days."),

    # ---- Fibonacci levels ----
    Lesson("Fibonacci retracements and extensions — the actual use", "intermediate",
           ["fibonacci", "retracement", "extension", "levels"],
           "Fibonacci levels (23.6%, 38.2%, 50%, 61.8%, 78.6%) are self-fulfilling because "
           "enough participants use them — making them useful as clusters to watch, not magic "
           "numbers. Key rationale: 61.8% (the golden ratio reciprocal) is where impulsive "
           "markets most often pause before resuming; 78.6% is the last line before a full "
           "retrace. Extensions (127.2%, 161.8%, 261.8%) project targets. Best practice: "
           "treat Fibonacci as a zone, not a price; a level only matters if it coincides "
           "with structure (prior high/low), a moving average, or a volume shelf. Confluences "
           "of two or more Fibonacci levels from different swings (a 'Fibonacci cluster') "
           "are the most reliable turning zones."),

    # ---- Pivot points ----
    Lesson("Pivot points and CPR: the intraday road map", "intermediate",
           ["pivot-points", "cpr", "support-resistance", "intraday"],
           "Classic daily pivots (P, R1-R3, S1-S3) calculated from the prior day's HLC are "
           "watched by floor traders and algo desks. The Central Pivot Range (CPR = prior "
           "TC, PP, BC) is the most important zone: narrow CPR (Trending day) vs wide CPR "
           "(Sideways day) sets the session bias before the open. Rules: (1) opening above "
           "CPR and holding it → buy dips to CPR; (2) below CPR → sell rallies to CPR; "
           "(3) first time price revisits R1/S1 is a high-probability reversal zone; "
           "(4) if price opens in CPR and churns, a range day is likely — trade range, "
           "not breakout. Weekly and monthly pivots serve as the next magnets when daily "
           "structure breaks."),

    # ---- Relative Strength & Sector Rotation ----
    Lesson("Relative strength rotation and sector ETF flows", "intermediate",
           ["relative-strength", "sector-rotation", "etf", "equities"],
           "In bull markets, money rotates through sectors in a predictable cycle: early "
           "recovery → Financials, Tech; expansion → Industrials, Materials; late cycle → "
           "Energy, Consumer Staples; recession → Utilities, Healthcare. The practical edge: "
           "buy the sectors just starting to outperform the index (RS turning up from below "
           "100 on a relative chart) and cut the ones starting to underperform. Relative "
           "strength of individual stocks vs their sector matters more than absolute price: "
           "a stock that holds up while its sector drops is showing institutional support "
           "and is a buy on sector recovery. RS lines making new highs before price makes "
           "new highs is a leading confirmation."),

    # ---- Volume Spread Analysis ----
    Lesson("Volume Spread Analysis (VSA): Wyckoff in practice", "advanced",
           ["vsa", "volume", "wyckoff", "microstructure"],
           "VSA reads price candles relative to their volume to identify professional "
           "activity. Key VSA signals: "
           "(1) Up-bar on ultra-high volume but narrow spread and close near low = "
           "distribution (supply has entered; bearish). "
           "(2) Down-bar on ultra-high volume with close near high = 'selling climax' "
           "— supply absorbed; potential bottom. "
           "(3) Up-bar on very low volume = 'no demand' — weak, expect a stall or reversal. "
           "(4) Down-bar on very low volume = 'no supply' — weak sellers; expect a bounce. "
           "The key is comparing the bar's spread and close position with its volume "
           "relative to recent bars. VSA explains *why* a level holds or breaks."),

    # ---- Intermarket analysis ----
    Lesson("Intermarket analysis: bonds, dollar, gold and commodities", "advanced",
           ["intermarket", "macro", "bonds", "dollar", "gold"],
           "Markets are interconnected; ignoring cross-asset signals is a blind spot. "
           "Core relationships (which break and rebuild): "
           "(1) Dollar ↑ → commodities ↓ (priced in USD), Emerging Markets ↓. "
           "(2) Yields ↑ (bond prices ↓) → growth stocks hurt more than value (duration). "
           "(3) Gold moves inversely to real yields (TIP/TLT spread); if real yields fall, "
           "gold likely rallies regardless of nominal rates. "
           "(4) Copper is the 'PhD in economics' — its strength leads cyclical stocks. "
           "(5) Credit spreads (HYG vs IEI) lead equity risk: spreads widening before "
           "equity falls is an early warning. "
           "Use these as regime filters, not entries; divergences between correlated "
           "markets are the high-value signal."),

    # ---- Currency correlations ----
    Lesson("Currency correlations and commodity currencies", "intermediate",
           ["fx", "correlations", "commodity-currencies", "cad", "aud", "nzd"],
           "Pairs aren't independent: EURUSD and GBPUSD are ~70–80% correlated (common "
           "dollar leg). Trading both simultaneously doubles exposure. AUD, CAD and NZD "
           "are commodity currencies: AUD tracks iron ore and Chinese PMI; CAD tracks crude "
           "oil; NZD tracks dairy and risk appetite. JPY is the safe-haven; it strengthens "
           "in risk-off as carry trades unwind (AUDJPY is almost a pure risk barometer). "
           "CHF is a safe haven pegged historically to EUR. DXY (dollar index) is 57% EUR, "
           "so it's nearly the inverse of EURUSD. Key pairs for carry: NZDJPY, AUDJPY "
           "— long in risk-on trends, crash hard in risk-off."),

    # ---- Central bank interventions ----
    Lesson("Central bank intervention signals and impact", "edge",
           ["fx", "central-bank", "intervention", "boj", "snb", "macro"],
           "Central banks intervene to cap volatility or defend levels. Warning signs: "
           "(1) Japan: MOF/BOJ verbal warnings ('we're watching closely') precede action; "
           "USDJPY at 150+ historically triggers FX intervention. Watch the 'rate of change' "
           "— the BOJ reacts to speed, not level. "
           "(2) SNB: Swiss franc pegged operations; EURCHF near 0.92–0.93 has historically "
           "triggered floor-defense rhetoric. "
           "(3) EM central banks: Brazil, Turkey intervene via banks; look for unnatural "
           "stabilization in spot while forwards widen. "
           "Practical: never hold tight stops into suspected intervention zones. The initial "
           "intervention spike is often faded as speculative shorts test resolve, but the "
           "second intervention usually sticks."),

    # ---- Crypto: MEV & sandwich attacks ----
    Lesson("Crypto: MEV, sandwich attacks and DEX execution", "edge",
           ["crypto", "defi", "mev", "dex", "execution"],
           "Maximal Extractable Value (MEV) is value extracted by reordering/inserting "
           "transactions in a block. The 'sandwich attack': a bot sees your large pending "
           "DEX swap, front-runs it (buys first to push price up), lets your trade fill at "
           "worse price, then sells. This taxes large market-order DEX traders silently. "
           "Mitigations: (1) use limit orders on DEXes; (2) set low slippage tolerance; "
           "(3) use Flashbots Protect / private mempools; (4) break large orders into clips. "
           "For CEX traders: MEV is less of a concern but front-running by HFT firms on "
           "thin books is analogous. The lesson: on DEXes, your transaction is public and "
           "predatory bots watch the mempool in real time."),

    # ---- Crypto: whale tracking ----
    Lesson("Crypto whale tracking and on-chain signals", "edge",
           ["crypto", "on-chain", "whales", "flows", "glassnode"],
           "On-chain data provides the crypto-specific edge. Key metrics: "
           "(1) Whale wallets (>1,000 BTC) accumulating = quiet institutional buying. "
           "(2) Exchange inflows spike → coins moved to sell; outflows → moved to hold. "
           "(3) MVRV Z-score: MVRV > 3.5 historically marks tops; < 0 marks bottoms. "
           "(4) Realized price: below spot → most holders in profit (fragile, prone to "
           "distribution); above spot → underwater, miners may sell. "
           "(5) Long-term holder (LTH) supply decreasing = distribution top signal. "
           "(6) Funding rates: sustained extreme positive funding (>0.1%/8h) precedes "
           "long squeezes; extreme negative → short squeeze risk. "
           "Sources: Glassnode, CryptoQuant, Santiment. These are bias-setters over days–weeks."),

    # ---- Regime-adaptive position sizing ----
    Lesson("Regime-adaptive position sizing", "advanced",
           ["regime", "sizing", "volatility", "risk", "kelly"],
           "One fixed risk-per-trade is suboptimal across regimes. The adaptive approach: "
           "(1) In a trending regime (ADX >25): full size, ATR trailing stop — let winners run. "
           "(2) In a ranging regime (ADX <20): half size, fixed profit target at resistance/support. "
           "(3) In a high-volatility regime (ATR% >3×normal): quarter size, wider stops, "
           "accept that slippage will be worse. "
           "(4) After a drawdown >10%: reduce to half size until account recovers to prior equity. "
           "This is 'volatility targeting': size inversely to ATR so each trade risks roughly "
           "the same dollar amount regardless of how choppy the market is. The mechanism: "
           "risk amount = equity × risk% / ATR_in_dollars. This is the professional norm."),

    # ---- Drawdown management & recovery ----
    Lesson("Drawdown management and account recovery protocols", "core",
           ["drawdown", "risk", "recovery", "psychology", "sizing"],
           "Every system has drawdowns; the question is whether they kill your account or "
           "you survive them. Protocol: "
           "(1) Pre-define a maximum drawdown limit (20% is typical) — if hit, stop trading "
           "and diagnose before resuming. "
           "(2) At 50% of max-drawdown, halve position size automatically. "
           "(3) During drawdown, check whether the edge has disappeared (regime change) or "
           "it's a normal system drawdown within historical bounds — these require different "
           "responses. (4) Recovery math: a 20% drawdown requires a 25% gain to return to HWM; "
           "a 50% drawdown requires 100%. Trying to recover too fast with oversizing is the "
           "most common cause of account death. The only safe path is grinding back at reduced size. "
           "(5) Journal every drawdown trade — the pattern almost always reveals a single "
           "behavioral leak (revenge trading, session-end FOMO, macro event ignoring)."),

    # ---- Pre/post market gaps ----
    Lesson("Pre/post-market behavior, gaps and the opening rotation", "intermediate",
           ["gaps", "premarket", "equities", "intraday", "opening"],
           "Equity gaps (opening price differs from prior close) are among the most studied "
           "edges in market microstructure. Types: "
           "(1) Common gap (<0.5%) — fills quickly; usually faded. "
           "(2) Breakaway gap — leaves a consolidation on high volume; often doesn't fill "
           "for weeks. Trade the pullback to the gap's edge. "
           "(3) Runaway/measurement gap — mid-trend; project equal move from breakout as target. "
           "(4) Exhaustion gap — late in trend on climactic volume; reversal signal. "
           "Opening gap fade: stocks gapping >2% on no news fill the gap 60–70% of the time "
           "within the session — a mean-reversion edge. Gap-and-go: confirmed volume expansion "
           "above the gap high in the first 30 min → momentum trade, target prior resistance. "
           "Pre-market thin liquidity makes spread cost important; wait for regular market open."),

    # ---- Earnings season ----
    Lesson("Earnings season patterns and option strategies", "intermediate",
           ["earnings", "options", "equities", "events", "iv"],
           "Options IV rises into earnings (inflating premium) then collapses after the print "
           "('IV crush'). Strategies: "
           "(1) Straddle into earnings profits only if the move exceeds the implied move "
           "(the expected move priced by the ATM straddle). Most retail traders overpay here — "
           "study average actual vs implied moves by ticker before playing. "
           "(2) Selling the earnings straddle (short vol) has a structural positive edge over "
           "time but risks catastrophic single-name loss; use iron condors with defined risk. "
           "(3) Pre-earnings drift: many stocks drift in the direction of the eventual move for "
           "1–2 weeks before the report — a weak but consistent pattern. "
           "(4) The first post-earnings report is often the most volatile; by the third beat "
           "the market expects it and the reaction is muted."),

    # ---- Index rebalancing front-running ----
    Lesson("Index rebalancing and front-running reconstitution", "edge",
           ["indexing", "rebalancing", "flow", "equities", "arbitrage"],
           "When a stock is added to a major index (S&P 500, Russell, MSCI), every passive "
           "fund must buy it at or before the effective date. This creates massive, "
           "predictable demand. Edge: buy the announced-but-not-yet-added stock immediately "
           "on announcement; sell into the passive inflows on effective date. The same works "
           "in reverse for deletions. Effect size varies: S&P 500 adds see 5–10% on "
           "announcement average, partly given back over following weeks. Russell reconstitution "
           "(June) is the most liquid opportunity; small-cap additions/deletions move 10–20%. "
           "Also: month-end and quarter-end rebalancing by multi-asset funds creates "
           "predictable flows in equity/bond ratios — sell equities that have outperformed "
           "at quarter-end as funds rebalance back."),

    # ---- Portfolio factor exposures ----
    Lesson("Factor investing: momentum, value, quality and carry", "advanced",
           ["factors", "quant", "momentum", "value", "quality", "carry"],
           "Systematic factors are persistent, risk-compensated return premia. The main ones: "
           "(1) Momentum: buy recent winners (12-month return minus last month), short losers. "
           "Works across asset classes. Risk: reversal at extremes and crash-risk in crowded "
           "unwinds. Use a 6–12 month lookback and rebalance monthly. "
           "(2) Value: buy cheap assets (P/B, P/E, EV/EBITDA) vs expensive; works slowly. "
           "(3) Quality: buy high ROE, low leverage, stable earnings. Defensive and boring. "
           "(4) Carry: long high-yielding assets, short low-yielding (FX carry, bond term "
           "premium, option premium harvesting). "
           "(5) Low volatility: lower-vol stocks outperform on risk-adjusted basis (the "
           "volatility anomaly). "
           "Real desks combine multiple factors to reduce drawdowns from any single factor "
           "blowup. Be aware of factor crowding risk — when too much capital chases the same "
           "signal, reversals are violent."),

    # ---- Order flow imbalance ----
    Lesson("Order flow imbalance and footprint charts", "edge",
           ["order-flow", "footprint", "microstructure", "tape", "imbalance"],
           "Order flow imbalance (OFI) measures whether aggressive buyers or sellers are "
           "dominant: OFI = buyer-initiated volume − seller-initiated volume. Persistent "
           "positive OFI at a support zone is institutional accumulation; negative OFI at "
           "resistance is distribution. Footprint charts show bid/ask volume at each tick — "
           "a 'stacked imbalance' (3+ consecutive price levels showing 3:1+ buy/sell ratio) "
           "is a high-probability continuation signal used by prop traders. Delta divergence: "
           "price makes a new high but cumulative delta (OFI) does not — absorption at the "
           "top, fade signal. Requires order flow software (Sierra Chart, Bookmap, Quantower) "
           "and is most useful on liquid futures and crypto."),

    # ---- Intraday time-of-day patterns ----
    Lesson("Time-of-day patterns and session timing edges", "intermediate",
           ["intraday", "timing", "sessions", "tod", "edge"],
           "Markets have repeatable time-of-day behaviors: "
           "(1) 9:30–10:00 ET (US equity open): highest volume, widest spreads, most false "
           "breakouts — amateurs react to overnight news; pros wait for the dust to settle. "
           "(2) 10:00–11:30 ET: first trend of the day establishes; ORB signals valid here. "
           "(3) 11:30–13:00 ET: lunch lull — volume drops, choppy, avoid unless playing "
           "mean-reversion in established range. "
           "(4) 13:00–15:00 ET: NYSE afternoon trend — often the same direction as morning. "
           "(5) 15:00–16:00 ET: MOC (market-on-close) flows distort; gaps sometimes fill in "
           "last 30 min. "
           "FX: avoid trading 30 min before/after major economic releases. "
           "Crypto: BTC often moves at 4:00, 8:00, 12:00, 16:00 UTC (hourly option expiry). "
           "Statistical rule: most equity-index upward drift happens overnight (close-to-open)."),

    # ---- Advanced candlestick patterns ----
    Lesson("Advanced candlestick patterns: three-bar and reversal clusters", "intermediate",
           ["candlestick", "patterns", "reversal", "continuation"],
           "Beyond the basic Doji and Engulfing: "
           "(1) Morning Star (3 bars): big red candle, then a small-bodied doji/spinning top, "
           "then a big green close above midpoint of first candle — powerful bottoming pattern. "
           "Evening Star is the mirror. "
           "(2) Three White Soldiers: three consecutive long green candles each closing near "
           "their highs — strong bullish continuation after a decline. Inverse: Three Black Crows. "
           "(3) Bullish/Bearish Harami: small candle body inside the prior large body — "
           "indecision and potential reversal, needs confirmation. "
           "(4) Island Reversal: a gap up, a session of small bars, then a gap back down "
           "(or vice versa) — rare but extremely reliable exhaustion pattern. "
           "(5) Tweezer tops/bottoms: two consecutive bars sharing the exact same high/low "
           "— precise resistance/support, common in FX at round numbers. "
           "Rule: multi-bar patterns need at least one of: volume confirmation, proximity to "
           "a key level, or divergence on an oscillator."),

    # ---- DXY and macro dollar impact ----
    Lesson("DXY, the dollar cycle and cross-asset impact", "advanced",
           ["dollar", "dxy", "macro", "fx", "intermarket"],
           "The US dollar (DXY) is the world's reserve currency; its direction ripples through "
           "every asset class. Dollar strength: EM equities fall (dollar debt more expensive), "
           "commodities fall (USD-priced), gold falls (unless real yields also fall), "
           "EURUSD/GBPUSD fall, crypto often pressured. Dollar weakness: the opposite. "
           "Dollar cycles: Fed rate hike cycles → dollar bull; easing cycles → dollar bear "
           "(but the actual turn often comes 6–12 months before the first cut, as the market "
           "prices in a peak). The DXY is 57% EUR, so it's nearly EURUSD inverted. "
           "For FX traders: watch the DXY trend on the weekly chart to frame all USD pairs. "
           "Key catalysts: FOMC, CPI, NFP. Reserve manager demand for USD is a secular "
           "tailwind that makes DXY declines slow and rally fast."),

    # ---- High-frequency structure ----
    Lesson("HFT and market microstructure impact for retail traders", "advanced",
           ["hft", "microstructure", "spread", "queue", "execution"],
           "HFT firms provide liquidity but also extract it. Key microstructure facts for "
           "retail participants: "
           "(1) Price improvement: retail orders routed to market makers often get fills "
           "inside the spread (payment for order flow), but at cost of potential adverse "
           "selection. "
           "(2) Queue priority: on limit-order-driven venues, time is secondary to price; "
           "front-of-queue limit orders fill first. HFTs with co-location cancel and re-post "
           "at sub-millisecond speed. "
           "(3) Momentum ignition: HFTs sometimes trigger cascades to fill positions at "
           "better prices — these look like stop hunts on the tape. "
           "(4) For retail: use limit orders; avoid market orders in thin conditions; "
           "slice size into natural clips (don't advertise full size); never trade the open "
           "auction if you're not sure of the price. "
           "(5) Crypto: HFTs dominate CEX top-of-book; DEX has MEV instead. "
           "Your edge vs HFTs is patience and information, not speed."),

    # ---- Gamma scalping ----
    Lesson("Gamma scalping and delta-hedging strategies", "advanced",
           ["options", "gamma", "delta", "hedging", "scalping"],
           "Long gamma positions (long options) benefit from large moves in either direction. "
           "Gamma scalping: buy a straddle (long calls + puts), then delta-hedge by selling "
           "the underlying when it rises and buying when it falls. Each hedge books a gain "
           "proportional to gamma × move². This P&L from delta-hedging offsets theta decay "
           "if realized vol > implied vol. If RV < IV you lose. The trade is a pure bet on "
           "RV vs IV. Short gamma (selling options) is the mirror: collect theta, lose from "
           "hedging in volatile markets. Practical rule for non-options-specialists: sell "
           "options when IV rank is in the top 25% of its 52-week range (rich premium) and "
           "buy when in the bottom 25% (cheap). Never sell naked gamma into known catalysts."),

    # ---- Regime detection ----
    Lesson("Market regime detection: ADX, ATR and EMA stacks", "advanced",
           ["regime", "adx", "atr", "trend", "ranging", "volatility"],
           "No single strategy works in all regimes. Before choosing a strategy, classify the "
           "regime: "
           "(1) Trending (ADX >25, EMAs aligned): MA crossovers, Donchian breakouts, Turtle "
           "systems work; mean-reversion fails and bleeds. "
           "(2) Ranging (ADX <20, price ping-ponging between levels): RSI/Stochastic reversals "
           "at extremes, BB mean-reversion, pivot-point fades work; trend-following whipsaws. "
           "(3) High-volatility (ATR% >3× baseline): everything struggles; reduce size to half, "
           "widen stops by 1.5×. Avoid scalping. "
           "(4) Low-volatility compression (ATR% <0.5×, BB squeeze): wait for the breakout; "
           "position for expansion direction. "
           "Implementation: compute ADX, ATR as % of price, and whether 20/50/200 EMAs are "
           "stacked. Use these three inputs to classify regime; switch strategy accordingly. "
           "Re-classify at least weekly for daily-bar traders, daily for intraday."),

    # ---- News and sentiment ----
    Lesson("News-driven sentiment and the narrative lifecycle", "intermediate",
           ["news", "sentiment", "narrative", "macro", "events"],
           "Prices move on information flow, but the response to news follows a lifecycle: "
           "(1) Anticipation: smart money positions before the print. "
           "(2) Release: initial spike on the headline. "
           "(3) Re-analysis: the market reads the detail (revision, forward guidance) — "
           "this often reverses the initial spike. "
           "(4) Persistence: if the underlying narrative changes (not just the data), "
           "the trend reasserts. "
           "Trading the news directly is the hardest game — you're competing with algos "
           "reading the release in microseconds. Better approaches: (a) trade the reaction "
           "not the release — wait for the first 1–5 minutes to resolve, then trade the "
           "sustained direction; (b) play the narrative lifecycle — buy what the market "
           "was positioned for before the print if the print was neutral; "
           "(c) use news as a regime filter, not as a trigger."),

    # ---- Tax efficiency ----
    Lesson("Tax efficiency in active trading", "core",
           ["tax", "efficiency", "structure", "wash-sale", "jurisdiction"],
           "Taxes are the largest avoidable cost for profitable traders. Key considerations: "
           "(1) Short-term capital gains are taxed as ordinary income in the US (up to 37%) "
           "vs long-term (15–20%). Holding >1 year on a winner is a decision to make with a "
           "taxable account but not a tax-deferred one (IRA, 401k). "
           "(2) Wash sale rule (US): you cannot harvest a loss and immediately repurchase the "
           "substantially identical security within 30 days. A common violation: harvest a "
           "stock loss, buy the same stock back next week. "
           "(3) Section 1256 contracts (futures, forex futures, some ETFs): 60% long-term / "
           "40% short-term regardless of holding period — major advantage for active traders. "
           "(4) Mark-to-market election (Section 475): traders can elect to treat all gains "
           "as ordinary income and deduct all losses vs 3,000 capital loss cap. "
           "(5) In jurisdictions with no capital gains tax (Dubai, Singapore, Switzerland): "
           "taxation framework changes strategy — more compounding, less turnover minimization. "
           "Consult a trader-specialist CPA; structure decisions should be made with an advisor."),

    # ---- Monte Carlo forward simulation ----
    Lesson("Monte Carlo simulation and forward-looking risk", "advanced",
           ["monte-carlo", "risk", "simulation", "validation", "drawdown"],
           "Your backtest produced one equity path, but your actual trading will produce a "
           "random draw from the distribution of possible paths. Monte Carlo simulation: "
           "(1) Collect your system's R-multiples from backtests. "
           "(2) Randomly sample (with replacement) N trades to simulate one path. "
           "(3) Repeat 1,000+ times. "
           "(4) From the distribution: look at the 95th-percentile max drawdown and the "
           "5th-percentile final equity. Size positions so the worst realistic drawdown "
           "(95th pct) is within your acceptable loss. "
           "Practical findings: most retail traders dramatically underestimate drawdown depth. "
           "A system with 55% win rate and 1:1 R:R will still regularly see 20+ consecutive "
           "loss-heavy sequences. The Monte Carlo provides psychological preparation: you "
           "WILL see these drawdowns even in a working system — the question is whether "
           "you sized so you can survive them."),
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
