"""Go licenses source."""

import logging

import httpx

from oss_license_scan.models import LicenseResult, Package
from oss_license_scan.utils.http import HttpClientConfig, http_client

logger = logging.getLogger(__name__)

GO_PKG_URL = "https://pkg.go.dev"


class GoLicensesSource:
    """pkg.go.devからライセンス情報を取得するソース。

    Go言語パッケージのライセンス情報をpkg.go.devから取得する。

    Note:
        pkg.go.devはAPIが限定的なため、HTMLパースまたは
        外部ツール（go-licenses）の結果を使用する場合がある。

    Example:
        >>> source = GoLicensesSource()
        >>> result = source.resolve(Package(ecosystem="go", name="github.com/gorilla/mux", version="v1.8.0"))
    """

    @property
    def name(self) -> str:
        """ソース名を返す。"""
        return "go_licenses"

    @property
    def ecosystems(self) -> list[str] | None:
        """対応エコシステムを返す。"""
        return ["go"]

    def resolve(self, pkg: Package) -> LicenseResult | None:
        """パッケージのライセンス情報を解決する。

        Args:
            pkg: 対象パッケージ

        Returns:
            LicenseResult: 取得成功時
            None: 取得失敗時
        """
        # pkg.go.devのライセンスページにアクセス
        module_path = pkg.name
        version = pkg.version

        # バージョンプレフィックスを正規化
        if version and not version.startswith("v"):
            version = f"v{version}"

        url = f"{GO_PKG_URL}/{module_path}@{version}?tab=licenses"

        try:
            config = HttpClientConfig(follow_redirects=True)
            with http_client(config) as client:
                response = client.get(url)

                if response.status_code != 200:
                    logger.debug(f"pkg.go.dev returned {response.status_code} for {pkg.name}")
                    return None

                # 簡易的なHTMLパースでライセンス情報を抽出
                html = response.text
                license_spdx = self._extract_license_from_html(html)

                if not license_spdx:
                    return None

                return LicenseResult(
                    source_name=self.name,
                    package=pkg,
                    license_spdx=license_spdx,
                    raw_license=license_spdx,
                    confidence=0.9,  # HTMLパースのため若干低め
                    evidence_path=f"{GO_PKG_URL}/{module_path}@{version}?tab=licenses",
                )

        except httpx.RequestError as e:
            logger.warning(f"Failed to fetch go package info for {pkg.name}: {e}")
            return None

    def _extract_license_from_html(self, html: str) -> str | None:
        """HTMLからライセンス情報を抽出する。

        pkg.go.devのライセンスページから主要なライセンス識別子を抽出。

        Args:
            html: HTMLコンテンツ

        Returns:
            ライセンス名、見つからない場合はNone
        """
        # 一般的なライセンスパターンをチェック
        license_patterns = [
            ("MIT", "MIT"),
            ("Apache-2.0", "Apache-2.0"),
            ("BSD-3-Clause", "BSD-3-Clause"),
            ("BSD-2-Clause", "BSD-2-Clause"),
            ("ISC", "ISC"),
            ("MPL-2.0", "MPL-2.0"),
            ("GPL-3.0", "GPL-3.0"),
            ("GPL-2.0", "GPL-2.0"),
            ("LGPL-3.0", "LGPL-3.0"),
            ("Unlicense", "Unlicense"),
        ]

        html_lower = html.lower()
        for pattern, spdx in license_patterns:
            # ライセンスセクション内でパターンを探す
            if pattern.lower() in html_lower:
                return spdx

        return None
