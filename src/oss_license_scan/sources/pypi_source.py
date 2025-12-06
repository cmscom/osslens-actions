"""PyPI API license source."""

import logging

import httpx

from oss_license_scan.license_utils import normalize_license_name
from oss_license_scan.models import LicenseResult, Package
from oss_license_scan.utils.http import http_client

logger = logging.getLogger(__name__)

PYPI_API_URL = "https://pypi.org/pypi"


class PyPISource:
    """PyPI APIからライセンス情報を取得するソース。

    PyPI JSON APIを使用してパッケージのライセンス情報を取得する。

    Example:
        >>> source = PyPISource()
        >>> result = source.resolve(Package(ecosystem="python", name="requests", version="2.31.0"))
        >>> print(result.license_spdx)  # Apache-2.0
    """

    @property
    def name(self) -> str:
        """ソース名を返す。"""
        return "pypi"

    @property
    def ecosystems(self) -> list[str] | None:
        """対応エコシステムを返す。"""
        return ["python"]

    def resolve(self, pkg: Package) -> LicenseResult | None:
        """パッケージのライセンス情報を解決する。

        Args:
            pkg: 対象パッケージ

        Returns:
            LicenseResult: 取得成功時
            None: 取得失敗時
        """
        url = f"{PYPI_API_URL}/{pkg.name}/{pkg.version}/json"

        try:
            with http_client() as client:
                response = client.get(url)

                if response.status_code != 200:
                    # バージョン指定なしで試す
                    url = f"{PYPI_API_URL}/{pkg.name}/json"
                    response = client.get(url)
                    if response.status_code != 200:
                        logger.debug(f"PyPI returned {response.status_code} for {pkg.name}")
                        return None

                data = response.json()
                info = data.get("info", {})

                # ライセンス情報を抽出
                raw_license = info.get("license")
                if not raw_license:
                    # classifiersからライセンスを抽出
                    classifiers = info.get("classifiers", [])
                    raw_license = self._extract_license_from_classifiers(classifiers)

                if not raw_license:
                    return None

                # SPDX IDに正規化
                license_spdx = normalize_license_name(raw_license)

                return LicenseResult(
                    source_name=self.name,
                    package=pkg,
                    license_spdx=license_spdx,
                    raw_license=raw_license,
                    confidence=1.0 if license_spdx else 0.8,
                    evidence_path=info.get("project_url")
                    or f"https://pypi.org/project/{pkg.name}/",
                )

        except httpx.RequestError as e:
            logger.warning(f"Failed to fetch PyPI info for {pkg.name}: {e}")
            return None

    def _extract_license_from_classifiers(self, classifiers: list[str]) -> str | None:
        """classifiersからライセンス情報を抽出する。

        Args:
            classifiers: PyPI classifiersリスト

        Returns:
            ライセンス名、見つからない場合はNone
        """
        for classifier in classifiers:
            if classifier.startswith("License :: OSI Approved ::"):
                # "License :: OSI Approved :: MIT License" -> "MIT License"
                parts = classifier.split("::")
                if len(parts) >= 3:
                    return parts[-1].strip()
        return None
