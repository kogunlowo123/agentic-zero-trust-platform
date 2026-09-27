import os

import litellm
from tenacity import retry, stop_after_attempt, wait_exponential

_AZURE_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
_AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
_AZURE_API_BASE = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
_AZURE_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")


class AzureOpenAIProvider:
    """LiteLLM-backed Azure OpenAI completion provider.

    Args:
        deployment: Azure OpenAI deployment name.
                    Defaults to the AZURE_OPENAI_DEPLOYMENT env var.
        api_base: Azure OpenAI endpoint URL.
                  Defaults to the AZURE_OPENAI_ENDPOINT env var.
        api_key: Azure OpenAI API key.
                 Defaults to the AZURE_OPENAI_API_KEY env var.
        api_version: Azure OpenAI API version.
                     Defaults to the AZURE_OPENAI_API_VERSION env var.
    """

    def __init__(
        self,
        deployment: str = _AZURE_DEPLOYMENT,
        api_base: str = _AZURE_API_BASE,
        api_key: str = _AZURE_API_KEY,
        api_version: str = _AZURE_API_VERSION,
    ) -> None:
        self._model = f"azure/{deployment}"
        self._api_base = api_base
        self._api_key = api_key
        self._api_version = api_version

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=1, max=30),
        reraise=True,
    )
    async def complete(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> dict:
        """Request a chat completion from Azure OpenAI.

        Handles rate-limit responses (429) with exponential back-off via
        tenacity.  On persistent failure the last exception is re-raised.

        Args:
            messages: List of OpenAI-format message dicts.
            model: Override the deployment model string.  Accepts the bare
                   deployment name; the 'azure/' prefix is prepended
                   automatically.
            max_tokens: Maximum completion tokens.
            **kwargs: Additional LiteLLM completion kwargs
                      (temperature, top_p, etc.).

        Returns:
            A dict with 'content', 'model', 'usage' keys:
                - content (str): The completion text.
                - model (str): The model string used.
                - usage (dict): token usage with keys
                  'prompt_tokens', 'completion_tokens', 'total_tokens'.

        Raises:
            litellm.RateLimitError: If rate-limit retries are exhausted.
            litellm.APIError: On other API-level errors.
        """
        effective_model = f"azure/{model}" if model and not model.startswith("azure/") else (model or self._model)

        response = await litellm.acompletion(
            model=effective_model,
            messages=messages,
            max_tokens=max_tokens,
            api_base=self._api_base or None,
            api_key=self._api_key or None,
            api_version=self._api_version,
            **kwargs,
        )

        content: str = response.choices[0].message.content or ""
        usage = response.usage or {}

        return {
            "content": content,
            "model": effective_model,
            "usage": {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
            },
        }
