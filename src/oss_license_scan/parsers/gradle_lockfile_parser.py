"""Parser for gradle.lockfile files."""

import re
from typing import ClassVar

from oss_license_scan.models import Dependency, Ecosystem, LockFileFormat, ParseResult
from oss_license_scan.parsers.base import BaseLockFileParser


class GradleLockfileParser(BaseLockFileParser):
    """gradle.lockfile パーサー"""

    FORMAT: ClassVar[LockFileFormat] = LockFileFormat.GRADLE_LOCKFILE
    ECOSYSTEM: ClassVar[Ecosystem] = Ecosystem.MAVEN
    FILENAME_PATTERNS: ClassVar[list[str]] = [r"^gradle\.lockfile$"]

    # Pattern to match dependency lines: group:artifact:version=configurations
    # Example: org.apache.commons:commons-lang3:3.12.0=compileClasspath,runtimeClasspath
    DEPENDENCY_PATTERN = re.compile(r"^([^:]+):([^:]+):([^=]+)=.*$")

    def parse(self, content: str) -> ParseResult:
        """
        gradle.lockfileをパースする。

        Expected format:
            org.apache.commons:commons-lang3:3.12.0=compileClasspath

        Args:
            content: ファイル内容

        Returns:
            ParseResult with Dependency list
        """
        dependencies: list[Dependency] = []
        warnings: list[str] = []

        for line_num, line in enumerate(content.splitlines(), 1):
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Skip empty= lines (Gradle marker for empty configurations)
            if line == "empty=":
                continue

            match = self.DEPENDENCY_PATTERN.match(line)
            if not match:
                if "=" in line and not line.startswith("empty"):
                    warnings.append(f"Line {line_num}: Could not parse: {line[:50]}...")
                continue

            group_id = match.group(1)
            artifact_id = match.group(2)
            version = match.group(3)

            # Create name in format groupId:artifactId
            name = f"{group_id}:{artifact_id}"

            dependencies.append(
                Dependency(
                    name=name,
                    version=version,
                    ecosystem=Ecosystem.MAVEN,
                    group_id=group_id,
                    artifact_id=artifact_id,
                )
            )

        return ParseResult(
            format=self.FORMAT,
            ecosystem=self.ECOSYSTEM,
            dependencies=dependencies,
            warnings=warnings,
        )
