"""OverridesSource for manual license overrides via YAML configuration."""

import logging
import re
from pathlib import Path
from typing import Any

from oss_license_scan.models import (
    LicenseResult,
    OverrideEntry,
    OverridesConfig,
    Package,
)

logger = logging.getLogger(__name__)


class OverridesSource:
    """License source for manual overrides via YAML configuration.

    Allows project maintainers to override license information for specific
    packages using patterns in a YAML file.

    Example:
        >>> from oss_license_scan.sources.overrides_source import load_overrides_config
        >>> config = load_overrides_config("license_overrides.yml")
        >>> source = OverridesSource(config)
        >>> pkg = Package(ecosystem="python", name="internal-lib", version="1.0.0")
        >>> result = source.resolve(pkg)
        >>> print(result.license_spdx)  # "Proprietary"
    """

    def __init__(self, config: OverridesConfig) -> None:
        """Initialize the overrides source.

        Args:
            config: OverridesConfig with override entries
        """
        self._config = config
        self._compiled_patterns: list[tuple[re.Pattern[str], OverrideEntry]] = []

        # Pre-compile patterns for efficiency
        for entry in config.overrides:
            try:
                # Anchor pattern for exact matching (unless it's already a regex)
                pattern_str = entry.pattern
                if not pattern_str.startswith("^"):
                    pattern_str = f"^{pattern_str}$"
                compiled = re.compile(pattern_str)
                self._compiled_patterns.append((compiled, entry))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{entry.pattern}': {e}")

    @property
    def name(self) -> str:
        """Return source name."""
        return "overrides"

    @property
    def ecosystems(self) -> list[str] | None:
        """Return supported ecosystems (None = all)."""
        return None  # Supports all ecosystems

    def resolve(self, pkg: Package) -> LicenseResult | None:
        """Resolve license from overrides configuration.

        Args:
            pkg: Package to resolve

        Returns:
            LicenseResult if an override matches, None otherwise
        """
        for pattern, entry in self._compiled_patterns:
            # Check ecosystem filter
            if entry.ecosystem is not None and entry.ecosystem != pkg.ecosystem:
                continue

            # Check pattern match
            if pattern.match(pkg.name):
                logger.debug(f"Override matched for {pkg.name}: {entry.pattern} -> {entry.license}")

                raw_license = entry.license
                if entry.reason:
                    raw_license = f"{entry.license} ({entry.reason})"

                return LicenseResult(
                    source_name=self.name,
                    package=pkg,
                    license_spdx=entry.license,
                    raw_license=raw_license,
                    confidence=1.0,  # Overrides have full confidence
                    evidence_path="license_overrides.yml",
                )

        return None


def load_overrides_config(path: Path | str) -> OverridesConfig:
    """Load overrides configuration from YAML file.

    Args:
        path: Path to license_overrides.yml file

    Returns:
        OverridesConfig parsed from the file

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file is invalid YAML or doesn't match expected schema
    """
    import yaml

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Overrides file not found: {file_path}")

    try:
        with open(file_path, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in overrides file: {e}") from e

    try:
        return OverridesConfig.model_validate(data)
    except Exception as e:
        raise ValueError(f"Invalid overrides configuration: {e}") from e
