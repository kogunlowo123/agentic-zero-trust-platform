from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    principal: str
    resource: str
    action: str
    policy_context: list[dict]  # retrieved RAG docs
    retrieved_docs: list[dict]
    decision: dict | None  # PolicyDecision: {allowed, reasons, principal, timestamp, decision_id}
    citations: list[str]
    posture_score: float | None
    tool_call_count: int
    budget_used_usd: float
    session_id: str
    error: str | None
    abstain: bool


class PostureState(TypedDict):
    messages: Annotated[list, add_messages]
    principal: str
    signals: dict
    posture_score: float | None
    risk_level: str | None
    recommendations: list[str]
    error: str | None
