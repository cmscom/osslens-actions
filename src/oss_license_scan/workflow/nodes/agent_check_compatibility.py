"""Agent-based license compatibility checking node."""

from typing import Any

from oss_license_scan.agent.compatibility.checker import CompatibilityChecker
from oss_license_scan.agent.compatibility.expression_parser import (
    parse_spdx_expression,
)
from oss_license_scan.agent.compatibility.rules import load_compatibility_rules
from oss_license_scan.agent.config import AgentConfig
from oss_license_scan.models import LicenseCompatibility
from oss_license_scan.workflow.state import LicenseScanState


def agent_check_compatibility_node(state: LicenseScanState) -> dict[str, Any]:
    """
    Check license compatibility for all dependency pairs.

    This node:
    1. Checks if agent is enabled
    2. Parses license expressions to get individual licenses
    3. Checks compatibility between all unique pairs of licenses
    4. Returns compatibility check results

    Args:
        state: Current workflow state

    Returns:
        dict with:
        - compatibility_checks: List of LicenseCompatibility results
    """
    # Check if agent is enabled
    agent_config = state.get("agent_config", AgentConfig())
    if not agent_config.enabled:
        return {"compatibility_checks": []}

    # Get dependencies with licenses
    dependencies_with_license = state.get("dependencies_with_license", [])

    # Filter out None licenses and parse expressions
    all_licenses = set()
    for dep in dependencies_with_license:
        if dep.license is None:
            continue

        # Parse SPDX expression to get individual licenses
        combinations = parse_spdx_expression(dep.license)

        # Extract all unique licenses from combinations
        for combo in combinations:
            for license_name in combo:
                all_licenses.add(license_name)

    # Convert to sorted list for consistent ordering
    licenses = sorted(all_licenses)

    # Load compatibility rules and create checker
    rules = load_compatibility_rules()
    checker = CompatibilityChecker(rules=rules)

    # Check compatibility for all unique pairs (excluding same license)
    compatibility_checks = []

    for i in range(len(licenses)):
        for j in range(i + 1, len(licenses)):
            license_a = licenses[i]
            license_b = licenses[j]

            # Check compatibility
            result = checker.check_compatibility(license_a, license_b)

            # Convert to LicenseCompatibility model
            compatibility = LicenseCompatibility(
                license_a=result.license_a,
                license_b=result.license_b,
                status=result.status,  # type: ignore
                explanation=result.explanation,
                conditions=result.conditions,
                source="rules",  # Using rule-based compatibility checking
            )

            compatibility_checks.append(compatibility)

    return {"compatibility_checks": compatibility_checks}
