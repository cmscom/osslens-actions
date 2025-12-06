"""Agent configuration management."""

import os

from pydantic import BaseModel, Field

from oss_license_scan.utils.env_validation import parse_bool_env, parse_int_env

DEFAULT_AGENT_LLM_MODEL = None


class AgentConfig(BaseModel):
    """Agent configuration settings."""

    enabled: bool = Field(
        default=True,
        description="Agent機能の有効/無効",
    )
    max_iterations: int = Field(
        default=10,
        ge=1,
        le=50,
        description="最大ツール呼び出し数",
    )
    timeout_seconds: int = Field(
        default=5,
        ge=1,
        le=30,
        description="ツール呼び出しタイムアウト（秒）",
    )
    max_consecutive_same_tool: int = Field(
        default=3,
        ge=1,
        le=10,
        description="同じツール連続呼び出し制限",
    )
    llm_model: str | None = Field(
        default=DEFAULT_AGENT_LLM_MODEL,
        description="使用するLLMモデル（Noneの場合はプロバイダーに応じたデフォルトを使用）",
    )
    github_token: str | None = Field(
        default=None,
        description="GitHub APIトークン（オプション）",
    )
    enable_cache: bool = Field(
        default=True,
        description="ツール呼び出しキャッシュの有効/無効",
    )
    cache_ttl_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="キャッシュTTL（日数）",
    )


def load_agent_config_from_env() -> AgentConfig:
    """
    Load Agent configuration from environment variables.

    Environment variables:
        ENABLE_AGENT: "true" or "false" (case-insensitive, default: "true")
        MAX_AGENT_ITERATIONS: Maximum tool call iterations (default: 10)
        AGENT_TIMEOUT_SECONDS: Tool call timeout in seconds (default: 5)
        GITHUB_TOKEN: GitHub API token (optional)
        MAX_CONSECUTIVE_SAME_TOOL: Max consecutive same tool calls (default: 3)
        AGENT_CACHE_TTL_DAYS: Cache TTL in days (default: 7)

    Returns:
        AgentConfig instance with values from environment variables

    Note:
        Invalid environment variable values will log a warning and use defaults.
        This prevents CLI crashes from user input errors.
    """
    enabled = parse_bool_env("ENABLE_AGENT", default=True)
    max_iterations = parse_int_env("MAX_AGENT_ITERATIONS", default=10, min_value=1, max_value=50)
    timeout_seconds = parse_int_env("AGENT_TIMEOUT_SECONDS", default=5, min_value=1, max_value=30)
    github_token = os.getenv("GITHUB_TOKEN")
    max_consecutive_same_tool = parse_int_env(
        "MAX_CONSECUTIVE_SAME_TOOL", default=3, min_value=1, max_value=10
    )
    cache_ttl_days = parse_int_env("AGENT_CACHE_TTL_DAYS", default=7, min_value=1, max_value=30)
    llm_model = os.getenv("AGENT_LLM_MODEL") or None

    return AgentConfig(
        enabled=enabled,
        max_iterations=max_iterations,
        timeout_seconds=timeout_seconds,
        github_token=github_token,
        max_consecutive_same_tool=max_consecutive_same_tool,
        cache_ttl_days=cache_ttl_days,
        llm_model=llm_model,
    )
