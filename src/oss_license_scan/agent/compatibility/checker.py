"""License compatibility checker."""

from pydantic import BaseModel, Field

from oss_license_scan.agent.compatibility.rules import (
    CompatibilityRule,
    CompatibilityRules,
)


class CompatibilityResult(BaseModel):
    """Result of a compatibility check between two licenses."""

    license_a: str = Field(..., description="First license identifier")
    license_b: str = Field(..., description="Second license identifier")
    status: str = Field(..., description="Compatibility status")
    is_compatible: bool = Field(..., description="Whether licenses are compatible")
    explanation: str = Field(..., description="Explanation of compatibility")
    conditions: list[str] = Field(default_factory=list, description="Conditions for compatibility")

    @classmethod
    def from_rule(
        cls, license_a: str, license_b: str, rule: CompatibilityRule
    ) -> "CompatibilityResult":
        """Create CompatibilityResult from a CompatibilityRule."""
        return cls(
            license_a=license_a,
            license_b=license_b,
            status=rule.status,
            is_compatible=rule.is_compatible(),
            explanation=rule.explanation,
            conditions=rule.conditions,
        )


class CompatibilityChecker:
    """Checker for license compatibility using predefined rules."""

    def __init__(self, rules: CompatibilityRules):
        """
        Initialize compatibility checker.

        Args:
            rules: CompatibilityRules container with compatibility rules
        """
        self.rules = rules

    def check_compatibility(self, license_a: str, license_b: str) -> CompatibilityResult:
        """
        Check compatibility between two licenses.

        Args:
            license_a: First license identifier
            license_b: Second license identifier

        Returns:
            CompatibilityResult: Result of compatibility check
        """
        # Same license is always compatible
        if license_a == license_b:
            return CompatibilityResult(
                license_a=license_a,
                license_b=license_b,
                status="compatible",
                is_compatible=True,
                explanation=f"{license_a} is compatible with itself",
                conditions=[],
            )

        # Find applicable rule
        rule = self.rules.find_rule(license_a, license_b)

        # Convert rule to result
        return CompatibilityResult.from_rule(license_a, license_b, rule)

    def check_batch(self, pairs: list[tuple[str, str]]) -> list[CompatibilityResult]:
        """
        Check compatibility for multiple license pairs.

        Args:
            pairs: List of (license_a, license_b) tuples

        Returns:
            list[CompatibilityResult]: Results for each pair
        """
        results = []
        for license_a, license_b in pairs:
            result = self.check_compatibility(license_a, license_b)
            results.append(result)
        return results
