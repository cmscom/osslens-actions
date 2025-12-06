"""Parser for go.sum files."""

import re
from typing import ClassVar

from oss_license_scan.models import Dependency, Ecosystem, LockFileFormat, ParseResult
from oss_license_scan.parsers.base import BaseLockFileParser


class GoSumParser(BaseLockFileParser):
    """go.sum パーサー"""

    FORMAT: ClassVar[LockFileFormat] = LockFileFormat.GO_SUM
    ECOSYSTEM: ClassVar[Ecosystem] = Ecosystem.GO
    FILENAME_PATTERNS: ClassVar[list[str]] = [r"^go\.sum$"]

    # Pattern to parse go.sum lines: module version hash
    # Example: github.com/pkg/errors v0.9.1 h1:FEBLx...
    LINE_PATTERN = re.compile(r"^(\S+)\s+(v[\d.]+(?:-[\w.]+)?(?:\+[\w.]+)?)\s+")

    def parse(self, content: str) -> ParseResult:
        """
        go.sumをパースする。

        Expected format:
            github.com/pkg/errors v0.9.1 h1:FEBLx...
            github.com/pkg/errors v0.9.1/go.mod h1:bwawx...

        Args:
            content: ファイル内容

        Returns:
            ParseResult with Dependency list (unique modules only)
        """
        dependencies: list[Dependency] = []
        warnings: list[str] = []
        seen_modules: set[tuple[str, str]] = set()

        for line_num, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            if not line:
                continue

            # Skip go.mod hash entries (we only want the main module entries)
            if "/go.mod " in line:
                continue

            match = self.LINE_PATTERN.match(line)
            if not match:
                if line and not line.startswith("#"):
                    warnings.append(f"Line {line_num}: Could not parse: {line[:50]}...")
                continue

            module_path = match.group(1)
            version = match.group(2)

            # Deduplicate by module path + version
            key = (module_path, version)
            if key in seen_modules:
                continue
            seen_modules.add(key)

            dependencies.append(
                Dependency(
                    name=module_path,
                    version=version,
                    ecosystem=Ecosystem.GO,
                    module_path=module_path,
                )
            )

        return ParseResult(
            format=self.FORMAT,
            ecosystem=self.ECOSYSTEM,
            dependencies=dependencies,
            warnings=warnings,
        )
