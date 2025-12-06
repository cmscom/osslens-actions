"""License compatibility rules loader and manager."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class CompatibilityRule(BaseModel):
    """Individual license compatibility rule."""

    license_a: str = Field(..., description="First license identifier")
    license_b: str = Field(..., description="Second license identifier")
    status: Literal["compatible", "conditional", "incompatible", "unknown"] = Field(
        ..., description="Compatibility status"
    )
    explanation: str = Field(..., description="Explanation of compatibility")
    conditions: list[str] = Field(
        default_factory=list, description="Conditions for compatibility (if conditional)"
    )

    def is_compatible(self) -> bool:
        """Check if licenses are compatible (including conditional)."""
        return self.status in ["compatible", "conditional"]


class CompatibilityRules(BaseModel):
    """Container for all compatibility rules."""

    rules: list[CompatibilityRule] = Field(
        default_factory=list, description="List of compatibility rules"
    )
    default_rule: CompatibilityRule = Field(..., description="Default rule when no match found")

    def find_rule(self, license_a: str, license_b: str) -> CompatibilityRule:
        """
        Find compatibility rule for two licenses.

        Args:
            license_a: First license identifier
            license_b: Second license identifier

        Returns:
            CompatibilityRule: Matching rule or default rule
        """
        # Try to find exact match (either order)
        for rule in self.rules:
            if (rule.license_a == license_a and rule.license_b == license_b) or (
                rule.license_a == license_b and rule.license_b == license_a
            ):
                return rule

        # Return default rule if no match found
        return self.default_rule


def load_compatibility_rules(rules_file: str | None = None) -> CompatibilityRules:
    """
    Load compatibility rules from JSON file.

    Args:
        rules_file: Path to rules JSON file. If None, loads default rules.

    Returns:
        CompatibilityRules: Loaded rules container

    Raises:
        FileNotFoundError: If specified rules file doesn't exist
        ValueError: If rules file is invalid JSON
    """
    if rules_file is None:
        # Load default rules from data/license_compatibility.json
        default_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "data"
            / "license_compatibility.json"
        )
        rules_path = default_path
    else:
        rules_path = Path(rules_file)
    if not rules_path.exists():
        raise FileNotFoundError(f"Rules file not found: {rules_file}")

    try:
        with open(rules_path) as f:
            data = json.load(f)

        # Parse rules
        rules = [CompatibilityRule(**rule_data) for rule_data in data.get("rules", [])]

        # Parse default rule
        default_rule_data = data.get("default_rule", {})
        default_rule = CompatibilityRule(
            license_a="",
            license_b="",
            status=default_rule_data.get("status", "unknown"),
            explanation=default_rule_data.get("explanation", "No compatibility rule defined"),
            conditions=default_rule_data.get("conditions", []),
        )

        return CompatibilityRules(rules=rules, default_rule=default_rule)

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in rules file: {e}") from e
