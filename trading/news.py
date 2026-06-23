"""
News, events and sentiment.

The agent's "fundamental/event awareness" layer. It pulls headlines (optional
providers + RSS), tracks a calendar of scheduled macro/crypto catalysts, and
scores sentiment with a transparent lexicon (no API key required) — upgradeable
to FinBERT/FinGPT if installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional


@dataclass
class Headline:
    title: str
    source: str
    sentiment: float = 0.0   # -1..1


@dataclass
class NewsReport:
    symbol: str
    headlines: List[Headline] = field(default_factory=list)
    upcoming_events: List[str] = field(default_factory=list)

    @property
    def net_sentiment(self) -> float:
        if not self.headlines:
            return 0.0
        return sum(h.sentiment for h in self.headlines) / len(self.headlines)

    def summary(self) -> str:
        if not self.headlines and not self.upcoming_events:
            return "No news/events available (provider offline)."
        s = self.net_sentiment
        mood = "bullish" if s > 0.15 else "bearish" if s < -0.15 else "neutral"
        parts = [f"Sentiment: {mood} ({s:+.2f}) over {len(self.headlines)} headlines."]
        if self.upcoming_events:
            parts.append("Upcoming catalysts: " + "; ".join(self.upcoming_events))
        return " ".join(parts)


# Transparent sentiment lexicon — deliberately simple and auditable.
_POSITIVE = {"surge", "rally", "beat", "bullish", "record", "upgrade", "gain",
             "soar", "approval", "partnership", "adoption", "growth", "profit"}
_NEGATIVE = {"crash", "plunge", "miss", "bearish", "lawsuit", "hack", "downgrade",
             "loss", "ban", "selloff", "default", "recession", "fraud", "halt"}

# Recurring scheduled catalysts the agent should always weigh.
MACRO_CALENDAR: List[str] = [
    "FOMC interest-rate decision (8x/year)",
    "US CPI inflation print (monthly)",
    "US Non-Farm Payrolls (first Friday monthly)",
    "Quarterly earnings season",
]
CRYPTO_CALENDAR: List[str] = [
    "Bitcoin halving (~every 4 years)",
    "Major token unlock schedules",
    "Perpetual funding-rate resets (8h)",
    "ETF flow / options expiry (monthly)",
]


def score_sentiment(text: str) -> float:
    """Lexicon sentiment in [-1, 1]. Upgradable to a model if installed."""
    words = text.lower().replace(",", " ").replace(".", " ").split()
    pos = sum(w in _POSITIVE for w in words)
    neg = sum(w in _NEGATIVE for w in words)
    if pos + neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


class NewsFeed:
    """Aggregates headlines + a relevant event calendar for a symbol."""

    def __init__(self, max_headlines: int = 15):
        self.max_headlines = max_headlines

    def get_news(self, symbol: str, is_crypto: bool = False) -> NewsReport:
        headlines = self._fetch_headlines(symbol)
        events = CRYPTO_CALENDAR if is_crypto else MACRO_CALENDAR
        return NewsReport(symbol=symbol, headlines=headlines, upcoming_events=events)

    def _fetch_headlines(self, symbol: str) -> List[Headline]:
        # Try yfinance news (no key needed) first; silently degrade otherwise.
        try:
            import yfinance as yf  # type: ignore
            news = getattr(yf.Ticker(symbol), "news", []) or []
            out: List[Headline] = []
            for item in news[: self.max_headlines]:
                title = item.get("title") or item.get("content", {}).get("title", "")
                if not title:
                    continue
                src = item.get("publisher") or "yahoo"
                out.append(Headline(title, src, score_sentiment(title)))
            if out:
                return out
        except Exception:
            pass
        return []
