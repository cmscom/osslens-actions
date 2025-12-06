"""npm registry license resolver."""

import logging
from typing import Any, ClassVar

import httpx

from oss_license_scan.models import Dependency, Ecosystem, LicenseInfo
from oss_license_scan.resolvers.base import BaseLicenseResolver

logger = logging.getLogger(__name__)


class NpmLicenseResolver(BaseLicenseResolver):
    """npm registry からライセンス情報を取得するリゾルバ"""

    ECOSYSTEM: ClassVar[Ecosystem] = Ecosystem.NPM
    REGISTRY_URL: ClassVar[str] = "https://registry.npmjs.org"
    TIMEOUT: ClassVar[float] = 10.0

    def resolve(self, dependency: Dependency) -> LicenseInfo:
        """
        npm registry からパッケージのライセンス情報を取得する。

        Args:
            dependency: 依存パッケージ情報

        Returns:
            LicenseInfo: ライセンス情報
        """
        version = dependency.version or "latest"
        package_info = self._fetch_package_info(dependency.name, version)

        if package_info is None:
            return LicenseInfo(license=None, license_text_url=None, homepage_url=None)

        license_name = self._extract_license(package_info)
        homepage_url = package_info.get("homepage")
        license_text_url = self._extract_license_url(package_info)

        return LicenseInfo(
            license=license_name,
            license_text_url=license_text_url,
            homepage_url=homepage_url,
        )

    def _fetch_package_info(self, name: str, version: str) -> dict[str, Any] | None:
        """
        npm registry からパッケージ情報を取得する。

        Args:
            name: パッケージ名（スコープ付きも対応: @types/node）
            version: バージョン

        Returns:
            パッケージ情報の辞書、取得できない場合はNone
        """
        # URL encode scoped packages (@ -> %40, / -> %2F)
        encoded_name = name.replace("/", "%2F")
        url = f"{self.REGISTRY_URL}/{encoded_name}/{version}"

        try:
            with httpx.Client(timeout=self.TIMEOUT) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    # Try to get latest version info
                    url = f"{self.REGISTRY_URL}/{encoded_name}"
                    response = client.get(url)
                    if response.status_code == 200:
                        data = response.json()
                        # Get info from versions or latest
                        if "versions" in data and version in data["versions"]:
                            return data["versions"][version]
                        return data
                logger.warning(f"npm registry returned {response.status_code} for {name}@{version}")
                return None
        except httpx.RequestError as e:
            logger.warning(f"Failed to fetch npm package info for {name}: {e}")
            return None

    def _extract_license(self, package_info: dict[str, Any]) -> str | None:
        """
        パッケージ情報からライセンス名を抽出する。

        npm package.json の license フィールドは以下の形式がある:
        - 文字列: "MIT"
        - オブジェクト: {"type": "MIT", "url": "..."}
        - 配列（旧形式）: [{"type": "MIT"}, {"type": "Apache-2.0"}]

        Args:
            package_info: パッケージ情報

        Returns:
            ライセンス名、見つからない場合はNone
        """
        # 新形式: license フィールド
        license_field = package_info.get("license")
        if license_field:
            if isinstance(license_field, str):
                return license_field
            elif isinstance(license_field, dict):
                return license_field.get("type")

        # 旧形式: licenses 配列
        licenses_field = package_info.get("licenses")
        if licenses_field and isinstance(licenses_field, list) and len(licenses_field) > 0:
            first_license = licenses_field[0]
            if isinstance(first_license, dict):
                return first_license.get("type")

        return None

    def _extract_license_url(self, package_info: dict[str, Any]) -> str | None:
        """
        パッケージ情報からライセンステキストURLを抽出する。

        repository フィールドからGitHubのURLを抽出し、LICENSE ファイルへのリンクを生成。

        Args:
            package_info: パッケージ情報

        Returns:
            ライセンステキストURL、見つからない場合はNone
        """
        repository = package_info.get("repository")
        if not repository:
            return None

        repo_url = None
        if isinstance(repository, str):
            repo_url = repository
        elif isinstance(repository, dict):
            repo_url = repository.get("url")

        if not repo_url:
            return None

        # git+https://... or git://... を https:// に変換
        repo_url = self._clean_git_url(repo_url)

        # GitHub URLの場合、LICENSE ファイルへのリンクを生成
        if "github.com" in repo_url:
            # Remove .git suffix
            if repo_url.endswith(".git"):
                repo_url = repo_url[:-4]
            return repo_url

        return repo_url

    def _clean_git_url(self, url: str) -> str:
        """
        Git URL を通常の HTTPS URL に変換する。

        Args:
            url: Git URL (例: git+https://github.com/user/repo.git)

        Returns:
            クリーンな HTTPS URL
        """
        # Remove git+ prefix
        if url.startswith("git+"):
            url = url[4:]

        # Convert git:// to https://
        if url.startswith("git://"):
            url = "https://" + url[6:]

        # Remove .git suffix
        if url.endswith(".git"):
            url = url[:-4]

        return url
