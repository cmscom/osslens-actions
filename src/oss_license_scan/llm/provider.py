"""LLM provider factory for creating LLM instances."""

import os
from typing import Any, Literal

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI


def create_llm(
    provider: Literal["openai", "anthropic"] | None = None,
    timeout: float = 5.0,
    with_fallback: bool = True,
    model_name: str | None = None,
) -> Any:
    """
    Create an LLM instance using factory pattern.

    Args:
        provider: Provider name (None to read from LLM_PROVIDER env var).
        timeout: Request timeout in seconds.
        with_fallback: Enable fallback functionality.
        model_name: Model name (None to use default for provider).

    Returns:
        Configured LLM instance.

    Raises:
        ValueError: If provider is invalid.
        EnvironmentError: If required API KEY environment variable is not set.
    """
    # Determine provider from env if not specified
    if provider is None:
        provider = os.getenv("LLM_PROVIDER", "openai")  # type: ignore

    # Validate provider
    if provider not in ["openai", "anthropic"]:
        raise ValueError(f"Invalid provider: {provider}. Must be 'openai' or 'anthropic'.")

    # Determine model name
    if model_name is None:
        if provider == "openai":
            model_name = os.getenv("LLM_MODEL_NAME", "gpt-4.1-mini")
        else:  # anthropic
            model_name = os.getenv("LLM_MODEL_NAME", "claude-haiku-4-5-20251001")

    # Create primary and fallback models
    if provider == "openai":
        # Check API key
        if not os.getenv("OPENAI_API_KEY"):
            raise OSError("OPENAI_API_KEY is not set. Please set it in .env file or environment.")

        # Determine if fallback is actually possible (FR-001)
        can_fallback = with_fallback and bool(os.getenv("ANTHROPIC_API_KEY"))

        primary = ChatOpenAI(
            model=model_name,
            timeout=timeout,
            max_retries=0 if can_fallback else 2,
        )

        if can_fallback:
            fallback_model = ChatAnthropic(  # type: ignore
                model_name="claude-haiku-4-5-20251001",
                timeout=timeout,
                max_retries=2,
            )
            return primary.with_fallbacks([fallback_model])

        return primary

    else:  # anthropic
        # Check API key
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise OSError(
                "ANTHROPIC_API_KEY is not set. Please set it in .env file or environment."
            )

        # Determine if fallback is actually possible (FR-001)
        can_fallback = with_fallback and bool(os.getenv("OPENAI_API_KEY"))

        primary = ChatAnthropic(  # type: ignore
            model_name=model_name,
            timeout=timeout,
            max_retries=0 if can_fallback else 2,
        )

        if can_fallback:
            fallback_model = ChatOpenAI(
                model="gpt-4.1-mini",
                timeout=timeout,
                max_retries=2,
            )
            return primary.with_fallbacks([fallback_model])

        return primary
