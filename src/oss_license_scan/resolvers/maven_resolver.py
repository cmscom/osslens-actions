"""Maven Central license resolver."""

import logging
from typing import Any, ClassVar

import httpx

from oss_license_scan.models import Dependency, Ecosystem, LicenseInfo
from oss_license_scan.resolvers.base import BaseLicenseResolver

logger = logging.getLogger(__name__)


class MavenLicenseResolver(BaseLicenseResolver):
    """Maven Central からライセンス情報を取得するリゾルバ"""

    ECOSYSTEM: ClassVar[Ecosystem] = Ecosystem.MAVEN
    SEARCH_URL: ClassVar[str] = "https://search.maven.org/solrsearch/select"
    REPO_URL: ClassVar[str] = "https://repo1.maven.org/maven2"
    TIMEOUT: ClassVar[float] = 10.0

    def resolve(self, dependency: Dependency) -> LicenseInfo:
        """
        Maven Central からアーティファクトのライセンス情報を取得する。

        Args:
            dependency: 依存パッケージ情報

        Returns:
            LicenseInfo: ライセンス情報
        """
        group_id = dependency.group_id
        artifact_id = dependency.name
        version = dependency.version or "latest"

        # If group_id is not provided, try to parse from name
        if not group_id:
            parsed_group, parsed_artifact = self._parse_maven_coordinate(dependency.name)
            if parsed_group:
                group_id = parsed_group
                artifact_id = parsed_artifact

        if not group_id:
            # Cannot resolve without group_id
            return LicenseInfo(license=None, license_text_url=None, homepage_url=None)

        artifact_info = self._fetch_artifact_info(group_id, artifact_id, version)

        if artifact_info is None:
            return LicenseInfo(license=None, license_text_url=None, homepage_url=None)

        license_name = self._extract_license(artifact_info)
        homepage_url = artifact_info.get("url")
        license_text_url = self._get_maven_url(group_id, artifact_id, version)

        return LicenseInfo(
            license=license_name,
            license_text_url=license_text_url,
            homepage_url=homepage_url,
        )

    def _fetch_artifact_info(
        self, group_id: str, artifact_id: str, version: str
    ) -> dict[str, Any] | None:
        """
        Maven Central Search API からアーティファクト情報を取得する。

        Args:
            group_id: グループID
            artifact_id: アーティファクトID
            version: バージョン

        Returns:
            アーティファクト情報の辞書、取得できない場合はNone
        """
        # Search for the artifact
        query = f'g:"{group_id}" AND a:"{artifact_id}" AND v:"{version}"'
        params = {
            "q": query,
            "rows": 1,
            "wt": "json",
        }

        try:
            with httpx.Client(timeout=self.TIMEOUT) as client:
                response = client.get(self.SEARCH_URL, params=params)
                if response.status_code == 200:
                    data = response.json()
                    docs = data.get("response", {}).get("docs", [])
                    if docs:
                        # Get POM for license info
                        pom_info = self._fetch_pom_info(group_id, artifact_id, version, client)
                        if pom_info:
                            return pom_info
                        # Return basic info from search
                        return docs[0]
                return None
        except httpx.RequestError as e:
            logger.warning(f"Failed to fetch Maven artifact info for {group_id}:{artifact_id}: {e}")
            return None

    def _fetch_pom_info(
        self,
        group_id: str,
        artifact_id: str,
        version: str,
        client: httpx.Client,
    ) -> dict[str, Any] | None:
        """
        POM ファイルからライセンス情報を取得する。

        Args:
            group_id: グループID
            artifact_id: アーティファクトID
            version: バージョン
            client: httpx クライアント

        Returns:
            ライセンス情報の辞書
        """
        # Construct POM URL
        group_path = group_id.replace(".", "/")
        pom_url = (
            f"{self.REPO_URL}/{group_path}/{artifact_id}/{version}/{artifact_id}-{version}.pom"
        )

        try:
            response = client.get(pom_url)
            if response.status_code == 200:
                return self._parse_pom_xml(response.text)
            return None
        except httpx.RequestError:
            return None

    def _parse_pom_xml(self, pom_content: str) -> dict[str, Any]:
        """
        POM XML からライセンス情報を抽出する。

        Args:
            pom_content: POM XMLの内容

        Returns:
            ライセンス情報の辞書
        """
        import xml.etree.ElementTree as ET

        result: dict[str, Any] = {}

        try:
            # Remove namespace for easier parsing
            pom_content = pom_content.replace('xmlns="http://maven.apache.org/POM/4.0.0"', "")
            root = ET.fromstring(pom_content)

            # Extract licenses
            licenses_elem = root.find(".//licenses")
            if licenses_elem is not None:
                licenses = []
                for license_elem in licenses_elem.findall("license"):
                    name_elem = license_elem.find("name")
                    if name_elem is not None and name_elem.text:
                        licenses.append(self._normalize_license_name(name_elem.text))
                if licenses:
                    result["licenses"] = licenses
                    result["license"] = licenses[0] if len(licenses) == 1 else " OR ".join(licenses)

            # Extract URL
            url_elem = root.find("url")
            if url_elem is not None and url_elem.text:
                result["url"] = url_elem.text

        except ET.ParseError as e:
            logger.debug(f"Failed to parse POM XML: {e}")

        return result

    def _normalize_license_name(self, name: str) -> str:
        """
        ライセンス名をSPDX識別子に正規化する。

        Args:
            name: 元のライセンス名

        Returns:
            正規化されたライセンス名
        """
        name_lower = name.lower()

        # Common mappings
        if "apache" in name_lower and "2" in name_lower:
            return "Apache-2.0"
        if "mit" in name_lower:
            return "MIT"
        if "bsd" in name_lower:
            if "3" in name_lower:
                return "BSD-3-Clause"
            if "2" in name_lower:
                return "BSD-2-Clause"
            return "BSD-3-Clause"
        if "lgpl" in name_lower:
            if "3" in name_lower:
                return "LGPL-3.0-only"
            if "2.1" in name_lower:
                return "LGPL-2.1-only"
            return "LGPL-3.0-only"
        if "gpl" in name_lower:
            if "3" in name_lower:
                return "GPL-3.0-only"
            if "2" in name_lower:
                return "GPL-2.0-only"
        if "eclipse" in name_lower or "epl" in name_lower:
            if "2" in name_lower:
                return "EPL-2.0"
            return "EPL-1.0"
        if "mozilla" in name_lower or "mpl" in name_lower:
            return "MPL-2.0"
        if "cddl" in name_lower:
            return "CDDL-1.0"

        return name

    def _extract_license(self, artifact_info: dict[str, Any]) -> str | None:
        """
        アーティファクト情報からライセンス名を抽出する。

        Args:
            artifact_info: アーティファクト情報

        Returns:
            ライセンス名、見つからない場合はNone
        """
        # Check direct license field
        if "license" in artifact_info:
            license_field = artifact_info["license"]
            if isinstance(license_field, str):
                return license_field
            elif isinstance(license_field, dict):
                return license_field.get("name")

        # Check licenses array
        if "licenses" in artifact_info:
            licenses = artifact_info["licenses"]
            if isinstance(licenses, list) and len(licenses) > 0:
                if len(licenses) == 1:
                    return licenses[0]
                return " OR ".join(licenses)

        return None

    def _get_maven_url(self, group_id: str, artifact_id: str, version: str) -> str:
        """
        MVN Repository URLを生成する。

        Args:
            group_id: グループID
            artifact_id: アーティファクトID
            version: バージョン

        Returns:
            MVN Repository URL
        """
        return f"https://mvnrepository.com/artifact/{group_id}/{artifact_id}/{version}"

    def _parse_maven_coordinate(self, name: str) -> tuple[str | None, str]:
        """
        Maven座標形式からgroup_idとartifact_idを抽出する。

        Args:
            name: アーティファクト名（group:artifact形式の可能性あり）

        Returns:
            (group_id, artifact_id) のタプル
        """
        if ":" in name:
            parts = name.split(":")
            if len(parts) >= 2:
                return parts[0], parts[1]
        return None, name
