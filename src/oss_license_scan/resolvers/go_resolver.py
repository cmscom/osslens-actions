"""Go module license resolver."""

import logging
import re
from typing import Any, ClassVar

import httpx

from oss_license_scan.models import Dependency, Ecosystem, LicenseInfo
from oss_license_scan.resolvers.base import BaseLicenseResolver

logger = logging.getLogger(__name__)


class GoLicenseResolver(BaseLicenseResolver):
    """pkg.go.dev および GitHub からライセンス情報を取得するリゾルバ"""

    ECOSYSTEM: ClassVar[Ecosystem] = Ecosystem.GO
    PKG_GO_DEV_URL: ClassVar[str] = "https://pkg.go.dev"
    GITHUB_API_URL: ClassVar[str] = "https://api.github.com"
    TIMEOUT: ClassVar[float] = 10.0

    def resolve(self, dependency: Dependency) -> LicenseInfo:
        """
        Go モジュールのライセンス情報を取得する。

        Args:
            dependency: 依存パッケージ情報

        Returns:
            LicenseInfo: ライセンス情報
        """
        version = dependency.version or "latest"
        module_info = self._fetch_module_info(dependency.name, version)

        license_name = None
        if module_info:
            license_name = module_info.get("license")

        # pkg.go.dev でライセンスが見つからない場合、GitHub API を試す
        if not license_name:
            github_license = self._fetch_github_license(dependency.name)
            if github_license:
                license_name = github_license

        homepage_url = self._get_homepage_url(dependency.name, module_info)
        license_text_url = self._get_license_text_url(dependency.name)

        return LicenseInfo(
            license=license_name,
            license_text_url=license_text_url,
            homepage_url=homepage_url,
        )

    def _fetch_module_info(self, name: str, version: str) -> dict[str, Any] | None:
        """
        pkg.go.dev からモジュール情報を取得する。

        Note: pkg.go.dev には公式 API がないため、GitHub API をフォールバックとして使用。

        Args:
            name: モジュールパス
            version: バージョン

        Returns:
            モジュール情報の辞書、取得できない場合はNone
        """
        # pkg.go.dev の JSON API は限定的なため、基本情報のみ返す
        # 実際のライセンス情報は GitHub API から取得
        github_repo = self._extract_github_repo(name)
        if github_repo:
            return {"homepage": f"https://github.com/{github_repo}"}
        return {}

    def _fetch_github_license(self, module_name: str) -> str | None:
        """
        GitHub API からライセンス情報を取得する。

        Args:
            module_name: Go モジュールパス

        Returns:
            ライセンス名、見つからない場合はNone
        """
        github_repo = self._extract_github_repo(module_name)
        if not github_repo:
            return None

        url = f"{self.GITHUB_API_URL}/repos/{github_repo}/license"

        try:
            with httpx.Client(timeout=self.TIMEOUT) as client:
                response = client.get(url, headers={"Accept": "application/vnd.github.v3+json"})
                if response.status_code == 200:
                    data = response.json()
                    license_info = data.get("license", {})
                    return license_info.get("spdx_id")
                return None
        except httpx.RequestError as e:
            logger.warning(f"Failed to fetch GitHub license for {module_name}: {e}")
            return None

    def _extract_github_repo(self, module_name: str) -> str | None:
        """
        Go モジュールパスから GitHub リポジトリを抽出する。

        Args:
            module_name: Go モジュールパス (例: github.com/user/repo/v2)

        Returns:
            GitHub リポジトリパス (例: user/repo)、GitHub でない場合はNone
        """
        if not module_name.startswith("github.com/"):
            return None

        # Remove github.com/ prefix
        path = module_name[11:]

        # Split by /
        parts = path.split("/")

        if len(parts) < 2:
            return None

        # user/repo の形式を返す（/v2, /v3, サブパッケージは除外）
        user = parts[0]
        repo = parts[1]

        # /v2, /v3 などのバージョンサフィックスを除去
        if re.match(r"^v\d+$", repo):
            return None

        return f"{user}/{repo}"

    def _get_homepage_url(self, module_name: str, module_info: dict[str, Any] | None) -> str | None:
        """
        モジュールのホームページURLを取得する。

        Args:
            module_name: モジュールパス
            module_info: モジュール情報

        Returns:
            ホームページURL
        """
        if module_info and module_info.get("homepage"):
            return module_info["homepage"]

        github_repo = self._extract_github_repo(module_name)
        if github_repo:
            return f"https://github.com/{github_repo}"

        # pkg.go.dev URL
        return f"{self.PKG_GO_DEV_URL}/{module_name}"

    def _get_license_text_url(self, module_name: str) -> str | None:
        """
        ライセンステキストのURLを取得する。

        Args:
            module_name: モジュールパス

        Returns:
            ライセンステキストURL
        """
        github_repo = self._extract_github_repo(module_name)
        if github_repo:
            return f"https://github.com/{github_repo}"

        return f"{self.PKG_GO_DEV_URL}/{module_name}?tab=licenses"
