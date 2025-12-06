"""LocalLicenseSource for reading license info from local files."""

import json
import logging
import re
from pathlib import Path

from oss_license_scan.models import LicenseResult, Package

logger = logging.getLogger(__name__)

# Common license file names
LICENSE_FILES = [
    "LICENSE",
    "LICENSE.txt",
    "LICENSE.md",
    "LICENSE.MIT",
    "LICENSE.APACHE",
    "license",
    "license.txt",
    "license.md",
    "LICENCE",
    "LICENCE.txt",
    "LICENCE.md",
    "COPYING",
    "COPYING.txt",
]

# Simple license detection patterns
LICENSE_PATTERNS = {
    "MIT": re.compile(r"\bMIT\s+License\b", re.IGNORECASE),
    "Apache-2.0": re.compile(r"\bApache\s+License[,\s]+Version\s+2\.0\b", re.IGNORECASE),
    "GPL-3.0": re.compile(r"\bGNU\s+General\s+Public\s+License\b.*\bversion\s+3\b", re.IGNORECASE),
    "BSD-3-Clause": re.compile(r"\bBSD\s+3-Clause\b", re.IGNORECASE),
    "ISC": re.compile(r"\bISC\s+License\b", re.IGNORECASE),
}


class LocalLicenseSource:
    """Local file system license source.

    Reads license information from local files such as:
    - node_modules/<package>/LICENSE
    - node_modules/<package>/package.json
    - site-packages/<package>.dist-info/METADATA
    """

    def __init__(
        self,
        base_path: Path | None = None,
        site_packages: Path | None = None,
    ) -> None:
        """Initialize the local source.

        Args:
            base_path: Base path for node_modules lookup
            site_packages: Path to Python site-packages directory
        """
        self._base_path = base_path
        self._site_packages = site_packages

    @property
    def name(self) -> str:
        """Return source name."""
        return "local"

    @property
    def ecosystems(self) -> list[str] | None:
        """Return supported ecosystems (None = all)."""
        return None  # Supports all ecosystems

    def resolve(self, pkg: Package) -> LicenseResult | None:
        """Resolve license from local files.

        Args:
            pkg: Package to resolve

        Returns:
            LicenseResult if found, None otherwise
        """
        if pkg.ecosystem == "python":
            return self._resolve_python(pkg)
        elif pkg.ecosystem == "npm":
            return self._resolve_npm(pkg)
        else:
            return None

    def _resolve_python(self, pkg: Package) -> LicenseResult | None:
        """Resolve Python package license from site-packages."""
        if self._site_packages is None:
            return None

        # Look for .dist-info directory
        dist_info_name = f"{pkg.name.replace('-', '_')}-{pkg.version}.dist-info"
        dist_info = self._site_packages / dist_info_name

        if not dist_info.exists():
            # Try with original name (no underscore replacement)
            dist_info_name = f"{pkg.name}-{pkg.version}.dist-info"
            dist_info = self._site_packages / dist_info_name
            if not dist_info.exists():
                return None

        # Read METADATA file
        metadata_file = dist_info / "METADATA"
        if metadata_file.exists():
            return self._parse_metadata(metadata_file, pkg)

        return None

    def _parse_metadata(self, metadata_file: Path, pkg: Package) -> LicenseResult | None:
        """Parse Python METADATA file for license info."""
        try:
            content = metadata_file.read_text(encoding="utf-8")
            # Look for License: header
            for line in content.split("\n"):
                if line.startswith("License:"):
                    license_value = line[8:].strip()
                    if license_value:
                        return LicenseResult(
                            source_name=self.name,
                            package=pkg,
                            license_spdx=license_value,
                            raw_license=license_value,
                            evidence_path=str(metadata_file),
                        )
        except Exception as e:
            logger.warning(f"Failed to parse METADATA for {pkg.name}: {e}")

        return None

    def _resolve_npm(self, pkg: Package) -> LicenseResult | None:
        """Resolve npm package license from node_modules."""
        if self._base_path is None:
            return None

        # Handle scoped packages (@scope/package)
        if pkg.name.startswith("@"):
            parts = pkg.name[1:].split("/", 1)
            if len(parts) == 2:
                package_dir = self._base_path / "node_modules" / f"@{parts[0]}" / parts[1]
            else:
                return None
        else:
            package_dir = self._base_path / "node_modules" / pkg.name

        if not package_dir.exists():
            return None

        # Try package.json first
        package_json = package_dir / "package.json"
        if package_json.exists():
            result = self._parse_package_json(package_json, pkg)
            if result:
                return result

        # Try LICENSE files
        for license_name in LICENSE_FILES:
            license_file = package_dir / license_name
            if license_file.exists():
                return self._parse_license_file(license_file, pkg)

        return None

    def _parse_package_json(self, package_json: Path, pkg: Package) -> LicenseResult | None:
        """Parse package.json for license info."""
        try:
            content = package_json.read_text(encoding="utf-8")
            data = json.loads(content)

            license_value = data.get("license")
            if isinstance(license_value, str) and license_value:
                return LicenseResult(
                    source_name=self.name,
                    package=pkg,
                    license_spdx=license_value,
                    raw_license=license_value,
                    evidence_path=str(package_json),
                )

            # Handle licenses array (older format)
            licenses = data.get("licenses")
            if isinstance(licenses, list) and licenses:
                first = licenses[0]
                if isinstance(first, dict) and "type" in first:
                    return LicenseResult(
                        source_name=self.name,
                        package=pkg,
                        license_spdx=first["type"],
                        raw_license=first["type"],
                        evidence_path=str(package_json),
                    )

        except Exception as e:
            logger.warning(f"Failed to parse package.json for {pkg.name}: {e}")

        return None

    def _parse_license_file(self, license_file: Path, pkg: Package) -> LicenseResult | None:
        """Parse LICENSE file and detect license type."""
        try:
            content = license_file.read_text(encoding="utf-8")

            # Try to detect license type from content
            detected_license = None
            for spdx_id, pattern in LICENSE_PATTERNS.items():
                if pattern.search(content):
                    detected_license = spdx_id
                    break

            return LicenseResult(
                source_name=self.name,
                package=pkg,
                license_spdx=detected_license,
                raw_license=content[:500],  # Truncate for storage
                evidence_path=str(license_file),
            )

        except Exception as e:
            logger.warning(f"Failed to read LICENSE file for {pkg.name}: {e}")

        return None
