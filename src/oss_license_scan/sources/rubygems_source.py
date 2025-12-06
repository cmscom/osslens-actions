"""RubyGems.org license source."""

import logging

import httpx

from oss_license_scan.models import LicenseResult, Package
from oss_license_scan.utils.http import http_client

logger = logging.getLogger(__name__)

RUBYGEMS_API_URL = "https://rubygems.org/api/v1/gems"


class RubyGemsSource:
    """RubyGems.org APIからライセンス情報を取得するソース。

    RubyGems.org APIを使用してgemのライセンス情報を取得する。

    Example:
        >>> source = RubyGemsSource()
        >>> result = source.resolve(Package(ecosystem="ruby", name="rails", version="7.1.0"))
        >>> print(result.license_spdx)  # MIT
    """

    @property
    def name(self) -> str:
        """ソース名を返す。"""
        return "rubygems"

    @property
    def ecosystems(self) -> list[str] | None:
        """対応エコシステムを返す。"""
        return ["ruby"]

    def resolve(self, pkg: Package) -> LicenseResult | None:
        """パッケージのライセンス情報を解決する。

        Args:
            pkg: 対象パッケージ

        Returns:
            LicenseResult: 取得成功時
            None: 取得失敗時
        """
        url = f"{RUBYGEMS_API_URL}/{pkg.name}.json"

        try:
            with http_client() as client:
                response = client.get(url)

                if response.status_code != 200:
                    logger.debug(f"RubyGems returned {response.status_code} for {pkg.name}")
                    return None

                data = response.json()

                # licensesフィールドを取得
                licenses = data.get("licenses")
                if not licenses or not isinstance(licenses, list) or len(licenses) == 0:
                    return None

                # 最初のライセンスを使用
                raw_license = licenses[0] if licenses else None
                if not raw_license:
                    return None

                homepage = data.get("homepage_uri")
                source_code = data.get("source_code_uri")

                return LicenseResult(
                    source_name=self.name,
                    package=pkg,
                    license_spdx=raw_license,
                    raw_license=raw_license,
                    confidence=1.0,
                    evidence_path=homepage
                    or source_code
                    or f"https://rubygems.org/gems/{pkg.name}",
                )

        except httpx.RequestError as e:
            logger.warning(f"Failed to fetch RubyGems info for {pkg.name}: {e}")
            return None
