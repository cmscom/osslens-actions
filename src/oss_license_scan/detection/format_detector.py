"""Format detection for lock files."""

import re
from pathlib import Path

from oss_license_scan.models import FormatDetectionResult, LockFileFormat


class FormatDetector:
    """ファイル形式自動検出クラス"""

    # Filename patterns for each format
    FILENAME_PATTERNS: dict[LockFileFormat, list[str]] = {
        LockFileFormat.REQUIREMENTS_TXT: [r"^requirements.*\.txt$"],
        LockFileFormat.PYPROJECT_TOML: [r"^pyproject\.toml$"],
        LockFileFormat.PYLOCK_TOML: [r"^pylock\.toml$", r"^pylock\.[^.]+\.toml$"],
        LockFileFormat.PACKAGE_LOCK_JSON: [r"^package-lock\.json$"],
        LockFileFormat.GO_SUM: [r"^go\.sum$"],
        LockFileFormat.GEMFILE_LOCK: [r"^Gemfile\.lock$"],
        LockFileFormat.POM_XML: [r"^pom\.xml$"],
        LockFileFormat.GRADLE_LOCKFILE: [r"^gradle\.lockfile$"],
    }

    # CLI format string to LockFileFormat mapping
    FORMAT_STRING_MAP: dict[str, LockFileFormat] = {
        "auto": None,  # type: ignore[dict-item]
        "requirements": LockFileFormat.REQUIREMENTS_TXT,
        "pyproject": LockFileFormat.PYPROJECT_TOML,
        "pylock": LockFileFormat.PYLOCK_TOML,
        "package-lock": LockFileFormat.PACKAGE_LOCK_JSON,
        "go-sum": LockFileFormat.GO_SUM,
        "gemfile-lock": LockFileFormat.GEMFILE_LOCK,
        "pom": LockFileFormat.POM_XML,
        "gradle-lock": LockFileFormat.GRADLE_LOCKFILE,
    }

    def detect(
        self,
        filename: str,
        content: str | None = None,
        explicit_format: str | None = None,
    ) -> FormatDetectionResult:
        """
        ファイル形式を検出する。

        Args:
            filename: ファイル名
            content: ファイル内容（オプション、将来のコンテンツベース検出用）
            explicit_format: 明示的な形式指定（CLI --format オプション）

        Returns:
            FormatDetectionResult: 検出結果

        Raises:
            ValueError: 無効なexplicit_formatが指定された場合
        """
        # 1. Explicit format takes highest priority
        if explicit_format and explicit_format != "auto":
            if explicit_format not in self.FORMAT_STRING_MAP:
                valid_formats = [k for k in self.FORMAT_STRING_MAP if k != "auto"]
                raise ValueError(
                    f"Unknown format: {explicit_format}. Supported: {', '.join(valid_formats)}"
                )
            return FormatDetectionResult(
                format=self.FORMAT_STRING_MAP[explicit_format],
                confidence=1.0,
                method="explicit",
            )

        # 2. Filename-based detection
        detected = self._detect_by_filename(filename)
        if detected:
            return FormatDetectionResult(
                format=detected,
                confidence=1.0,
                method="filename",
            )

        # 3. Content-based detection (future enhancement)
        # Currently not implemented - would check content structure

        # 4. Unknown format
        return FormatDetectionResult(
            format=None,
            confidence=0.0,
            method="unknown",
        )

    def detect_from_path(self, path: Path) -> FormatDetectionResult:
        """
        ファイルパスから形式を検出する。

        Args:
            path: ファイルパス

        Returns:
            FormatDetectionResult: 検出結果
        """
        return self.detect(path.name)

    def _detect_by_filename(self, filename: str) -> LockFileFormat | None:
        """
        ファイル名からフォーマットを検出する。

        Args:
            filename: ファイル名

        Returns:
            LockFileFormat | None: 検出されたフォーマット、またはNone
        """
        for format_type, patterns in self.FILENAME_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, filename, re.IGNORECASE):
                    return format_type
        return None

    @classmethod
    def get_supported_formats(cls) -> list[str]:
        """
        サポートされているCLI形式文字列のリストを取得する。

        Returns:
            list[str]: サポートされている形式文字列
        """
        return [k for k in cls.FORMAT_STRING_MAP if k != "auto"]
