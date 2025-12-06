"""RubyGems license resolver."""

import logging
from typing import Any, ClassVar

import httpx

from oss_license_scan.models import Dependency, Ecosystem, LicenseInfo
from oss_license_scan.resolvers.base import BaseLicenseResolver

logger = logging.getLogger(__name__)


class RubyGemsLicenseResolver(BaseLicenseResolver):
    """RubyGems.org からライセンス情報を取得するリゾルバ"""

    ECOSYSTEM: ClassVar[Ecosystem] = Ecosystem.RUBY
    API_URL: ClassVar[str] = "https://rubygems.org/api/v1"
    TIMEOUT: ClassVar[float] = 10.0

    def resolve(self, dependency: Dependency) -> LicenseInfo:
        """
        RubyGems.org からgemのライセンス情報を取得する。

        Args:
            dependency: 依存パッケージ情報

        Returns:
            LicenseInfo: ライセンス情報
        """
        version = dependency.version or "latest"
        gem_info = self._fetch_gem_info(dependency.name, version)

        if gem_info is None:
            return LicenseInfo(license=None, license_text_url=None, homepage_url=None)

        license_name = self._extract_license(gem_info)
        homepage_url = gem_info.get("homepage_uri")
        license_text_url = self._extract_license_url(gem_info, dependency.name)

        return LicenseInfo(
            license=license_name,
            license_text_url=license_text_url,
            homepage_url=homepage_url,
        )

    def _fetch_gem_info(self, name: str, version: str) -> dict[str, Any] | None:
        """
        RubyGems.org API からgem情報を取得する。

        Args:
            name: gem名
            version: バージョン

        Returns:
            gem情報の辞書、取得できない場合はNone
        """
        # まず特定バージョンを試す
        url = f"{self.API_URL}/versions/{name}.json"

        try:
            with httpx.Client(timeout=self.TIMEOUT) as client:
                response = client.get(url)
                if response.status_code == 200:
                    versions = response.json()
                    # Find the specific version
                    for v in versions:
                        if v.get("number") == version:
                            # Get detailed info
                            return self._fetch_gem_details(name, client)
                    # If specific version not found, return general info
                    return self._fetch_gem_details(name, client)
                elif response.status_code == 404:
                    return None
                logger.warning(f"RubyGems API returned {response.status_code} for {name}")
                return None
        except httpx.RequestError as e:
            logger.warning(f"Failed to fetch RubyGems info for {name}: {e}")
            return None

    def _fetch_gem_details(self, name: str, client: httpx.Client) -> dict[str, Any] | None:
        """
        gem の詳細情報を取得する。

        Args:
            name: gem名
            client: httpx クライアント

        Returns:
            gem情報の辞書
        """
        url = f"{self.API_URL}/gems/{name}.json"
        try:
            response = client.get(url)
            if response.status_code == 200:
                return response.json()
            return None
        except httpx.RequestError:
            return None

    def _extract_license(self, gem_info: dict[str, Any]) -> str | None:
        """
        gem情報からライセンス名を抽出する。

        RubyGems の licenses フィールドは文字列の配列。

        Args:
            gem_info: gem情報

        Returns:
            ライセンス名、見つからない場合はNone
        """
        licenses = gem_info.get("licenses")
        if not licenses:
            return None

        if isinstance(licenses, list):
            if len(licenses) == 0:
                return None
            elif len(licenses) == 1:
                return licenses[0]
            else:
                # Multiple licenses - return SPDX expression
                return " OR ".join(licenses)

        return None

    def _extract_license_url(self, gem_info: dict[str, Any], name: str) -> str | None:
        """
        gem情報からライセンステキストURLを抽出する。

        Args:
            gem_info: gem情報
            name: gem名

        Returns:
            ライセンステキストURL
        """
        # Prefer source_code_uri
        source_code_uri = gem_info.get("source_code_uri")
        if source_code_uri:
            return source_code_uri

        # Try project_uri
        project_uri = gem_info.get("project_uri")
        if project_uri:
            return project_uri

        # Fallback to RubyGems page
        return f"https://rubygems.org/gems/{name}"
