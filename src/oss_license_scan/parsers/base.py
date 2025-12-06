"""Base classes for lock file parsers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from oss_license_scan.models import Ecosystem, LockFileFormat, ParseResult


class ParseError(Exception):
    """パースエラー例外クラス"""

    def __init__(
        self,
        message: str,
        filename: str | None = None,
        line: int | None = None,
        column: int | None = None,
    ):
        self.message = message
        self.filename = filename
        self.line = line
        self.column = column
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        parts = [self.message]
        if self.filename:
            parts.append(f"in {self.filename}")
        if self.line:
            location = f"line {self.line}"
            if self.column:
                location += f", column {self.column}"
            parts.append(f"at {location}")
        return " ".join(parts)


class BaseLockFileParser(ABC):
    """ロックファイルパーサー基底クラス"""

    # クラス変数: サブクラスで定義必須
    FORMAT: ClassVar[LockFileFormat]
    ECOSYSTEM: ClassVar[Ecosystem]
    FILENAME_PATTERNS: ClassVar[list[str]]

    @abstractmethod
    def parse(self, content: str) -> ParseResult:
        """
        ロックファイルをパースして依存関係を抽出する。

        Args:
            content: ファイル内容

        Returns:
            ParseResult: パース結果

        Raises:
            ParseError: パース失敗時
        """
        ...

    def parse_file(self, file_path: Path) -> ParseResult:
        """
        ファイルからパースする。

        Args:
            file_path: ファイルパス

        Returns:
            ParseResult: パース結果

        Raises:
            FileNotFoundError: ファイルが存在しない場合
            ParseError: パース失敗時
        """
        content = file_path.read_text(encoding="utf-8")
        return self.parse(content)

    def can_parse(self, filename: str, content: str | None = None) -> bool:
        """
        このパーサーが処理可能か判定する。

        Args:
            filename: ファイル名
            content: ファイル内容（オプション）

        Returns:
            bool: 処理可能ならTrue
        """
        import re

        for pattern in self.FILENAME_PATTERNS:
            if re.match(pattern, filename, re.IGNORECASE):
                return True
        return False
