"""
Auto-tuner — improve a bot's performance and (optionally) edit it live.

Two kinds of improvement, both safety-gated:

1. **Parameter tuning** — grid-search + walk-forward on fresh data, then apply
   the new params to the `BotConfig` *only* if they are out-of-sample ROBUST and
   beat the bot's current configuration by a margin. Every edit is audited and
   reversible via `BotConfig.rollback()`.

2. **Code improvement** — use the LLM to propose edits to the bot's strategy
   source file, grounded in its performance review and walk-forward results.
   Proposals are written to a side file and the original is backed up; nothing
   overwrites live code unless `apply=True` is passed explicitly.

The `monitor()` method is the live loop: call it on a schedule (cron, the /loop
skill, etc.) to re-tune each bot as new bars arrive.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .backtest import Backtester, BacktestResult
from .bot import BotConfig
from .market_data import MarketData
from .optimize import grid_search, walk_forward, DEFAULT_GRIDS, METRICS, _bind


@dataclass
class TuneProposal:
    bot: str
    strategy: str
    metric: str
    current_params: Dict[str, object]
    current_score: float
    best_params: Dict[str, object]
    best_score: float
    improvement_pct: float
    oos_robust: bool
    recommended: bool
    rationale: str

    def summary(self) -> str:
        verdict = "APPLY ✓" if self.recommended else "HOLD ✗"
        return (
            f"=== TUNE PROPOSAL [{verdict}]: {self.bot} ({self.strategy}, {self.metric}) ===\n"
            f"Current {self.current_params} -> {self.current_score:.3f}\n"
            f"Proposed {self.best_params} -> {self.best_score:.3f} "
            f"({self.improvement_pct:+.1f}%)\n"
            f"Walk-forward OOS: {'ROBUST' if self.oos_robust else 'FRAGILE'}\n"
            f"{self.rationale}"
        )


@dataclass
class CodeProposal:
    bot: str
    code_path: str
    proposed_path: Optional[str]
    backup_path: Optional[str]
    applied: bool
    diff_preview: str
    note: str

    def summary(self) -> str:
        status = "APPLIED" if self.applied else "PROPOSED (dry-run)"
        out = [f"=== CODE IMPROVEMENT [{status}]: {self.bot} ===", self.note]
        if self.proposed_path:
            out.append(f"Proposal written to: {self.proposed_path}")
        if self.backup_path:
            out.append(f"Backup of original:  {self.backup_path}")
        if self.diff_preview:
            out.append("\n--- preview ---\n" + self.diff_preview)
        return "\n".join(out)


class AutoTuner:
    def __init__(self, market_data: Optional[MarketData] = None,
                 min_improvement_pct: float = 10.0, require_robust: bool = True,
                 min_trades: int = 5):
        self.md = market_data or MarketData()
        self.min_improvement_pct = min_improvement_pct
        self.require_robust = require_robust
        self.min_trades = min_trades

    # -- parameter tuning --------------------------------------------------
    def _score_params(self, bars, strategy: str, params: Dict, metric: str) -> tuple:
        bt = Backtester(warmup=min(200, max(40, len(bars["close"]) // 4)))
        res = bt.run(bars, strategy=_bind(strategy, params), symbol="?")
        return METRICS[metric](res), res.n_trades

    def propose_params(self, bot: BotConfig, timeframe: Optional[str] = None,
                       limit: int = 800, metric: str = "calmar",
                       param_grid: Optional[Dict] = None) -> TuneProposal:
        tf = timeframe or bot.timeframe
        data = self.md.get_ohlcv(bot.symbol, tf, limit=limit)
        bars = data.as_bars()
        grid = param_grid if param_grid is not None else DEFAULT_GRIDS.get(bot.strategy, {})

        current_score, _ = self._score_params(bars, bot.strategy, bot.params, metric)
        search = grid_search(bars, bot.strategy, grid, metric=metric, symbol=bot.symbol,
                             min_trades=self.min_trades)
        wf = walk_forward(bars, bot.strategy, grid, metric=metric, symbol=bot.symbol)

        best_score = search.best_score
        denom = abs(current_score) if current_score else 1.0
        improvement = (best_score - current_score) / denom * 100

        robust_ok = wf.robust or not self.require_robust
        beats_current = improvement >= self.min_improvement_pct
        changed = search.best_params != bot.params
        recommended = bool(robust_ok and beats_current and changed)

        rationale = self._rationale(recommended, beats_current, robust_ok, changed, wf)
        return TuneProposal(
            bot=bot.name, strategy=bot.strategy, metric=metric,
            current_params=dict(bot.params), current_score=round(current_score, 3),
            best_params=search.best_params, best_score=round(best_score, 3),
            improvement_pct=round(improvement, 1), oos_robust=wf.robust,
            recommended=recommended, rationale=rationale,
        )

    def _rationale(self, rec, beats, robust, changed, wf) -> str:
        if rec:
            return (f"New params survive {wf.n_folds}-fold walk-forward "
                    f"(OOS {wf.oos_total_return:+.2f}%) and clear the improvement "
                    "threshold — safe to apply.")
        bits = []
        if not changed:
            bits.append("best params equal current (nothing to change)")
        if not beats:
            bits.append(f"improvement below {self.min_improvement_pct}% threshold")
        if not robust:
            bits.append("walk-forward says FRAGILE (likely overfit)")
        return "Holding: " + "; ".join(bits) + "."

    def apply_params(self, bot: BotConfig, proposal: TuneProposal,
                     path: Optional[str] = None, force: bool = False) -> BotConfig:
        """Apply proposed params to the bot if recommended (or forced), with audit."""
        if proposal.recommended or force:
            reason = (f"auto-tune {proposal.metric} "
                      f"{proposal.current_score}->{proposal.best_score} "
                      f"({proposal.improvement_pct:+.1f}%)"
                      + ("" if proposal.recommended else " [FORCED]"))
            bot.update_params(proposal.best_params, reason=reason, source="auto-tuner")
            if path:
                bot.save(path)
        return bot

    # -- code improvement (LLM) -------------------------------------------
    def improve_code(self, bot: BotConfig, performance_text: str = "",
                     loader=None, apply: bool = False) -> CodeProposal:
        """Have the LLM propose edits to the bot's strategy source file.

        Safe by default: writes a `<file>.proposed` and backs up the original;
        only overwrites the live file when `apply=True`.
        """
        if not bot.code_path or not os.path.isfile(bot.code_path):
            return CodeProposal(bot.name, bot.code_path or "", None, None, False, "",
                                "No code_path set or file not found — nothing to improve.")
        with open(bot.code_path, encoding="utf-8") as f:
            original = f.read()

        if loader is None or loader is False:
            return CodeProposal(
                bot.name, bot.code_path, None, None, False, "",
                "LLM unavailable (Ollama not running). Set up the model to enable "
                "code improvement; parameter tuning still works without it.")

        prompt = self._code_prompt(bot, original, performance_text)
        try:
            revised = loader.generate(prompt, system_prompt=_CODE_SYSTEM_PROMPT)
        except Exception as e:  # noqa: BLE001
            return CodeProposal(bot.name, bot.code_path, None, None, False, "",
                                f"LLM error during code improvement: {e}")

        revised = _strip_code_fence(revised)
        proposed_path = bot.code_path + ".proposed"
        with open(proposed_path, "w", encoding="utf-8") as f:
            f.write(revised)

        diff_preview = _unified_preview(original, revised)
        backup_path = None
        applied = False
        if apply:
            backup_path = f"{bot.code_path}.bak.{datetime.now(timezone.utc):%Y%m%d%H%M%S}"
            shutil.copy2(bot.code_path, backup_path)
            with open(bot.code_path, "w", encoding="utf-8") as f:
                f.write(revised)
            applied = True

        note = ("Applied LLM code edit (original backed up)." if applied else
                "Dry-run: review the .proposed file, then re-run with apply=True.")
        return CodeProposal(bot.name, bot.code_path, proposed_path, backup_path,
                            applied, diff_preview, note)

    def _code_prompt(self, bot: BotConfig, source: str, performance_text: str) -> str:
        return (
            f"Improve this trading bot's strategy code. Bot '{bot.name}' trades "
            f"{bot.symbol} on {bot.timeframe} using a '{bot.strategy}' approach with "
            f"params {bot.params}.\n\n"
            f"Recent performance review:\n{performance_text or '(none provided)'}\n\n"
            f"Current source code:\n```python\n{source}\n```\n\n"
            "Return ONLY the full revised Python file. Keep the public interface and "
            "function/class names identical so it stays drop-in compatible. Improve "
            "robustness, add sensible risk controls (stops), and fix obvious weaknesses. "
            "Do not add network calls or secrets. No prose outside the code."
        )

    # -- live loop ---------------------------------------------------------
    def monitor(self, bots: List[BotConfig], path_for: Optional[Dict[str, str]] = None,
                metric: str = "calmar", apply: bool = False) -> str:
        """Re-tune each bot on fresh data. Call on a schedule for 'live' tuning.

        With apply=False (default) it only reports proposals; with apply=True it
        applies the recommended (robust + improving) param changes and persists.
        """
        path_for = path_for or {}
        lines = [f"=== AUTO-TUNE SWEEP @ {datetime.now(timezone.utc):%Y-%m-%d %H:%M}Z "
                 f"({'APPLY' if apply else 'DRY-RUN'}) ==="]
        for bot in bots:
            if not bot.enabled:
                lines.append(f"· {bot.name}: disabled, skipped.")
                continue
            try:
                proposal = self.propose_params(bot, metric=metric)
            except Exception as e:  # noqa: BLE001
                lines.append(f"✗ {bot.name}: tuning failed ({e}).")
                continue
            if proposal.recommended and apply:
                self.apply_params(bot, proposal, path=path_for.get(bot.name))
                lines.append(f"✓ {bot.name}: applied {proposal.best_params} "
                             f"({proposal.improvement_pct:+.1f}% {metric}).")
            elif proposal.recommended:
                lines.append(f"→ {bot.name}: improvement available "
                             f"{proposal.best_params} ({proposal.improvement_pct:+.1f}%); "
                             "run with apply=True to commit.")
            else:
                lines.append(f"· {bot.name}: no change ({proposal.rationale})")
        return "\n".join(lines)


_CODE_SYSTEM_PROMPT = (
    "You are a senior quant developer. You refactor trading-strategy code to be "
    "more robust and risk-aware without changing its public interface. You output "
    "only valid Python source — no explanations, no markdown prose."
)


def _strip_code_fence(text: str) -> str:
    import re
    m = re.search(r"```(?:python)?\n(.*?)\n```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def _unified_preview(a: str, b: str, context: int = 2, max_lines: int = 40) -> str:
    import difflib
    diff = list(difflib.unified_diff(
        a.splitlines(), b.splitlines(), fromfile="current", tofile="proposed",
        lineterm="", n=context))
    if not diff:
        return "(no textual changes)"
    return "\n".join(diff[:max_lines]) + ("\n... (truncated)" if len(diff) > max_lines else "")
