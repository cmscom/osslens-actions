"""SourceRegistry for managing LicenseSource implementations."""

from oss_license_scan.sources.base import LicenseSource

# デフォルトのソース優先順序
DEFAULT_SOURCE_ORDER = [
    "local",  # 1. ローカルファイル（最速・オフライン可）
    "pypi",  # 2. レジストリAPI
    "npm_registry",
    "go_licenses",
    "rubygems",
    "maven_central",
    "github",  # 3. GitHub（フォールバック）
    "overrides",  # 4. 手動オーバーライド（最終上書き）
]


class SourceRegistry:
    """LicenseSourceの登録・管理を行うレジストリ。

    ソースの登録、取得、優先順位付けを管理する。

    Example:
        >>> registry = SourceRegistry()
        >>> registry.register(PyPISource())
        >>> registry.register(NpmRegistrySource())
        >>> sources = registry.get_for_ecosystem("python")
        >>> for src in sources:
        ...     result = src.resolve(pkg)
        ...     if result:
        ...         break
    """

    def __init__(self) -> None:
        """レジストリを初期化。"""
        self._sources: dict[str, LicenseSource] = {}
        self._order: list[str] = list(DEFAULT_SOURCE_ORDER)

    def register(self, source: LicenseSource) -> None:
        """ソースを登録する。

        Args:
            source: 登録するLicenseSource実装
        """
        self._sources[source.name] = source

    def get(self, name: str) -> LicenseSource | None:
        """名前でソースを取得する。

        Args:
            name: ソース名

        Returns:
            LicenseSource: 見つかった場合
            None: 見つからない場合
        """
        return self._sources.get(name)

    def get_for_ecosystem(self, ecosystem: str) -> list[LicenseSource]:
        """エコシステムに対応するソースを優先順位順で取得する。

        Args:
            ecosystem: エコシステム名（例: "python", "npm"）

        Returns:
            list[LicenseSource]: 対応するソースのリスト（優先順位順）
        """
        result: list[LicenseSource] = []

        for name in self._order:
            source = self._sources.get(name)
            if source is None:
                continue

            # ecosystemsがNoneなら全エコシステム対応
            if source.ecosystems is None:
                result.append(source)
            elif ecosystem in source.ecosystems:
                result.append(source)

        return result

    def get_ordered(self, names: list[str] | None = None) -> list[LicenseSource]:
        """指定順序でソースを取得する。

        Args:
            names: ソース名のリスト（優先順）。Noneはデフォルト順序。

        Returns:
            list[LicenseSource]: 指定順序のソースリスト
        """
        order = names if names is not None else self._order
        result: list[LicenseSource] = []

        for name in order:
            source = self._sources.get(name)
            if source is not None:
                result.append(source)

        return result

    def list_all(self) -> list[str]:
        """登録されている全ソース名を取得する。

        Returns:
            list[str]: ソース名のリスト
        """
        return list(self._sources.keys())

    def set_order(self, order: list[str]) -> None:
        """ソースの優先順序を設定する。

        Args:
            order: ソース名のリスト（優先順）
        """
        self._order = list(order)
