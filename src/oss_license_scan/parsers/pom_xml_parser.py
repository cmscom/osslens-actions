"""Parser for pom.xml files."""

from typing import ClassVar
from xml.etree import ElementTree

from oss_license_scan.models import Dependency, Ecosystem, LockFileFormat, ParseResult
from oss_license_scan.parsers.base import BaseLockFileParser, ParseError


class PomXmlParser(BaseLockFileParser):
    """pom.xml パーサー"""

    FORMAT: ClassVar[LockFileFormat] = LockFileFormat.POM_XML
    ECOSYSTEM: ClassVar[Ecosystem] = Ecosystem.MAVEN
    FILENAME_PATTERNS: ClassVar[list[str]] = [r"^pom\.xml$"]

    # Maven POM namespace
    MAVEN_NS = {"m": "http://maven.apache.org/POM/4.0.0"}

    def parse(self, content: str) -> ParseResult:
        """
        pom.xmlをパースする。

        Extracts <dependencies> section.

        Args:
            content: ファイル内容

        Returns:
            ParseResult with Dependency list (includes groupId, artifactId)

        Raises:
            ParseError: パース失敗時
        """
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError as e:
            raise ParseError(f"Invalid XML: {e}") from e

        dependencies: list[Dependency] = []
        warnings: list[str] = []

        # Try to find namespace
        ns = self._detect_namespace(root)

        # Find dependencies element
        deps_elem = (
            root.find(f"{ns}dependencies", self.MAVEN_NS) if ns else root.find("dependencies")
        )
        if deps_elem is None:
            # Try without namespace
            deps_elem = root.find("dependencies")

        if deps_elem is None:
            return ParseResult(
                format=self.FORMAT,
                ecosystem=self.ECOSYSTEM,
                dependencies=[],
                warnings=["No <dependencies> section found"],
            )

        # Parse each dependency
        for dep_elem in deps_elem.findall(f"{ns}dependency" if ns else "dependency", self.MAVEN_NS):
            group_id = self._get_text(dep_elem, "groupId", ns)
            artifact_id = self._get_text(dep_elem, "artifactId", ns)
            version = self._get_text(dep_elem, "version", ns)

            if not group_id or not artifact_id:
                warnings.append("Dependency missing groupId or artifactId")
                continue

            # Create name in format groupId:artifactId
            name = f"{group_id}:{artifact_id}"

            dependencies.append(
                Dependency(
                    name=name,
                    version=version,
                    ecosystem=Ecosystem.MAVEN,
                    group_id=group_id,
                    artifact_id=artifact_id,
                )
            )

        return ParseResult(
            format=self.FORMAT,
            ecosystem=self.ECOSYSTEM,
            dependencies=dependencies,
            warnings=warnings,
        )

    def _detect_namespace(self, root: ElementTree.Element) -> str:
        """Detect if the XML uses Maven namespace."""
        tag = root.tag
        if tag.startswith("{"):
            # Has namespace
            return "m:"
        return ""

    def _get_text(self, parent: ElementTree.Element, tag: str, ns: str) -> str | None:
        """Get text content of a child element."""
        elem = parent.find(f"{ns}{tag}", self.MAVEN_NS) if ns else parent.find(tag)
        if elem is None:
            # Try without namespace
            elem = parent.find(tag)
        return elem.text.strip() if elem is not None and elem.text else None
