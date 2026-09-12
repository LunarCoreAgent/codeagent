"""Token budgets for agent runs, including sub-agent roll-up."""

from __future__ import annotations

from dataclasses import dataclass

from codeagent.core.types import Usage


class BudgetExceededError(RuntimeError):
    """Raised when an agent's total token usage exceeds its budget."""


@dataclass
class Budget:
    """A spending cap for a single ``Agent.run`` (one user task).

    ``max_total_tokens`` counts input + output tokens, including usage
    rolled up from delegated sub-agents (Codex-style root-goal budgeting).
    Usage is reset at the start of each ``run`` so a long desktop chat
    does not accumulate every prior turn into one hard cap.

    When ``aware`` is set, the agent injects a budget-status line into the
    system prompt on every iteration, so the model can adapt its behavior
    (pace exploration, prefer verification over blind search) as the budget
    drains — the key mechanism behind Google Research's Budget-Aware
    Tool-Use (BATS) agent scaling.

    ``soft`` changes what happens when the cap is hit mid-work: instead of
    raising :class:`BudgetExceededError`, the agent wraps up with the best
    answer so far. Finished answers (no more tool calls) are always kept,
    even a little over the cap — throwing them away wastes the spend.
    """

    max_total_tokens: int | None = None
    aware: bool = True
    soft: bool = False

    def used(self, usage: Usage) -> int:
        return usage.input_tokens + usage.output_tokens

    def exceeded(self, usage: Usage) -> bool:
        if self.max_total_tokens is None:
            return False
        return self.used(usage) > self.max_total_tokens

    def status_message(self, usage: Usage) -> str:
        """One-line budget status for in-context injection."""
        if self.max_total_tokens is None:
            return ""
        used = usage.input_tokens + usage.output_tokens
        remaining = max(self.max_total_tokens - used, 0)
        pct = remaining / self.max_total_tokens * 100
        if pct > 50:
            guidance = "Plenty of budget remains; explore as needed."
        elif pct > 20:
            guidance = "Budget is draining; prefer targeted, high-confidence actions."
        else:
            guidance = "Budget nearly exhausted; wrap up with the best answer you have."
        return (
            f"[Budget status] {used}/{self.max_total_tokens} tokens used, "
            f"{pct:.0f}% remaining. {guidance}"
        )
