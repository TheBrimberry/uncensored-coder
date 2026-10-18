"""
Trade journal & performance analytics.

Ingests your past trading data (CSV / JSON / broker fills / backtest results),
computes the metrics that actually matter, breaks performance down by symbol /
strategy / direction / time, and *diagnoses weaknesses* into concrete, actionable
recommendations the auto-tuner can act on.

The CSV loader is forgiving: it accepts common column names (and aliases) and
computes P&L from entry/exit if a pnl column isn't present.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


# Column aliases the CSV loader understands (lower-cased, stripped).
_ALIASES = {
    "symbol": {"symbol", "ticker", "instrument", "pair", "market", "asset"},
    "direction": {"direction", "side", "type", "action", "position"},
    "entry_price": {"entry_price", "entry", "open_price", "openprice", "price_in", "buy_price"},
    "exit_price": {"exit_price", "exit", "close_price", "closeprice", "price_out", "sell_price"},
    "qty": {"qty", "quantity", "size", "volume", "units", "amount", "lots"},
    "pnl": {"pnl", "profit", "p&l", "pl", "net", "netpnl", "realized", "result"},
    "fees": {"fees", "fee", "commission", "cost", "costs"},
    "strategy": {"strategy", "bot", "system", "setup", "model"},
    "entry_time": {"entry_time", "open_time", "opened", "date", "datetime", "time", "timestamp"},
    "exit_time": {"exit_time", "close_time", "closed"},
}

_LONG_WORDS = {"long", "buy", "b", "1", "+1", "bull"}
_SHORT_WORDS = {"short", "sell", "s", "-1", "bear"}


@dataclass
class TradeRecord:
    symbol: str
    direction: str                       # "long" | "short"
    entry_price: float = 0.0
    exit_price: float = 0.0
    qty: float = 1.0
    pnl: Optional[float] = None          # explicit P&L overrides computed
    fees: float = 0.0
    strategy: Optional[str] = None
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None

    @property
    def net_pnl(self) -> float:
        if self.pnl is not None:
            return self.pnl - self.fees
        sign = 1.0 if self.direction == "long" else -1.0
        return sign * (self.exit_price - self.entry_price) * self.qty - self.fees

    @property
    def return_pct(self) -> float:
        notional = abs(self.entry_price) * self.qty
        if notional <= 0:
            return 0.0
        return self.net_pnl / notional * 100.0

    @property
    def is_win(self) -> bool:
        return self.net_pnl > 0

    def weekday(self) -> Optional[str]:
        ts = self._parse_time(self.entry_time)
        return ts.strftime("%A") if ts else None

    def hour(self) -> Optional[int]:
        ts = self._parse_time(self.entry_time)
        return ts.hour if ts else None

    @staticmethod
    def _parse_time(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M",
                    "%Y-%m-%d", "%m/%d/%Y %H:%M", "%m/%d/%Y", "%d/%m/%Y %H:%M",
                    "%d/%m/%Y"):
            try:
                return datetime.strptime(value.strip(), fmt)
            except (ValueError, AttributeError):
                continue
        return None


@dataclass
class Insight:
    """A diagnosed weakness + a concrete recommendation."""

    severity: str                        # "high" | "medium" | "low"
    area: str                            # e.g. "direction", "symbol", "risk"
    message: str
    suggestion: str
    param_hint: Dict[str, object] = field(default_factory=dict)  # machine-actionable


@dataclass
class PerformanceReport:
    n_trades: int
    win_rate: float
    profit_factor: float
    expectancy: float                    # avg net P&L per trade
    total_pnl: float
    avg_win: float
    avg_loss: float
    payoff_ratio: float                  # avg_win / |avg_loss|
    max_drawdown: float                  # on cumulative P&L curve
    sharpe: float
    by_symbol: Dict[str, float] = field(default_factory=dict)
    by_strategy: Dict[str, float] = field(default_factory=dict)
    by_direction: Dict[str, float] = field(default_factory=dict)
    by_weekday: Dict[str, float] = field(default_factory=dict)
    insights: List[Insight] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            "=== PERFORMANCE REVIEW ===",
            f"Trades: {self.n_trades} | Win rate: {self.win_rate:.1%} | "
            f"Profit factor: {self.profit_factor:.2f}",
            f"Total P&L: {self.total_pnl:+.2f} | Expectancy/trade: {self.expectancy:+.2f}",
            f"Avg win: {self.avg_win:+.2f} | Avg loss: {self.avg_loss:+.2f} | "
            f"Payoff: {self.payoff_ratio:.2f}",
            f"Max drawdown: {self.max_drawdown:.2f} | Sharpe: {self.sharpe:.2f}",
        ]
        if self.by_direction:
            lines.append("By direction: " + ", ".join(
                f"{k} {v:+.2f}" for k, v in self.by_direction.items()))
        if self.by_symbol:
            top = sorted(self.by_symbol.items(), key=lambda x: x[1])
            lines.append("Worst symbols: " + ", ".join(
                f"{k} {v:+.2f}" for k, v in top[:3]))
        if self.by_strategy:
            lines.append("By strategy: " + ", ".join(
                f"{k} {v:+.2f}" for k, v in self.by_strategy.items()))
        if self.insights:
            lines.append("\nDIAGNOSIS & RECOMMENDATIONS:")
            for ins in self.insights:
                lines.append(f"  [{ins.severity.upper()}] {ins.message}")
                lines.append(f"        → {ins.suggestion}")
        return "\n".join(lines)


class TradeJournal:
    """Holds trade records and produces a diagnosed performance report."""

    def __init__(self, records: Optional[List[TradeRecord]] = None):
        self.records: List[TradeRecord] = records or []

    # -- loaders -----------------------------------------------------------
    @classmethod
    def from_records(cls, records: List[TradeRecord]) -> "TradeJournal":
        return cls(list(records))

    @classmethod
    def from_csv(cls, path: str, mapping: Optional[Dict[str, str]] = None) -> "TradeJournal":
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        return cls([cls._row_to_record(r, mapping) for r in rows if r])

    @classmethod
    def from_json(cls, path: str) -> "TradeJournal":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        rows = data if isinstance(data, list) else data.get("trades", [])
        return cls([cls._row_to_record({str(k): v for k, v in r.items()}) for r in rows])

    @classmethod
    def from_backtest(cls, result) -> "TradeJournal":
        """Build a journal from a BacktestResult's trade list."""
        recs = []
        for t in getattr(result, "trades", []):
            recs.append(TradeRecord(
                symbol=result.symbol, direction=t.direction,
                entry_price=t.entry_price, exit_price=t.exit_price or t.entry_price,
                pnl=t.pnl_pct, strategy=result.strategy,
            ))
        return cls(recs)

    @staticmethod
    def _resolve(headers: Dict[str, str], field_name: str,
                 mapping: Optional[Dict[str, str]]) -> Optional[str]:
        if mapping and field_name in mapping:
            return mapping[field_name]
        aliases = _ALIASES.get(field_name, {field_name})
        for key in headers:
            if key.strip().lower() in aliases:
                return key
        return None

    @classmethod
    def _row_to_record(cls, row: Dict[str, str],
                       mapping: Optional[Dict[str, str]] = None) -> TradeRecord:
        def get(field_name, default=None):
            key = cls._resolve(row, field_name, mapping)
            return row.get(key, default) if key else default

        def fnum(field_name, default=0.0):
            raw = get(field_name)
            if raw is None or raw == "":
                return default
            try:
                return float(str(raw).replace(",", "").replace("$", "").strip())
            except ValueError:
                return default

        raw_dir = str(get("direction", "long")).strip().lower()
        direction = "short" if raw_dir in _SHORT_WORDS else "long"
        pnl_raw = get("pnl")
        pnl = None
        if pnl_raw not in (None, ""):
            try:
                pnl = float(str(pnl_raw).replace(",", "").replace("$", "").strip())
            except ValueError:
                pnl = None
        return TradeRecord(
            symbol=str(get("symbol", "?")).strip(),
            direction=direction,
            entry_price=fnum("entry_price"),
            exit_price=fnum("exit_price"),
            qty=fnum("qty", 1.0) or 1.0,
            pnl=pnl,
            fees=fnum("fees", 0.0),
            strategy=(str(get("strategy")).strip() if get("strategy") else None),
            entry_time=(str(get("entry_time")) if get("entry_time") else None),
            exit_time=(str(get("exit_time")) if get("exit_time") else None),
        )

    # -- analytics ---------------------------------------------------------
    def analyze(self) -> PerformanceReport:
        recs = self.records
        n = len(recs)
        if n == 0:
            return PerformanceReport(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

        pnls = [r.net_pnl for r in recs]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        total = sum(pnls)
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        pf = gross_win / gross_loss if gross_loss else float("inf")
        avg_win = (gross_win / len(wins)) if wins else 0.0
        avg_loss = (sum(losses) / len(losses)) if losses else 0.0
        payoff = (avg_win / abs(avg_loss)) if avg_loss else float("inf")

        # drawdown on cumulative P&L
        cum, peak, max_dd = 0.0, 0.0, 0.0
        for p in pnls:
            cum += p
            peak = max(peak, cum)
            max_dd = max(max_dd, peak - cum)

        mean = total / n
        var = sum((p - mean) ** 2 for p in pnls) / n
        std = math.sqrt(var)
        sharpe = (mean / std * math.sqrt(n)) if std else 0.0

        report = PerformanceReport(
            n_trades=n, win_rate=len(wins) / n, profit_factor=pf,
            expectancy=mean, total_pnl=total, avg_win=avg_win, avg_loss=avg_loss,
            payoff_ratio=payoff, max_drawdown=max_dd, sharpe=sharpe,
            by_symbol=self._group(lambda r: r.symbol),
            by_strategy=self._group(lambda r: r.strategy or "unspecified"),
            by_direction=self._group(lambda r: r.direction),
            by_weekday=self._group(lambda r: r.weekday() or "unknown"),
        )
        report.insights = self._diagnose(report)
        return report

    def _group(self, key) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for r in self.records:
            out[key(r)] = out.get(key(r), 0.0) + r.net_pnl
        return out

    # -- diagnosis ---------------------------------------------------------
    def _diagnose(self, rep: PerformanceReport) -> List[Insight]:
        insights: List[Insight] = []

        # Losing side of the book.
        for direction, pnl in rep.by_direction.items():
            if pnl < 0 and rep.n_trades >= 10:
                insights.append(Insight(
                    "high", "direction",
                    f"Your {direction} trades are net negative ({pnl:+.2f}).",
                    f"Consider disabling {direction}s or tightening their entry filter.",
                    {"disable_direction": direction},
                ))

        # Consistently losing symbols.
        for sym, pnl in sorted(rep.by_symbol.items(), key=lambda x: x[1]):
            if pnl < 0 and rep.n_trades >= 8:
                insights.append(Insight(
                    "medium", "symbol",
                    f"{sym} is a net loser ({pnl:+.2f}).",
                    f"Drop {sym} from the universe or re-tune its parameters.",
                    {"drop_symbol": sym},
                ))
                break  # surface the single worst, don't spam

        # Poor reward/risk geometry.
        if rep.payoff_ratio < 1.0 and rep.win_rate < 0.5:
            insights.append(Insight(
                "high", "risk",
                f"Payoff {rep.payoff_ratio:.2f} with sub-50% win rate is a negative edge.",
                "Widen take-profit / cut losers faster — raise the R:R target.",
                {"increase_rr": True},
            ))

        # Overtrading with thin expectancy.
        if rep.expectancy <= 0:
            insights.append(Insight(
                "high", "edge",
                f"Expectancy per trade is {rep.expectancy:+.2f} — no positive edge.",
                "Re-optimize parameters (walk-forward) before trading more size.",
                {"retune": True},
            ))

        # Drawdown vs total return.
        if rep.total_pnl > 0 and rep.max_drawdown > 2 * rep.total_pnl:
            insights.append(Insight(
                "medium", "risk",
                f"Max drawdown ({rep.max_drawdown:.2f}) dwarfs total P&L "
                f"({rep.total_pnl:+.2f}).",
                "Lower per-trade risk % and cap correlated exposure.",
                {"reduce_risk_pct": True},
            ))

        # Worst weekday.
        if rep.by_weekday:
            worst_day, worst_pnl = min(rep.by_weekday.items(), key=lambda x: x[1])
            if worst_pnl < 0 and worst_day != "unknown" and rep.n_trades >= 15:
                insights.append(Insight(
                    "low", "timing",
                    f"{worst_day} is your worst day ({worst_pnl:+.2f}).",
                    f"Consider pausing the bot on {worst_day}s.",
                    {"skip_weekday": worst_day},
                ))

        if not insights:
            insights.append(Insight(
                "low", "general",
                "No glaring weaknesses detected.",
                "Keep validating with walk-forward and watch for regime change.",
            ))
        return insights
