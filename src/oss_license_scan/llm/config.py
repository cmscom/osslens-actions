"""LLM configuration management."""

import os
from typing import Literal

from pydantic import BaseModel, Field

from oss_license_scan.agent.config import AgentConfig, load_agent_config_from_env
from oss_license_scan.utils.env_validation import (
    parse_bool_env,
    parse_float_env,
    parse_int_env,
    parse_optional_int_env,
    parse_str_env,
)


class LLMConfig(BaseModel):
    """
    LLM configuration.

    Attributes:
        provider: LLM provider ("openai" | "anthropic")
        model_name: Model name
        temperature: Temperature (0.0～1.0)
        timeout: Timeout in seconds
        max_retries: Maximum retry count
        with_fallback: Enable fallback to alternative provider
        min_confidence: Minimum confidence score (below this is ignored)
        max_llm_calls: Maximum LLM call count (cost limit), None for unlimited
    """

    provider: Literal["openai", "anthropic"] = "openai"
    model_name: str = "gpt-4o"
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    timeout: float = Field(default=5.0, gt=0.0)
    max_retries: int = Field(default=0, ge=0)
    with_fallback: bool = True
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    max_llm_calls: int | None = Field(default=None, gt=0)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """
        Create LLMConfig from environment variables.

        Returns:
            LLMConfig instance with values from environment variables.

        Note:
            Invalid environment variable values will log a warning and use defaults.
            This prevents CLI crashes from user input errors.
        """
        provider = parse_str_env(
            "LLM_PROVIDER", default="openai", allowed_values=["openai", "anthropic"]
        )
        model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o")
        temperature = parse_float_env("LLM_TEMPERATURE", default=0.0, min_value=0.0, max_value=1.0)
        timeout = parse_float_env("LLM_TIMEOUT", default=5.0, min_value=0.1)
        max_retries = parse_int_env("LLM_MAX_RETRIES", default=0, min_value=0)
        with_fallback = parse_bool_env("LLM_WITH_FALLBACK", default=True)
        min_confidence = parse_float_env(
            "LLM_MIN_CONFIDENCE", default=0.5, min_value=0.0, max_value=1.0
        )
        max_llm_calls = parse_optional_int_env("MAX_LLM_CALLS", min_value=1)

        return cls(
            provider=provider,  # type: ignore
            model_name=model_name,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
            with_fallback=with_fallback,
            min_confidence=min_confidence,
            max_llm_calls=max_llm_calls,
        )


def get_agent_config() -> AgentConfig:
    """
    Get Agent configuration from environment variables.

    Environment variables:
        ENABLE_AGENT: Enable/disable agent (default: true)
        MAX_AGENT_ITERATIONS: Maximum iterations (default: 10)
        AGENT_TIMEOUT_SECONDS: Timeout in seconds (default: 5)
        GITHUB_TOKEN: GitHub API token (optional)

    Returns:
        AgentConfig instance.
    """
    return load_agent_config_from_env()
