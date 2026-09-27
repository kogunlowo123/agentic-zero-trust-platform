import json

import litellm

_PLANNER_MODEL = "azure/gpt-4o-mini"
_SYSTEM_PROMPT = """\
You are a task planner for a zero-trust security agent. Given a task description and
a list of available tools, return a JSON array of tool names in the order they should
be called to complete the task. Only include tools from the provided list.
Respond with valid JSON only — no explanations.

Example output:
["rag_search", "policy_query"]
"""


class TaskPlanner:
    """Generates ordered tool-call plans for agent tasks using an LLM.

    Args:
        model: LiteLLM model string to use for planning.
               Defaults to 'azure/gpt-4o-mini'.
    """

    def __init__(self, model: str = _PLANNER_MODEL) -> None:
        self._model = model

    async def plan(self, task: str, available_tools: list[str]) -> list[str]:
        """Generate an ordered list of tool calls to complete a task.

        Args:
            task: Natural-language description of the task to complete.
            available_tools: List of tool names the agent has access to.

        Returns:
            An ordered list of tool names from *available_tools*.
            Returns an empty list if the planner cannot produce a valid plan.
        """
        user_message = (
            f"Task: {task}\n\n"
            f"Available tools: {json.dumps(available_tools)}\n\n"
            "Return the ordered JSON array of tool names to call."
        )

        response = await litellm.acompletion(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
            max_tokens=256,
            response_format={"type": "json_object"},
        )

        raw_content: str = response.choices[0].message.content or "[]"

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            return []

        # The model may return {"plan": [...]} or just [...]
        if isinstance(parsed, list):
            candidate = parsed
        elif isinstance(parsed, dict):
            # Try common wrapper keys
            for key in ("plan", "tools", "steps", "order"):
                if key in parsed and isinstance(parsed[key], list):
                    candidate = parsed[key]
                    break
            else:
                return []
        else:
            return []

        # Filter to only tools that are actually available
        available_set = set(available_tools)
        return [t for t in candidate if isinstance(t, str) and t in available_set]
