"""npm registry license source."""

import logging
from typing import Any

import httpx

from oss_license_scan.models import LicenseResult, Package
from oss_license_scan.utils.http import http_client

logger = logging.getLogger(__name__)

NPM_REGISTRY_URL = "https://registry.npmjs.org"


class NpmRegistrySource:
    """npm registryからライセンス情報を取得するソース。

    npm registry APIを使用してパッケージのライセンス情報を取得する。

    Example:
        >>> source = NpmRegistrySource()
        >>> result = source.resolve(Package(ecosystem="npm", name="lodash", version="4.17.21"))
        >>> print(result.license_spdx)  # MIT
    """

    @property
    def name(self) -> str:
        """ソース名を返す。"""
        return "npm_registry"

    @property
    def ecosystems(self) -> list[str] | None:
        """対応エコシステムを返す。"""
        return ["npm"]

    def resolve(self, pkg: Package) -> LicenseResult | None:
        """パッケージのライセンス情報を解決する。

        Args:
            pkg: 対象パッケージ

        Returns:
            LicenseResult: 取得成功時
            None: 取得失敗時
        """
        # スコープ付きパッケージのエンコード
        encoded_name = pkg.name.replace("/", "%2F")
        url = f"{NPM_REGISTRY_URL}/{encoded_name}/{pkg.version}"

        try:
            with http_client() as client:
                response = client.get(url)

                if response.status_code == 404:
                    # バージョン指定なしで試す
                    url = f"{NPM_REGISTRY_URL}/{encoded_name}"
                    response = client.get(url)

                if response.status_code != 200:
                    logger.debug(f"npm registry returned {response.status_code} for {pkg.name}")
                    return None

                data = response.json()

                # バージョン情報がある場合はそれを使用
                if "versions" in data and pkg.version in data["versions"]:
                    data = data["versions"][pkg.version]

                # ライセンス情報を抽出
                raw_license = self._extract_license(data)

                homepage = data.get("homepage")
                repository = self._extract_repository_url(data)

                # GitHubリポジトリ情報をパッケージのextraに追加（フォールバック用）
                github_repo = self._extract_github_repo_from_url(repository)
                if github_repo:
                    pkg.extra["github_repo"] = github_repo

                if not raw_license:
                    return None

                return LicenseResult(
                    source_name=self.name,
                    package=pkg,
                    license_spdx=raw_license,  # npmはSPDX形式が多い
                    raw_license=raw_license,
                    confidence=1.0,
                    evidence_path=homepage
                    or repository
                    or f"https://www.npmjs.com/package/{pkg.name}",
                )

        except httpx.RequestError as e:
            logger.warning(f"Failed to fetch npm info for {pkg.name}: {e}")
            return None

    def _extract_license(self, data: dict[str, Any]) -> str | None:
        """パッケージ情報からライセンスを抽出する。

        Args:
            data: パッケージ情報

        Returns:
            ライセンス名、見つからない場合はNone
        """
        license_field = data.get("license")
        if license_field:
            if isinstance(license_field, str):
                return license_field
            elif isinstance(license_field, dict):
                return license_field.get("type")

        # 旧形式: licenses配列
        licenses_field = data.get("licenses")
        if licenses_field and isinstance(licenses_field, list) and len(licenses_field) > 0:
            first = licenses_field[0]
            if isinstance(first, dict):
                return first.get("type")

        return None

    def _extract_repository_url(self, data: dict[str, Any]) -> str | None:
        """リポジトリURLを抽出する。

        Args:
            data: パッケージ情報

        Returns:
            リポジトリURL、見つからない場合はNone
        """
        repository = data.get("repository")
        if not repository:
            return None

        if isinstance(repository, str):
            return self._clean_git_url(repository)
        elif isinstance(repository, dict):
            url = repository.get("url")
            if url:
                return self._clean_git_url(url)

        return None

    def _clean_git_url(self, url: str) -> str:
        """Git URLをクリーンなHTTPS URLに変換する。

        Args:
            url: Git URL

        Returns:
            クリーンなURL
        """
        if url.startswith("git+"):
            url = url[4:]
        if url.startswith("git://"):
            url = "https://" + url[6:]
        if url.endswith(".git"):
            url = url[:-4]
        return url

    def _extract_github_repo_from_url(self, url: str | None) -> str | None:
        """URLからGitHubリポジトリ情報を抽出する。

        Args:
            url: リポジトリURL

        Returns:
            GitHubリポジトリ（owner/repo形式）、抽出できない場合はNone
        """
        if not url:
            return None

        # github.com/owner/repo 形式を抽出
        if "github.com" in url:
            # URLをパース
            cleaned = self._clean_git_url(url)
            # https://github.com/owner/repo または github.com/owner/repo
            if "github.com/" in cleaned:
                parts = cleaned.split("github.com/")[1].split("/")
                if len(parts) >= 2:
                    return f"{parts[0]}/{parts[1]}"

        return None
