"""Parser for pylock.toml (PEP 751) files."""

import tomllib
from typing import ClassVar

from oss_license_scan.models import Dependency, Ecosystem, LockFileFormat, ParseResult
from oss_license_scan.parsers.base import BaseLockFileParser, ParseError


class PylockTomlParser(BaseLockFileParser):
    """pylock.toml (PEP 751) パーサー"""

    FORMAT: ClassVar[LockFileFormat] = LockFileFormat.PYLOCK_TOML
    ECOSYSTEM: ClassVar[Ecosystem] = Ecosystem.PYTHON
    FILENAME_PATTERNS: ClassVar[list[str]] = [r"^pylock\.toml$", r"^pylock\.[^.]+\.toml$"]

    def parse(self, content: str) -> ParseResult:
        """
        pylock.tomlをパースする。

        Expected format:
            lock-version = "1.0"
            [[packages]]
            name = "requests"
            version = "2.32.3"

        Args:
            content: ファイル内容

        Returns:
            ParseResult with Dependency list

        Raises:
            ParseError: パース失敗時
        """
        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError as e:
            raise ParseError(f"Invalid TOML: {e}") from e

        dependencies: list[Dependency] = []
        warnings: list[str] = []

        # Extract packages
        packages = data.get("packages", [])
        for pkg in packages:
            name = pkg.get("name")
            version = pkg.get("version")

            if not name:
                warnings.append("Package entry missing 'name' field")
                continue

            dependencies.append(
                Dependency(
                    name=name,
                    version=version,
                    ecosystem=Ecosystem.PYTHON,
                )
            )

        # Extract metadata
        metadata: dict[str, object] = {}
        if "lock-version" in data:
            metadata["lock-version"] = data["lock-version"]
        if "requires-python" in data:
            metadata["requires-python"] = data["requires-python"]
        if "created-by" in data:
            metadata["created-by"] = data["created-by"]

        return ParseResult(
            format=self.FORMAT,
            ecosystem=self.ECOSYSTEM,
            dependencies=dependencies,
            warnings=warnings,
            metadata=metadata,
        )
