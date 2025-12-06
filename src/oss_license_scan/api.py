"""Main API for OSS license scanning."""

import logging
from pathlib import Path

from oss_license_scan.models import ScanReport

logger = logging.getLogger(__name__)


class PolicyValidationError(ValueError):
    """Raised when policy file validation fails."""

    pass


def scan_project(
    input_file: str | Path,
    project_type: str | None = None,
    policy_file: str | Path | None = None,
    enable_llm: bool = True,
    enable_agent: bool = True,
    verbose: bool = False,
    explain_license: str | None = None,
    license_sources: list[str] | None = None,
    overrides_file: str | Path | None = None,
    mode: str = "fast",
) -> ScanReport:
    """
    Scan a project for OSS license information.

    Args:
        input_file: Path to the input file (lock file or dependency file)
        project_type: Format type. If None, auto-detect from filename.
            Supported: requirements, pyproject, pylock, package-lock,
                       go-sum, gemfile-lock, pom, gradle-lock
        policy_file: Optional path to policy.json file
        enable_llm: Enable LLM integration for license inference (default: True)
        enable_agent: Enable Agent feature for dynamic license search (default: True)
        verbose: Enable verbose mode (generate license summaries for all packages)
        explain_license: Generate summary for specific license (e.g., "MIT")
        license_sources: Custom source order list (e.g., ["pypi", "github"]).
            If None, uses default source order.
        overrides_file: Path to license_overrides.yml for manual license overrides
        mode: Resolution mode - "fast" (first source wins) or "deep" (all sources, consistency check)

    Returns:
        ScanReport with license information and policy results

    Raises:
        FileNotFoundError: If input file not found
        PolicyValidationError: If policy file is invalid
        ValueError: If project type cannot be determined

    Examples:
        >>> report = scan_project("requirements.txt")
        >>> print(report.summary.total_dependencies)
        42
    """
    # Delegate to LangGraph workflow adapter
    from oss_license_scan.workflow.adapters import scan_project_with_langgraph

    return scan_project_with_langgraph(
        input_file=input_file,
        project_type=project_type,
        policy_file=policy_file,
        enable_llm=enable_llm,
        enable_agent=enable_agent,
        verbose=verbose,
        explain_license=explain_license,
        license_sources=license_sources,
        overrides_file=overrides_file,
        mode=mode,
    )
