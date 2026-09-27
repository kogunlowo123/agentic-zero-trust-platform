from agent_runtime.orchestrator.state import AgentState

# Cost per 1 000 tokens for supported models (USD)
LITELLM_COST_PER_1K_TOKENS: dict[str, float] = {
    "gpt-4o": 0.005,
    "gpt-4o-mini": 0.00015,
}


class BudgetEnforcer:
    """Enforces per-session token and tool-call budgets.

    Args:
        max_budget_usd: Maximum total LLM spend allowed for the session.
        max_tool_calls: Maximum number of tool invocations allowed.
    """

    def __init__(self, max_budget_usd: float, max_tool_calls: int) -> None:
        if max_budget_usd <= 0:
            raise ValueError("max_budget_usd must be positive")
        if max_tool_calls < 1:
            raise ValueError("max_tool_calls must be at least 1")
        self.max_budget_usd = max_budget_usd
        self.max_tool_calls = max_tool_calls

    def check(self, state: AgentState) -> bool:
        """Return True if the session is within both budget and tool-call limits.

        Args:
            state: Current agent state with ``budget_used_usd`` and
                   ``tool_call_count`` fields.
        """
        budget_ok = state.get("budget_used_usd", 0.0) < self.max_budget_usd
        calls_ok = state.get("tool_call_count", 0) < self.max_tool_calls
        return budget_ok and calls_ok

    def record_tool_call(self, state: AgentState, cost_usd: float) -> AgentState:
        """Increment the tool-call counter and deduct the cost from the budget.

        Args:
            state: Current agent state (not mutated in place).
            cost_usd: The USD cost of this tool invocation.

        Returns:
            A new state dict with updated ``tool_call_count`` and
            ``budget_used_usd`` values.
        """
        updated = dict(state)
        updated["tool_call_count"] = state.get("tool_call_count", 0) + 1
        updated["budget_used_usd"] = state.get("budget_used_usd", 0.0) + cost_usd
        return updated  # type: ignore[return-value]

    @staticmethod
    def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
        """Estimate the USD cost of a completion.

        Looks up the per-1k-token rate for *model*.  Returns 0.0 for
        unknown models so the caller can still make progress.

        Args:
            model: The model identifier as used in LiteLLM (without 'azure/' prefix).
            tokens_in: Number of prompt tokens.
            tokens_out: Number of completion tokens.
        """
        # Strip provider prefix (e.g. 'azure/gpt-4o' -> 'gpt-4o')
        base_model = model.split("/")[-1]
        rate = LITELLM_COST_PER_1K_TOKENS.get(base_model, 0.0)
        total_tokens = tokens_in + tokens_out
        return (total_tokens / 1000.0) * rate
