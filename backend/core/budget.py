"""
ASCENT Token Budget — per-workflow token and cost limits.

Dev 4 owns this file. Agents check budget before LLM calls; llm.py tracks usage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("budget")

# Rough blended USD per 1K tokens (input + output average) for cost estimates
_COST_PER_1K_TOKENS = 0.0004


class BudgetExceededError(Exception):
    """Raised when a workflow has exhausted its token or cost budget."""

    def __init__(self, message: str = "Token budget exceeded"):
        super().__init__(message)
        self.message = message


@dataclass
class TokenBudget:
    """Tracks token usage and cost for a single pipeline run."""

    max_tokens: int = field(default_factory=lambda: settings.MAX_TOKENS_PER_WORKFLOW)
    max_cost_usd: float = field(default_factory=lambda: settings.MAX_COST_PER_WORKFLOW)
    tokens_used: int = 0
    cost_usd: float = 0.0
    by_agent: dict[str, int] = field(default_factory=dict)

    def track(self, agent: str, tokens: int, cost_usd: Optional[float] = None) -> None:
        """Record tokens (and optional cost) for an agent."""
        if tokens <= 0:
            return
        self.tokens_used += tokens
        self.by_agent[agent] = self.by_agent.get(agent, 0) + tokens
        if cost_usd is not None:
            self.cost_usd += cost_usd
        else:
            self.cost_usd += (tokens / 1000.0) * _COST_PER_1K_TOKENS

        logger.info(
            "budget_tracked",
            agent=agent,
            tokens=tokens,
            total_tokens=self.tokens_used,
            max_tokens=self.max_tokens,
            cost_usd=round(self.cost_usd, 6),
            usage_pct=round(self.usage_fraction() * 100, 1),
        )

    def check_remaining(self) -> int:
        """Tokens still available before hitting the cap."""
        return max(0, self.max_tokens - self.tokens_used)

    def remaining_cost_usd(self) -> float:
        return max(0.0, self.max_cost_usd - self.cost_usd)

    def usage_fraction(self) -> float:
        if self.max_tokens <= 0:
            return 1.0
        return min(1.0, self.tokens_used / self.max_tokens)

    def is_exceeded(self) -> bool:
        return self.tokens_used >= self.max_tokens or self.cost_usd >= self.max_cost_usd

    def tier(self) -> int:
        """
        Context compression tier from budget usage.
        1: < 50%, 2: 50–80%, 3: > 80%
        """
        frac = self.usage_fraction()
        if frac < 0.5:
            return 1
        if frac < 0.8:
            return 2
        return 3

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_tokens": self.max_tokens,
            "max_cost_usd": self.max_cost_usd,
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
            "by_agent": dict(self.by_agent),
        }

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> TokenBudget:
        if not data:
            return cls()
        return cls(
            max_tokens=data.get("max_tokens", settings.MAX_TOKENS_PER_WORKFLOW),
            max_cost_usd=data.get("max_cost_usd", settings.MAX_COST_PER_WORKFLOW),
            tokens_used=data.get("tokens_used", 0),
            cost_usd=data.get("cost_usd", 0.0),
            by_agent=dict(data.get("by_agent", {})),
        )

    def state_updates(self) -> dict[str, Any]:
        """Fields to merge into PipelineState after tracking."""
        return {
            "token_budget": self.to_dict(),
            "total_tokens_used": self.tokens_used,
            "total_cost_usd": self.cost_usd,
        }


def get_budget(state: dict[str, Any]) -> TokenBudget:
    """Load TokenBudget from pipeline state (token_budget dict or legacy counters)."""
    if state.get("token_budget"):
        return TokenBudget.from_dict(state["token_budget"])
    return TokenBudget(
        tokens_used=state.get("total_tokens_used", 0) or 0,
        cost_usd=state.get("total_cost_usd", 0.0) or 0.0,
    )


def estimate_cost_usd(total_tokens: int) -> float:
    return (total_tokens / 1000.0) * _COST_PER_1K_TOKENS


def format_cost_usd(amount: float) -> str:
    """Format a USD amount for API responses."""
    return f"${amount:.2f}"


def usage_from_pipeline_result(result: dict[str, Any]) -> tuple[int, float]:
    """
    Read token/cost totals from a pipeline result dict.

    LangGraph may expose totals on top-level fields or only inside token_budget.
    """
    tokens = int(result.get("total_tokens_used") or 0)
    cost = float(result.get("total_cost_usd") or 0.0)
    budget = result.get("token_budget")
    if isinstance(budget, dict):
        if not tokens:
            tokens = int(budget.get("tokens_used") or 0)
        if not cost:
            cost = float(budget.get("cost_usd") or 0.0)
    return tokens, cost


def check_budget_or_stop(
    state: dict[str, Any],
    agent: str,
    workflow_id: str = "unknown",
) -> Optional[dict[str, Any]]:
    """
    If budget is exceeded, return a state patch that stops the agent gracefully.
    Otherwise return None (proceed).
    """
    budget = get_budget(state)
    if not budget.is_exceeded():
        return None

    msg = (
        f"Token budget exceeded ({budget.tokens_used:,} / {budget.max_tokens:,} tokens, "
        f"${budget.cost_usd:.4f} / ${budget.max_cost_usd:.2f}). Pipeline stopped at {agent}."
    )
    logger.warning("budget_exceeded", agent=agent, workflow_id=workflow_id, message=msg)

    from backend.models.schemas import ActivityEvent, AgentStatus

    return {
        "error": msg,
        "should_continue": False,
        "current_agent": agent,
        **budget.state_updates(),
        "activity_log": [
            ActivityEvent(
                agent=agent,
                status=AgentStatus.ERROR,
                message="Budget exceeded",
                detail=msg,
                workflow_id=workflow_id,
            )
        ],
    }
