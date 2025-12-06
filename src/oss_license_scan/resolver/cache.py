"""Source cache for license resolution results."""

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

# デフォルトキャッシュTTL（時間）
DEFAULT_CACHE_TTL_HOURS = 24


class SourceCacheEntry(BaseModel):
    """LicenseSourceキャッシュエントリ。

    ライセンス情報取得結果をキャッシュするためのモデル。
    SQLiteテーブルに保存される。
    """

    cache_key: str = Field(..., description="Primary Key: source_name:ecosystem:name:version")
    source_name: str = Field(..., description="ソース名")
    package_key: str = Field(..., description="パッケージキー（ecosystem:name@version）")
    license_spdx: str | None = Field(None, description="SPDX ID（正規化後）")
    raw_license: str | None = Field(None, description="元のライセンス文字列")
    confidence: float = Field(default=1.0, description="信頼度スコア")
    evidence_path: str | None = Field(None, description="証拠パス/URL")
    created_at: datetime = Field(..., description="作成日時")
    expires_at: datetime = Field(..., description="有効期限")

    def is_expired(self) -> bool:
        """エントリが期限切れかどうかを判定する。

        Returns:
            bool: 期限切れならTrue
        """
        return datetime.now(UTC) > self.expires_at

    @classmethod
    def create(
        cls,
        source_name: str,
        package_key: str,
        license_spdx: str | None,
        raw_license: str | None,
        confidence: float = 1.0,
        evidence_path: str | None = None,
        ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
    ) -> "SourceCacheEntry":
        """新しいキャッシュエントリを作成する。

        Args:
            source_name: ソース名
            package_key: パッケージキー
            license_spdx: SPDX ID
            raw_license: 元のライセンス文字列
            confidence: 信頼度
            evidence_path: 証拠パス
            ttl_hours: TTL（時間）

        Returns:
            SourceCacheEntry: 新しいエントリ
        """
        now = datetime.now(UTC)
        # cache_keyはsource_name + package_keyから生成
        cache_key = f"{source_name}:{package_key}"

        return cls(
            cache_key=cache_key,
            source_name=source_name,
            package_key=package_key,
            license_spdx=license_spdx,
            raw_license=raw_license,
            confidence=confidence,
            evidence_path=evidence_path,
            created_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
        )
