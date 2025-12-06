"""Parser for pyproject.toml files (Poetry and PEP 621 formats)."""

import re
import tomllib
from typing import ClassVar

from oss_license_scan.models import Dependency, Ecosystem, LockFileFormat, ParseResult
from oss_license_scan.parsers.base import BaseLockFileParser, ParseError


class PyprojectTomlParser(BaseLockFileParser):
    """pyproject.toml パーサー (Poetry/PEP 621対応)"""

    FORMAT: ClassVar[LockFileFormat] = LockFileFormat.PYPROJECT_TOML
    ECOSYSTEM: ClassVar[Ecosystem] = Ecosystem.PYTHON
    FILENAME_PATTERNS: ClassVar[list[str]] = [r"^pyproject\.toml$"]

    def parse(self, content: str) -> ParseResult:
        """
        pyproject.tomlをパースする。

        Supports:
            - PEP 621 format: [project] dependencies = ["requests>=2.0"]
            - Poetry format: [tool.poetry.dependencies] requests = "^2.0"

        Args:
            content: ファイル内容

        Returns:
            ParseResult with Dependency list

        Raises:
            ParseError: パース失敗時
        """
        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError as e:
            raise ParseError(f"Invalid TOML: {e}") from e

        dependencies: list[Dependency] = []
        warnings: list[str] = []
        metadata: dict[str, object] = {}

        # Try PEP 621 format first
        pep621_deps = self._parse_pep621(data, warnings)
        dependencies.extend(pep621_deps)

        # Try Poetry format
        poetry_deps = self._parse_poetry(data, warnings)
        dependencies.extend(poetry_deps)

        # Extract project metadata
        if "project" in data:
            project = data["project"]
            if "name" in project:
                metadata["project_name"] = project["name"]
            if "version" in project:
                metadata["project_version"] = project["version"]
            if "requires-python" in project:
                metadata["requires-python"] = project["requires-python"]

        if "tool" in data and "poetry" in data["tool"]:
            poetry = data["tool"]["poetry"]
            if "name" in poetry:
                metadata["project_name"] = poetry["name"]
            if "version" in poetry:
                metadata["project_version"] = poetry["version"]

        if not dependencies:
            warnings.append(
                "No dependencies found in pyproject.toml. "
                "Supported formats: PEP 621 ([project] dependencies) "
                "and Poetry ([tool.poetry.dependencies])"
            )

        return ParseResult(
            format=self.FORMAT,
            ecosystem=self.ECOSYSTEM,
            dependencies=dependencies,
            warnings=warnings,
            metadata=metadata,
        )

    def _parse_pep621(self, data: dict[str, object], warnings: list[str]) -> list[Dependency]:
        """PEP 621形式の依存関係をパースする。

        Format:
            [project]
            dependencies = [
                "requests>=2.0",
                "click~=8.0",
            ]

        Args:
            data: TOMLデータ
            warnings: 警告リスト（追加される）

        Returns:
            依存関係リスト
        """
        dependencies: list[Dependency] = []

        project = data.get("project")
        if not isinstance(project, dict):
            return dependencies

        deps_list = project.get("dependencies")
        if not isinstance(deps_list, list):
            return dependencies

        for dep_str in deps_list:
            if not isinstance(dep_str, str):
                warnings.append(f"Invalid dependency entry: {dep_str}")
                continue

            dep = self._parse_requirement_string(dep_str, warnings)
            if dep:
                dependencies.append(dep)

        # Also parse optional dependencies
        optional_deps = project.get("optional-dependencies")
        if isinstance(optional_deps, dict):
            for _group_name, group_deps in optional_deps.items():
                if isinstance(group_deps, list):
                    for dep_str in group_deps:
                        if isinstance(dep_str, str):
                            dep = self._parse_requirement_string(dep_str, warnings)
                            if dep:
                                dependencies.append(dep)

        return dependencies

    def _parse_poetry(self, data: dict[str, object], warnings: list[str]) -> list[Dependency]:
        """Poetry形式の依存関係をパースする。

        Format:
            [tool.poetry.dependencies]
            python = "^3.9"
            requests = "^2.0"
            click = {version = "^8.0", optional = true}

        Args:
            data: TOMLデータ
            warnings: 警告リスト（追加される）

        Returns:
            依存関係リスト
        """
        dependencies: list[Dependency] = []

        tool = data.get("tool")
        if not isinstance(tool, dict):
            return dependencies

        poetry = tool.get("poetry")
        if not isinstance(poetry, dict):
            return dependencies

        # Parse main dependencies
        deps = poetry.get("dependencies")
        if isinstance(deps, dict):
            for name, version_spec in deps.items():
                # Skip python version constraint
                if name.lower() == "python":
                    continue

                dep = self._parse_poetry_dependency(name, version_spec, warnings)
                if dep:
                    dependencies.append(dep)

        # Parse dev dependencies
        dev_deps = poetry.get("dev-dependencies")
        if isinstance(dev_deps, dict):
            for name, version_spec in dev_deps.items():
                dep = self._parse_poetry_dependency(name, version_spec, warnings)
                if dep:
                    dependencies.append(dep)

        # Parse group dependencies (Poetry 1.2+)
        groups = poetry.get("group")
        if isinstance(groups, dict):
            for _group_name, group_data in groups.items():
                if isinstance(group_data, dict):
                    group_deps = group_data.get("dependencies")
                    if isinstance(group_deps, dict):
                        for name, version_spec in group_deps.items():
                            dep = self._parse_poetry_dependency(name, version_spec, warnings)
                            if dep:
                                dependencies.append(dep)

        return dependencies

    def _parse_requirement_string(self, req_str: str, warnings: list[str]) -> Dependency | None:
        """PEP 508形式の依存関係文字列をパースする。

        Examples:
            "requests>=2.0"
            "click~=8.0"
            "numpy==1.24.0"
            "pandas[excel]>=2.0"

        Args:
            req_str: 依存関係文字列
            warnings: 警告リスト

        Returns:
            Dependency or None
        """
        # Remove extras and environment markers
        req_str = req_str.strip()

        # Remove environment markers (e.g., ; python_version >= "3.8")
        if ";" in req_str:
            req_str = req_str.split(";")[0].strip()

        # Remove extras (e.g., [excel])
        req_str = re.sub(r"\[.*?\]", "", req_str)

        # Parse name and version specifier
        # Pattern: name followed by optional version specifier
        match = re.match(r"^([a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+)*)\s*(.*)?$", req_str)
        if not match:
            warnings.append(f"Could not parse dependency: {req_str}")
            return None

        name = match.group(1)
        version_spec = match.group(2).strip() if match.group(2) else None

        # Extract version from specifier
        version = None
        if version_spec:
            # For exact version (==), extract the version
            exact_match = re.match(r"==\s*([^\s,]+)", version_spec)
            if exact_match:
                version = exact_match.group(1)
            else:
                # Store the full specifier for non-exact versions
                version = version_spec

        return Dependency(
            name=name,
            version=version,
            ecosystem=Ecosystem.PYTHON,
        )

    def _parse_poetry_dependency(
        self, name: str, version_spec: object, warnings: list[str]
    ) -> Dependency | None:
        """Poetry形式の依存関係をパースする。

        Args:
            name: パッケージ名
            version_spec: バージョン指定（文字列またはdict）
            warnings: 警告リスト

        Returns:
            Dependency or None
        """
        version = None

        if isinstance(version_spec, str):
            # Simple string version: "^2.0" or ">=1.0,<2.0"
            version = self._normalize_poetry_version(version_spec)
        elif isinstance(version_spec, dict):
            # Complex specification: {version = "^2.0", optional = true}
            ver = version_spec.get("version")
            if isinstance(ver, str):
                version = self._normalize_poetry_version(ver)
            # Handle git/path dependencies
            if "git" in version_spec or "path" in version_spec:
                warnings.append(f"Git/path dependency '{name}' - version may not be accurate")
        else:
            warnings.append(f"Unknown version format for '{name}': {version_spec}")
            return None

        return Dependency(
            name=name,
            version=version,
            ecosystem=Ecosystem.PYTHON,
        )

    def _normalize_poetry_version(self, version: str) -> str:
        """Poetry形式のバージョン指定を正規化する。

        Poetry uses caret (^) and tilde (~) version constraints.
        We keep them as-is since they represent version ranges.

        Args:
            version: Poetryバージョン文字列

        Returns:
            正規化されたバージョン文字列
        """
        return version.strip()
