"""Parser for Gemfile.lock files."""

import re
from typing import ClassVar

from oss_license_scan.models import Dependency, Ecosystem, LockFileFormat, ParseResult
from oss_license_scan.parsers.base import BaseLockFileParser


class GemfileLockParser(BaseLockFileParser):
    """Gemfile.lock パーサー"""

    FORMAT: ClassVar[LockFileFormat] = LockFileFormat.GEMFILE_LOCK
    ECOSYSTEM: ClassVar[Ecosystem] = Ecosystem.RUBY
    FILENAME_PATTERNS: ClassVar[list[str]] = [r"^Gemfile\.lock$"]

    # Pattern to match gem specs: "    gem-name (version)"
    GEM_SPEC_PATTERN = re.compile(r"^\s{4}(\S+)\s+\(([^)]+)\)$")

    def parse(self, content: str) -> ParseResult:
        """
        Gemfile.lockをパースする。

        Parses GEM section specs.

        Args:
            content: ファイル内容

        Returns:
            ParseResult with Dependency list
        """
        dependencies: list[Dependency] = []
        warnings: list[str] = []
        in_gem_section = False
        in_specs_section = False

        for line in content.splitlines():
            # Track section transitions
            if line == "GEM":
                in_gem_section = True
                continue
            elif line and not line.startswith(" "):
                # New top-level section
                in_gem_section = False
                in_specs_section = False
                continue

            if in_gem_section:
                if line.strip() == "specs:":
                    in_specs_section = True
                    continue

                if in_specs_section:
                    # Match gem spec lines (4-space indent)
                    match = self.GEM_SPEC_PATTERN.match(line)
                    if match:
                        name = match.group(1)
                        version = match.group(2)

                        dependencies.append(
                            Dependency(
                                name=name,
                                version=version,
                                ecosystem=Ecosystem.RUBY,
                            )
                        )

        return ParseResult(
            format=self.FORMAT,
            ecosystem=self.ECOSYSTEM,
            dependencies=dependencies,
            warnings=warnings,
        )
