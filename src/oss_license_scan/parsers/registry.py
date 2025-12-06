"""Parser registry for lock file parsers."""

from typing import TYPE_CHECKING

from oss_license_scan.models import LockFileFormat

if TYPE_CHECKING:
    from oss_license_scan.parsers.base import BaseLockFileParser


class ParserRegistry:
    """パーサーレジストリ"""

    _parsers: dict[LockFileFormat, type["BaseLockFileParser"]] = {}

    @classmethod
    def register(cls, parser_class: type["BaseLockFileParser"]) -> None:
        """パーサーを登録する"""
        cls._parsers[parser_class.FORMAT] = parser_class

    @classmethod
    def get(cls, format: LockFileFormat) -> "BaseLockFileParser":
        """フォーマットに対応するパーサーを取得する"""
        if format not in cls._parsers:
            raise ValueError(f"No parser registered for {format}")
        return cls._parsers[format]()

    @classmethod
    def detect(cls, filename: str, content: str | None = None) -> LockFileFormat | None:
        """ファイルに対応するフォーマットを検出する"""
        for parser_class in cls._parsers.values():
            parser = parser_class()
            if parser.can_parse(filename, content):
                return parser_class.FORMAT
        return None

    @classmethod
    def all_formats(cls) -> list[LockFileFormat]:
        """登録されている全フォーマットを取得する"""
        return list(cls._parsers.keys())
