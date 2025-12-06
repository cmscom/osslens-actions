"""Resolver registry for license resolvers."""

from typing import TYPE_CHECKING

from oss_license_scan.models import Ecosystem

if TYPE_CHECKING:
    from oss_license_scan.resolvers.base import BaseLicenseResolver


class ResolverRegistry:
    """リゾルバレジストリ"""

    _resolvers: dict[Ecosystem, type["BaseLicenseResolver"]] = {}

    @classmethod
    def register(cls, resolver_class: type["BaseLicenseResolver"]) -> None:
        """リゾルバを登録する"""
        cls._resolvers[resolver_class.ECOSYSTEM] = resolver_class

    @classmethod
    def get(cls, ecosystem: Ecosystem) -> "BaseLicenseResolver":
        """エコシステムに対応するリゾルバを取得する"""
        if ecosystem not in cls._resolvers:
            raise ValueError(f"No resolver registered for {ecosystem}")
        return cls._resolvers[ecosystem]()
