"""Maven Central license source."""

import logging
from xml.etree import ElementTree

import httpx

from oss_license_scan.models import LicenseResult, Package
from oss_license_scan.utils.http import http_client

logger = logging.getLogger(__name__)

MAVEN_CENTRAL_URL = "https://repo1.maven.org/maven2"


class MavenCentralSource:
    """Maven Centralからライセンス情報を取得するソース。

    Maven Central RepositoryのPOMファイルからライセンス情報を取得する。

    Example:
        >>> source = MavenCentralSource()
        >>> pkg = Package(
        ...     ecosystem="maven",
        ...     name="commons-lang3",
        ...     version="3.12.0",
        ...     extra={"group_id": "org.apache.commons", "artifact_id": "commons-lang3"}
        ... )
        >>> result = source.resolve(pkg)
        >>> print(result.license_spdx)  # Apache-2.0
    """

    @property
    def name(self) -> str:
        """ソース名を返す。"""
        return "maven_central"

    @property
    def ecosystems(self) -> list[str] | None:
        """対応エコシステムを返す。"""
        return ["maven"]

    def resolve(self, pkg: Package) -> LicenseResult | None:
        """パッケージのライセンス情報を解決する。

        Args:
            pkg: 対象パッケージ

        Returns:
            LicenseResult: 取得成功時
            None: 取得失敗時
        """
        # extraからgroupIdとartifactIdを取得
        raw_group_id = pkg.extra.get("group_id")
        raw_artifact_id = pkg.extra.get("artifact_id")
        group_id: str = str(raw_group_id) if raw_group_id else ""
        artifact_id: str = str(raw_artifact_id) if raw_artifact_id else pkg.name

        if not group_id:
            # パッケージ名からgroupIdを推測
            if ":" in pkg.name:
                group_id, artifact_id = pkg.name.split(":", 1)
            else:
                logger.debug(f"Missing group_id for Maven package {pkg.name}")
                return None

        # POMファイルのURLを構築
        group_path = group_id.replace(".", "/")
        pom_url = f"{MAVEN_CENTRAL_URL}/{group_path}/{artifact_id}/{pkg.version}/{artifact_id}-{pkg.version}.pom"

        try:
            with http_client() as client:
                response = client.get(pom_url)

                if response.status_code != 200:
                    logger.debug(f"Maven Central returned {response.status_code} for {pkg.name}")
                    return None

                # POMをパース
                license_info = self._parse_pom_licenses(response.text)
                if not license_info:
                    return None

                raw_license, license_url = license_info

                # ライセンス名をSPDX IDに正規化
                license_spdx = self._normalize_maven_license(raw_license)

                return LicenseResult(
                    source_name=self.name,
                    package=pkg,
                    license_spdx=license_spdx,
                    raw_license=raw_license,
                    confidence=1.0 if license_spdx else 0.8,
                    evidence_path=license_url or pom_url,
                )

        except httpx.RequestError as e:
            logger.warning(f"Failed to fetch Maven POM for {pkg.name}: {e}")
            return None

    def _parse_pom_licenses(self, pom_content: str) -> tuple[str, str | None] | None:
        """POMファイルからライセンス情報をパースする。

        Args:
            pom_content: POMファイルの内容

        Returns:
            (ライセンス名, ライセンスURL)のタプル、見つからない場合はNone
        """
        try:
            # 名前空間を除去
            pom_content = self._remove_namespace(pom_content)
            root = ElementTree.fromstring(pom_content)

            # licenses/licenseを探す
            licenses_elem = root.find("licenses")
            if licenses_elem is None:
                return None

            license_elem = licenses_elem.find("license")
            if license_elem is None:
                return None

            name_elem = license_elem.find("name")
            url_elem = license_elem.find("url")

            if name_elem is None or name_elem.text is None:
                return None

            return (name_elem.text, url_elem.text if url_elem is not None else None)

        except ElementTree.ParseError as e:
            logger.debug(f"Failed to parse POM: {e}")
            return None

    def _remove_namespace(self, xml_content: str) -> str:
        """XMLから名前空間宣言を除去する。

        Args:
            xml_content: XML文字列

        Returns:
            名前空間を除去したXML
        """
        import re

        # xmlns属性を除去
        xml_content = re.sub(r'\sxmlns[^"]*"[^"]*"', "", xml_content)
        return xml_content

    def _normalize_maven_license(self, license_name: str) -> str | None:
        """Mavenライセンス名をSPDX IDに正規化する。

        Args:
            license_name: Mavenのライセンス名

        Returns:
            SPDX ID、正規化できない場合はNone
        """
        # 一般的なMavenライセンス名のマッピング
        license_map = {
            "Apache License, Version 2.0": "Apache-2.0",
            "The Apache Software License, Version 2.0": "Apache-2.0",
            "Apache 2.0": "Apache-2.0",
            "Apache-2.0": "Apache-2.0",
            "MIT License": "MIT",
            "The MIT License": "MIT",
            "MIT": "MIT",
            "BSD License": "BSD-3-Clause",
            "BSD": "BSD-3-Clause",
            "BSD-3-Clause": "BSD-3-Clause",
            "Eclipse Public License 1.0": "EPL-1.0",
            "Eclipse Public License - v 1.0": "EPL-1.0",
            "GNU General Public License v3.0": "GPL-3.0",
            "GNU Lesser General Public License v3.0": "LGPL-3.0",
        }

        # 完全一致
        if license_name in license_map:
            return license_map[license_name]

        # 部分一致
        license_lower = license_name.lower()
        if "apache" in license_lower and "2" in license_lower:
            return "Apache-2.0"
        if "mit" in license_lower:
            return "MIT"
        if "bsd" in license_lower:
            return "BSD-3-Clause"
        if "gpl" in license_lower and "3" in license_lower:
            if "lesser" in license_lower or "lgpl" in license_lower:
                return "LGPL-3.0"
            return "GPL-3.0"

        return None
