"""Agent license search service.

This module extracts the business logic from agent_search_licenses node
into a reusable service class for better testability and separation of concerns.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from langchain_core.messages import AIMessage, ToolMessage

from oss_license_scan.agent.config import AgentConfig
from oss_license_scan.agent.react_agent import run_agent_with_tools
from oss_license_scan.agent.tools.github_search import github_search
from oss_license_scan.agent.tools.go_search import go_search
from oss_license_scan.agent.tools.npm_search import npm_search
from oss_license_scan.agent.tools.pypi_search import pypi_search
from oss_license_scan.agent.tools.rubygems_search import rubygems_search
from oss_license_scan.agent.tools.spdx_search import spdx_search
from oss_license_scan.license_utils import normalize_license_name
from oss_license_scan.models import DependencyWithLicense, Ecosystem

logger = logging.getLogger(__name__)

# AgentSearchResultと同じ型定義
SourceType = Literal["pypi", "npm", "rubygems", "go", "github", "spdx", "llm"]
VALID_SOURCES: set[str] = {"pypi", "npm", "rubygems", "go", "github", "spdx", "llm"}


def _validate_source(source: str) -> SourceType:
    """ソース文字列を検証してSourceType型に変換する。

    Args:
        source: 検証するソース文字列

    Returns:
        有効なSourceType値、無効な場合は"llm"にフォールバック
    """
    if source in VALID_SOURCES:
        return source  # type: ignore[return-value]
    return "llm"


@dataclass
class LicenseSearchResult:
    """ライセンス検索結果を表すデータクラス。

    Attributes:
        license_name: 検出されたライセンス名（SPDX ID）
        confidence: 信頼度スコア（0.0-1.0）
        source: 情報源（pypi, npm, rubygems, go, github, spdx, llm）
        reasoning: 検索過程の説明リスト
        homepage_url: プロジェクトホームページURL
        license_text_url: ライセンステキストURL
    """

    license_name: str | None = None
    confidence: float = 0.0
    source: SourceType = "llm"
    reasoning: list[str] = field(default_factory=list)
    homepage_url: str | None = None
    license_text_url: str | None = None


class AgentLicenseSearchService:
    """Agentを使用したライセンス検索サービス。

    パッケージのライセンス情報を複数のソースから検索する:
    1. 公式パッケージレジストリ（PyPI, npm, RubyGems, pkg.go.dev）
    2. GitHubリポジトリ
    3. LLM Agent（フォールバック）

    Example:
        >>> service = AgentLicenseSearchService(AgentConfig())
        >>> result = service.search_license(dep)
        >>> print(result.license_name)  # "MIT"
    """

    def __init__(self, agent_config: AgentConfig) -> None:
        """サービスを初期化する。

        Args:
            agent_config: Agent設定
        """
        self._agent_config = agent_config

    def search_license(self, dep: DependencyWithLicense) -> LicenseSearchResult:
        """パッケージのライセンスを検索する。

        検索優先順位:
        1. 公式パッケージレジストリ
        2. GitHubリポジトリ（homepage_urlがGitHubの場合）
        3. LLM Agent（フォールバック）

        Args:
            dep: 検索対象パッケージ

        Returns:
            LicenseSearchResult: 検索結果
        """
        result = LicenseSearchResult(
            homepage_url=dep.homepage_url,
            license_text_url=dep.license_text_url,
        )

        # 1. 公式レジストリを検索
        registry_result = self._search_official_registry(dep)
        if registry_result and registry_result.get("success"):
            self._process_registry_result(registry_result, result)
            if result.license_name:
                return result

        # 2. GitHubを検索（homepage_urlがGitHubの場合）
        if result.homepage_url and "github.com" in result.homepage_url.lower():
            self._search_github(result.homepage_url, result)
            if result.license_name:
                return result

        # 3. LLM Agentを使用（フォールバック）
        if self._agent_config.enabled:
            self._search_with_agent(dep, result)

        return result

    def _search_official_registry(self, dep: DependencyWithLicense) -> dict[str, Any] | None:
        """公式パッケージレジストリを検索する。

        Args:
            dep: 検索対象パッケージ

        Returns:
            検索結果の辞書、またはNone
        """
        ecosystem = dep.ecosystem

        if ecosystem == Ecosystem.PYTHON:
            return pypi_search(dep.name, dep.version)
        elif ecosystem == Ecosystem.NPM:
            return npm_search(dep.name, dep.version)
        elif ecosystem == Ecosystem.RUBY:
            return rubygems_search(dep.name, dep.version)
        elif ecosystem == Ecosystem.GO:
            module_path = dep.module_path or dep.name
            return go_search(module_path, dep.version)
        elif ecosystem == Ecosystem.MAVEN:
            # TODO: Maven Central検索を実装
            return None
        else:
            return None

    def _process_registry_result(
        self, registry_result: dict[str, Any], result: LicenseSearchResult
    ) -> None:
        """レジストリ検索結果を処理する。

        Args:
            registry_result: レジストリからの検索結果
            result: 更新するLicenseSearchResult
        """
        found_license = registry_result.get("license", "")
        source_str = registry_result.get("source", "pypi")

        if found_license and found_license.lower() != "unknown":
            result.license_name = normalize_license_name(found_license)
            result.confidence = 0.95
            result.source = _validate_source(source_str)
            result.reasoning.append(f"Found license '{found_license}' from {source_str} registry")
        else:
            result.reasoning.append(f"Official registry ({source_str}) returned 'Unknown' license")

        # URLを更新
        if registry_result.get("homepage_url"):
            result.homepage_url = registry_result["homepage_url"]
        if registry_result.get("license_text_url"):
            result.license_text_url = registry_result["license_text_url"]

    def _search_github(self, url: str, result: LicenseSearchResult) -> None:
        """GitHubリポジトリを検索する。

        Args:
            url: GitHubリポジトリURL
            result: 更新するLicenseSearchResult
        """
        result.reasoning.append(f"Trying GitHub search with URL: {url}")
        github_result = github_search(url)

        if github_result.get("success"):
            found_license = github_result.get("license", "")

            if github_result.get("homepage_url"):
                result.homepage_url = github_result["homepage_url"]
            if github_result.get("license_text_url"):
                result.license_text_url = github_result["license_text_url"]

            if found_license and found_license.lower() != "unknown":
                result.license_name = normalize_license_name(found_license)
                result.confidence = 0.90
                result.source = "github"
                result.reasoning.append(f"Found license '{found_license}' from GitHub")
            else:
                result.reasoning.append("GitHub returned 'Unknown' license")
        else:
            error = github_result.get("error", "Unknown error")
            result.reasoning.append(f"GitHub search failed: {error}")

    def _search_with_agent(self, dep: DependencyWithLicense, result: LicenseSearchResult) -> None:
        """LLM Agentを使用してライセンスを検索する。

        Args:
            dep: 検索対象パッケージ
            result: 更新するLicenseSearchResult
        """
        result.reasoning.append("Attempting Agent-based search as fallback")

        # エコシステムに応じたツールを選択
        tools = self._get_tools_for_ecosystem(dep.ecosystem)
        ecosystem_name = self._get_ecosystem_name(dep.ecosystem)

        query = (
            f"Search for the license of {ecosystem_name} package '{dep.name}' "
            f"version '{dep.version}'. Use the available tools to find accurate "
            "license information."
        )

        try:
            agent_result = run_agent_with_tools(
                query=query,
                tools=tools,  # type: ignore[arg-type]
                config=self._agent_config,
            )

            self._process_agent_result(agent_result, result)

        except Exception as e:
            logger.warning(f"Agent search failed for {dep.name}: {e}")

    def _get_tools_for_ecosystem(self, ecosystem: Ecosystem | None) -> list[Any]:
        """エコシステムに応じたツールリストを取得する。

        Args:
            ecosystem: パッケージエコシステム

        Returns:
            使用するツールのリスト
        """
        if ecosystem == Ecosystem.NPM:
            return [npm_search, github_search, spdx_search]
        elif ecosystem == Ecosystem.RUBY:
            return [rubygems_search, github_search, spdx_search]
        elif ecosystem == Ecosystem.GO:
            return [go_search, github_search, spdx_search]
        else:
            return [pypi_search, github_search, spdx_search]

    def _get_ecosystem_name(self, ecosystem: Ecosystem | None) -> str:
        """エコシステムの表示名を取得する。

        Args:
            ecosystem: パッケージエコシステム

        Returns:
            エコシステムの表示名
        """
        if ecosystem == Ecosystem.NPM:
            return "npm"
        elif ecosystem == Ecosystem.RUBY:
            return "Ruby"
        elif ecosystem == Ecosystem.GO:
            return "Go"
        else:
            return "Python"

    def _process_agent_result(
        self, agent_result: dict[str, Any], result: LicenseSearchResult
    ) -> None:
        """Agent検索結果を処理する。

        Args:
            agent_result: Agentからの検索結果
            result: 更新するLicenseSearchResult
        """
        messages = agent_result.get("messages", [])

        # ToolMessageからツール結果を抽出
        for msg in messages:
            if isinstance(msg, ToolMessage):
                try:
                    content = msg.content
                    if isinstance(content, str):
                        tool_result = json.loads(content)
                        if tool_result.get("success") and tool_result.get("license"):
                            found_license = tool_result["license"]
                            if found_license and found_license.lower() != "unknown":
                                result.license_name = normalize_license_name(found_license)
                                result.confidence = 0.95
                                source_str = tool_result.get("source", "llm")
                                result.source = _validate_source(source_str)
                                result.reasoning.append(
                                    f"Agent tool result: {source_str} returned '{found_license}'"
                                )
                                return
                except (json.JSONDecodeError, TypeError):
                    continue

        # AIMessageから抽出
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                content = msg.content
                if isinstance(content, str):
                    result.reasoning.append(content)
                    try:
                        parsed = json.loads(content)
                        if "license_name" in parsed:
                            result.license_name = normalize_license_name(parsed["license_name"])
                            result.confidence = parsed.get("confidence", 0.9)
                            result.source = _validate_source(parsed.get("source", "llm"))
                            return
                    except json.JSONDecodeError:
                        extracted = self._extract_license_from_text(content)
                        if extracted:
                            result.license_name = extracted
                            result.confidence = 0.7
                            return

    @staticmethod
    def _extract_license_from_text(text: str) -> str | None:
        """テキストから一般的なライセンス名を抽出する。

        Args:
            text: 解析するテキスト

        Returns:
            検出されたライセンス名、または見つからない場合はNone
        """
        # 一般的なライセンスパターン（優先順位順）
        license_patterns = [
            # SPDX形式
            (r"\bApache-2\.0\b", "Apache-2.0"),
            (r"\bMIT\b", "MIT"),
            (r"\bGPL-3\.0(?:-only|-or-later)?\b", "GPL-3.0"),
            (r"\bGPL-2\.0(?:-only|-or-later)?\b", "GPL-2.0"),
            (r"\bLGPL-3\.0(?:-only|-or-later)?\b", "LGPL-3.0"),
            (r"\bLGPL-2\.1(?:-only|-or-later)?\b", "LGPL-2.1"),
            (r"\bBSD-3-Clause\b", "BSD-3-Clause"),
            (r"\bBSD-2-Clause\b", "BSD-2-Clause"),
            (r"\bMPL-2\.0\b", "MPL-2.0"),
            (r"\bISC\b", "ISC"),
            (r"\bUnlicense\b", "Unlicense"),
            (r"\bCC0-1\.0\b", "CC0-1.0"),
            # フルネーム形式
            (r"Apache (?:Software )?License[,\s]+(?:Version\s+)?2\.0", "Apache-2.0"),
            (r"MIT License", "MIT"),
            (r"GNU General Public License[,\s]+(?:Version\s+|v)?3", "GPL-3.0"),
            (r"GNU General Public License[,\s]+(?:Version\s+|v)?2", "GPL-2.0"),
            (r"GPL version 2", "GPL-2.0"),
            (r"GPL version 3", "GPL-3.0"),
            (r"GPLv2", "GPL-2.0"),
            (r"GPLv3", "GPL-3.0"),
            (r"BSD 3-Clause", "BSD-3-Clause"),
            (r"BSD 2-Clause", "BSD-2-Clause"),
            (r"Mozilla Public License 2\.0", "MPL-2.0"),
            (r"Python Software Foundation License", "PSF-2.0"),
        ]

        for pattern, license_name in license_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return license_name

        return None
