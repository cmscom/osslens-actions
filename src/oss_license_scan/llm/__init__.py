"""LLM integration module for license inference and analysis."""

from oss_license_scan.llm.config import LLMConfig
from oss_license_scan.llm.provider import create_llm

__all__ = ["LLMConfig", "create_llm"]
