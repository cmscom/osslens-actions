"""Parser for package-lock.json files."""

import json
from typing import ClassVar

from oss_license_scan.models import Dependency, Ecosystem, LockFileFormat, ParseResult
from oss_license_scan.parsers.base import BaseLockFileParser, ParseError


class PackageLockJsonParser(BaseLockFileParser):
    """package-lock.json パーサー"""

    FORMAT: ClassVar[LockFileFormat] = LockFileFormat.PACKAGE_LOCK_JSON
    ECOSYSTEM: ClassVar[Ecosystem] = Ecosystem.NPM
    FILENAME_PATTERNS: ClassVar[list[str]] = [r"^package-lock\.json$"]

    def parse(self, content: str) -> ParseResult:
        """
        package-lock.jsonをパースする。

        Supports lockfileVersion 2 and 3.
        Extracts dependencies from packages object.

        Args:
            content: ファイル内容

        Returns:
            ParseResult with Dependency list

        Raises:
            ParseError: パース失敗時
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON: {e}") from e

        dependencies: list[Dependency] = []
        warnings: list[str] = []

        lockfile_version = data.get("lockfileVersion", 1)

        # Extract from packages (lockfileVersion 2 and 3)
        packages = data.get("packages", {})
        for pkg_path, pkg_info in packages.items():
            # Skip root package (empty string key)
            if pkg_path == "":
                continue

            # Extract package name from path (node_modules/package-name)
            name = pkg_path.replace("node_modules/", "").split("/")[-1]

            # Handle scoped packages (@org/package)
            if pkg_path.count("node_modules/") > 0:
                parts = pkg_path.split("node_modules/")[-1]
                name = parts

            version = pkg_info.get("version")

            if not name:
                warnings.append(f"Package entry missing name: {pkg_path}")
                continue

            dependencies.append(
                Dependency(
                    name=name,
                    version=version,
                    ecosystem=Ecosystem.NPM,
                )
            )

        # Extract metadata
        metadata: dict[str, object] = {
            "lockfileVersion": lockfile_version,
        }
        if "name" in data:
            metadata["projectName"] = data["name"]
        if "version" in data:
            metadata["projectVersion"] = data["version"]

        return ParseResult(
            format=self.FORMAT,
            ecosystem=self.ECOSYSTEM,
            dependencies=dependencies,
            warnings=warnings,
            metadata=metadata,
        )
