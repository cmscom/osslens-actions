"""Adapter to wrap existing BaseLicenseResolver as LicenseSource."""

from oss_license_scan.models import (
    Dependency,
    Ecosystem,
    LicenseResult,
    Package,
)
from oss_license_scan.resolvers.base import BaseLicenseResolver


class ResolverAdapter:
    """既存のBaseLicenseResolverをLicenseSourceに変換するアダプター。

    既存のリゾルバ実装を新しいLicenseSourceインターフェースで
    使用可能にするアダプターパターンの実装。

    Example:
        >>> from oss_license_scan.resolvers.npm_resolver import NpmLicenseResolver
        >>> adapter = ResolverAdapter(NpmLicenseResolver())
        >>> result = adapter.resolve(package)
    """

    def __init__(self, resolver: BaseLicenseResolver) -> None:
        """アダプターを初期化する。

        Args:
            resolver: ラップする既存リゾルバ
        """
        self.resolver = resolver
        self._name = f"resolver_{resolver.ECOSYSTEM.value}"
        self._ecosystems = [resolver.ECOSYSTEM.value]

    @property
    def name(self) -> str:
        """ソース名を返す。"""
        return self._name

    @property
    def ecosystems(self) -> list[str] | None:
        """対応エコシステムを返す。"""
        return self._ecosystems

    def resolve(self, pkg: Package) -> LicenseResult | None:
        """パッケージのライセンス情報を解決する。

        Args:
            pkg: 対象パッケージ

        Returns:
            LicenseResult: 取得成功時
            None: 取得失敗時
        """
        # PackageをDependencyに変換
        # extra から取得した値を str | None にキャスト
        group_id = pkg.extra.get("group_id")
        artifact_id = pkg.extra.get("artifact_id")
        module_path = pkg.extra.get("module_path")
        dep = Dependency(
            name=pkg.name,
            version=pkg.version,
            ecosystem=Ecosystem(pkg.ecosystem) if pkg.ecosystem else None,
            group_id=str(group_id) if group_id else None,
            artifact_id=str(artifact_id) if artifact_id else None,
            module_path=str(module_path) if module_path else None,
        )

        # 既存リゾルバでライセンス情報を取得
        license_info = self.resolver.resolve(dep)

        # ライセンス情報がない場合はNone
        if license_info.license is None:
            return None

        # LicenseResultに変換
        return LicenseResult(
            source_name=self.name,
            package=pkg,
            license_spdx=license_info.license,
            raw_license=license_info.license,
            confidence=1.0,
            evidence_path=license_info.license_text_url or license_info.homepage_url,
        )
