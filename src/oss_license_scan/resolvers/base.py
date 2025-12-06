"""Base classes for license resolvers."""

from abc import ABC, abstractmethod
from typing import ClassVar

from oss_license_scan.models import Dependency, Ecosystem, LicenseInfo


class BaseLicenseResolver(ABC):
    """ライセンスリゾルバ基底クラス"""

    ECOSYSTEM: ClassVar[Ecosystem]

    @abstractmethod
    def resolve(self, dependency: Dependency) -> LicenseInfo:
        """
        パッケージのライセンス情報を取得する。

        Args:
            dependency: 依存パッケージ情報

        Returns:
            LicenseInfo: ライセンス情報

        Note:
            取得できない場合はlicense=Noneを返す
        """
        ...

    async def resolve_async(self, dependency: Dependency) -> LicenseInfo:
        """非同期でライセンス情報を取得する（デフォルトは同期版を呼び出す）"""
        return self.resolve(dependency)
