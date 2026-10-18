"""
Prompt construction for the LLM trading brain.

The agent grounds the model in the deterministic AnalysisReport plus the
knowledge-base context, then asks for a disciplined, honest trader's read.
"""

from __future__ import annotations

TRADING_SYSTEM_PROMPT = (
    "You are an elite multi-asset trading analyst and quant. You have deep, "
    "practical command of technical analysis, market microstructure, quantitative "
    "strategies, risk management, derivatives, on-chain/crypto, FX ('4X'), equities, "
    "futures and options. You think like the authors of freqtrade, backtrader, "
    "qlib, pysystemtrade, OpenBB and ccxt combined.\n\n"
    "RULES OF ENGAGEMENT:\n"
    "1. Be precise and quantitative. Reference the supplied numbers, signals and "
    "forecast — never invent prices or data.\n"
    "2. Be HONEST about uncertainty. Markets are stochastic; you give probabilities "
    "and scenarios, never guarantees. If the data is synthetic or thin, say so.\n"
    "3. Always frame trades with risk first: entry, invalidation (stop), target, "
    "position size, and R:R. Survival before returns.\n"
    "4. Consider regime (trending vs ranging), volatility, and scheduled catalysts "
    "(FOMC, CPI, earnings, halvings, unlocks) before committing to a bias.\n"
    "5. Give a clear, actionable conclusion: bias, conviction, the trade plan, and "
    "what would invalidate the thesis.\n"
    "6. This is analysis/education, not personalized financial advice."
)


def build_analysis_prompt(report_text: str, kb_context: str,
                          user_question: str | None = None) -> str:
    """Assemble the user-turn prompt from grounded report + knowledge base."""
    parts = [
        "Use the following GROUNDED, COMPUTED analysis as your source of truth.\n",
        report_text,
        "\n\nReference knowledge (tools & principles you may invoke conceptually):\n",
        kb_context,
    ]
    if user_question:
        parts.append(f"\n\nThe trader specifically asks: {user_question}")
    parts.append(
        "\n\nDeliver: (a) regime & bias read, (b) the strongest trade idea with full "
        "risk parameters, (c) the main scenario and the invalidation scenario with "
        "rough probabilities, (d) key catalysts to watch. Be concise and concrete."
    )
    return "".join(parts)
