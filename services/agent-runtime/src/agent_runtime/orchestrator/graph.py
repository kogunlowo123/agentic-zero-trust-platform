"""Policy-enforcer LangGraph agent.

Builds and exposes a compiled StateGraph that:
  1. Retrieves relevant policy documents via RAG (retrieve node).
  2. Evaluates the access request against OPA (evaluate node).
  3. Generates a grounded compliance report via LLM (generate node).

Conditional edges handle low-confidence retrieval (abstain) and errors.
"""

import os
import uuid
from datetime import datetime, timezone

import litellm
import structlog
from langgraph.graph import END, StateGraph

from agent_runtime.guardrails.citation_validator import (
    extract_citations,
    validate_citations,
)
from agent_runtime.guardrails.grounding_check import check_grounding
from agent_runtime.orchestrator.state import AgentState
from agent_runtime.tools.policy_query import policy_query_tool
from agent_runtime.tools.rag_search import rag_search_tool

log = structlog.get_logger(__name__)

_LLM_MODEL = "azure/gpt-4o"
_MIN_RETRIEVAL_SCORE = float(os.environ.get("MIN_RETRIEVAL_SCORE", "0.7"))
_OPA_RESOURCE_SENSITIVITY = os.environ.get("OPA_RESOURCE_SENSITIVITY", "HIGH")
_OPA_PRINCIPAL_TIER = os.environ.get("OPA_PRINCIPAL_TIER", "T1")

_REPORT_SYSTEM_PROMPT = """\
You are a zero-trust policy compliance analyst. Your task is to produce a
structured compliance report for an access decision.

Rules:
- Ground every claim in the retrieved policy documents provided below.
- Cite each source document using [DOC-N] notation (1-indexed).
- Be concise but complete: include the decision, justification, and any
  recommended remediation if access was denied.
- Do not include any information that is not supported by the provided documents.
- Output plain text; do not use markdown headers.
"""


# ---------------------------------------------------------------------------
# Node: retrieve_policy_context
# ---------------------------------------------------------------------------

async def retrieve_policy_context(state: AgentState) -> AgentState:
    """RAG retrieval node.

    Queries the policy corpus for documents relevant to the current
    (principal, resource, action) triple.  Sets ``abstain = True`` when
    the best retrieval score falls below the minimum confidence threshold.

    Args:
        state: Current agent state.

    Returns:
        Updated state with ``policy_context``, ``retrieved_docs``, and
        ``abstain`` populated.
    """
    query = (
        f"Principal '{state['principal']}' requests '{state['action']}' "
        f"on resource '{state['resource']}'."
    )

    try:
        docs = await rag_search_tool(
            query=query,
            top_k=5,
            principal=state.get("principal"),
        )
    except RuntimeError as exc:
        log.error("rag_retrieval_failed", error=str(exc), session_id=state.get("session_id"))
        return {
            **state,
            "policy_context": [],
            "retrieved_docs": [],
            "abstain": True,
            "error": f"RAG retrieval failed: {exc}",
        }

    if not docs:
        return {
            **state,
            "policy_context": [],
            "retrieved_docs": [],
            "abstain": True,
            "error": "No policy documents retrieved.",
        }

    max_score = max(d.get("score", 0.0) for d in docs)
    should_abstain = max_score < _MIN_RETRIEVAL_SCORE

    log.info(
        "rag_retrieval_complete",
        doc_count=len(docs),
        max_score=max_score,
        abstain=should_abstain,
        session_id=state.get("session_id"),
    )

    return {
        **state,
        "policy_context": docs,
        "retrieved_docs": docs,
        "abstain": should_abstain,
        "error": None if not should_abstain else (
            f"Retrieval confidence too low (max score {max_score:.2f} < "
            f"{_MIN_RETRIEVAL_SCORE}); abstaining."
        ),
    }


# ---------------------------------------------------------------------------
# Node: evaluate_request
# ---------------------------------------------------------------------------

