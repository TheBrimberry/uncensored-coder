"""
Editable bot configuration.

A `BotConfig` is the live, persistent definition of a trading bot: which symbol /
strategy / timeframe it runs, its tunable `params`, its risk budget, and an
append-only audit log of every change. The auto-tuner edits these params; the
audit log + `rollback()` make every automated edit reversible.

Persisted as plain JSON so it is human-readable and diff-friendly in git.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class ChangeLogEntry:
    timestamp: str
    field: str                           # "params" | "risk_pct" | "enabled" | ...
    old_value: object
    new_value: object
    reason: str
    source: str                          # "auto-tuner" | "manual" | ...


@dataclass
class BotConfig:
    name: str
    symbol: str
    strategy: str
    timeframe: str = "1d"
    params: Dict[str, object] = field(default_factory=dict)
    risk_pct: float = 1.0
    enabled: bool = True
    # Optional path to the bot's strategy source file (for code improvements).
    code_path: Optional[str] = None
    history: List[ChangeLogEntry] = field(default_factory=list)

    # -- persistence -------------------------------------------------------
    @classmethod
    def load(cls, path: str) -> "BotConfig":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        history = [ChangeLogEntry(**h) for h in data.pop("history", [])]
        cfg = cls(**data)
        cfg.history = history
        return cfg

    def save(self, path: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        payload = asdict(self)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return path

    # -- mutation (audited) ------------------------------------------------
    def _log(self, field_name: str, old, new, reason: str, source: str) -> None:
        self.history.append(ChangeLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            field=field_name, old_value=old, new_value=new,
            reason=reason, source=source,
        ))

    def update_params(self, new_params: Dict[str, object], reason: str = "",
                      source: str = "auto-tuner") -> "BotConfig":
        old = dict(self.params)
        merged = {**self.params, **new_params}
        if merged != old:
            self._log("params", old, merged, reason, source)
            self.params = merged
        return self

    def set_field(self, field_name: str, value, reason: str = "",
                  source: str = "manual") -> "BotConfig":
        if not hasattr(self, field_name):
            raise AttributeError(f"BotConfig has no field '{field_name}'")
        old = getattr(self, field_name)
        if old != value:
            self._log(field_name, old, value, reason, source)
            setattr(self, field_name, value)
        return self

    def rollback(self, steps: int = 1) -> "BotConfig":
        """Undo the last `steps` audited changes, restoring prior values."""
        for _ in range(steps):
            if not self.history:
                break
            entry = self.history.pop()
            setattr(self, entry.field, entry.old_value)
        return self

    def summary(self) -> str:
        state = "enabled" if self.enabled else "DISABLED"
        lines = [
            f"Bot '{self.name}' [{state}] — {self.strategy} on {self.symbol} ({self.timeframe})",
            f"  risk/trade: {self.risk_pct}%  params: {self.params}",
        ]
        if self.history:
            last = self.history[-1]
            lines.append(f"  last change: {last.field} via {last.source} "
                         f"@ {last.timestamp} ({last.reason})")
        return "\n".join(lines)