async def evaluate_request(state: AgentState) -> AgentState:
    """OPA evaluation node.

    Calls the OPA policy engine via ``policy_query_tool`` and constructs
    a PolicyDecision.  Emits a structured log event on denial.

    Args:
        state: Current agent state (must have passed retrieval).

    Returns:
        Updated state with ``decision`` populated.
    """
    posture_score = state.get("posture_score") or 0.0

    try:
        opa_result = await policy_query_tool(
            principal_id=state["principal"],
            principal_tier=_OPA_PRINCIPAL_TIER,
            resource_id=state["resource"],
            resource_sensitivity=_OPA_RESOURCE_SENSITIVITY,
            action=state["action"],
            posture_score=posture_score,
        )
    except RuntimeError as exc:
        log.error(
            "opa_evaluation_failed",
            error=str(exc),
            principal=state["principal"],
            session_id=state.get("session_id"),
        )
        return {
            **state,
            "decision": None,
            "error": f"OPA evaluation failed: {exc}",
        }

    decision: dict = {
        "allowed": opa_result["allowed"],
        "reasons": opa_result["reasons"],
        "principal": state["principal"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision_id": opa_result.get("decision_id", str(uuid.uuid4())),
    }

    if not decision["allowed"]:
        log.warning(
            "policy_violation",
            principal=state["principal"],
            resource=state["resource"],
            action=state["action"],
            reasons=decision["reasons"],
            decision_id=decision["decision_id"],
            session_id=state.get("session_id"),
        )

    log.info(
        "opa_decision",
        allowed=decision["allowed"],
        decision_id=decision["decision_id"],
        session_id=state.get("session_id"),
    )

    return {**state, "decision": decision, "error": None}


# ---------------------------------------------------------------------------
# Node: generate_report
# ---------------------------------------------------------------------------

async def generate_report(state: AgentState) -> AgentState:
    """LLM report generation node.

    Produces a grounded compliance report using the retrieved policy
    documents as context.  Validates citations against the source list
    and attaches the grounding score.

    Args:
        state: Current agent state with ``decision`` and ``retrieved_docs``.

    Returns:
        Updated state with ``messages`` (report appended) and ``citations``.
    """
    decision = state.get("decision") or {}
    docs = state.get("retrieved_docs", [])

    # Build the document context block for the prompt
    doc_context_lines: list[str] = []
    for idx, doc in enumerate(docs, start=1):
        content = doc.get("content", "")
        metadata = doc.get("metadata", {})
        title = metadata.get("title", f"Document {idx}")
        doc_context_lines.append(f"[DOC-{idx}] {title}:\n{content}")
    doc_context = "\n\n".join(doc_context_lines)

    user_prompt = (
        f"Access request summary:\n"
        f"  Principal: {state['principal']}\n"
        f"  Resource:  {state['resource']}\n"
        f"  Action:    {state['action']}\n"
        f"  Decision:  {'ALLOWED' if decision.get('allowed') else 'DENIED'}\n"
        f"  Reasons:   {'; '.join(decision.get('reasons', []))}\n"
        f"  Decision ID: {decision.get('decision_id', 'N/A')}\n\n"
        f"Policy documents:\n{doc_context}\n\n"
        "Generate a compliance report grounded in the above documents."
    )

    try:
        response = await litellm.acompletion(
            model=_LLM_MODEL,
            messages=[
                {"role": "system", "content": _REPORT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=2048,
        )
        report_text: str = response.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001
        log.error(
            "report_generation_failed",
            error=str(exc),
            session_id=state.get("session_id"),
        )
        return {
            **state,
            "error": f"Report generation failed: {exc}",
            "citations": [],
        }

    # Validate grounding and citations
    grounding_score = check_grounding(report_text, docs)
    citations = extract_citations(report_text)
    _valid, invalid_citations = validate_citations(citations, docs)

    if invalid_citations:
        log.warning(
            "invalid_citations_in_report",
            invalid=invalid_citations,
            session_id=state.get("session_id"),
        )

    log.info(
        "report_generated",
        grounding_score=grounding_score,
        citation_count=len(citations),
        session_id=state.get("session_id"),
    )

    # Append the report as an assistant message
    new_message = {"role": "assistant", "content": report_text}
    updated_messages = list(state.get("messages", [])) + [new_message]

    return {
        **state,
        "messages": updated_messages,
        "citations": citations,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Conditional edge functions
# ---------------------------------------------------------------------------

def should_abstain(state: AgentState) -> str:
    """Route to 'abstain' (END) when retrieval confidence is too low or an
    error occurred; otherwise proceed to 'evaluate'.
    """
    if state.get("abstain") or state.get("error"):
        return "abstain"
    return "evaluate"


def route_after_evaluate(state: AgentState) -> str:
    """Route to 'error' (END) when OPA evaluation failed; otherwise
    proceed to 'generate'.
    """
    if state.get("error"):
        return "error"
    return "generate"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_policy_enforcer_graph() -> StateGraph:
    """Construct and compile the policy-enforcer LangGraph.

    Graph topology:
        retrieve --> [abstain? -> END] --> evaluate --> [error? -> END] --> generate --> END

    Returns:
        A compiled LangGraph StateGraph ready for invocation.
    """
    graph = StateGraph(AgentState)

    graph.add_node("retrieve", retrieve_policy_context)
    graph.add_node("evaluate", evaluate_request)
    graph.add_node("generate", generate_report)

    graph.set_entry_point("retrieve")

    graph.add_conditional_edges(
        "retrieve",
        should_abstain,
        {"abstain": END, "evaluate": "evaluate"},
    )
    graph.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {"error": END, "generate": "generate"},
    )
    graph.add_edge("generate", END)

    return graph.compile()


# Module-level compiled graph instance
policy_enforcer = build_policy_enforcer_graph()


# ---------------------------------------------------------------------------
# Entrypoint (for `python -m agent_runtime.orchestrator.graph`)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    async def _smoke_test() -> None:
        initial_state: AgentState = {
            "messages": [],
            "principal": "user@example.com",
            "resource": "arn:data:customer-records",
            "action": "read",
            "policy_context": [],
            "retrieved_docs": [],
            "decision": None,
            "citations": [],
            "posture_score": 85.0,
            "tool_call_count": 0,
            "budget_used_usd": 0.0,
            "session_id": str(uuid.uuid4()),
            "error": None,
            "abstain": False,
        }
        result = await policy_enforcer.ainvoke(initial_state)
        print("Decision:", result.get("decision"))
        print("Citations:", result.get("citations"))
        print("Error:", result.get("error"))

    asyncio.run(_smoke_test())
