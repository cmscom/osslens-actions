"""agent_search_licenses node: Agentを使用してライセンス不明パッケージを検索

このモジュールはLangGraphノード関数を提供し、ビジネスロジックは
AgentLicenseSearchServiceに委譲しています。

責務分割:
- agent_search_licenses_node: LangGraph状態の読み書き、ログ出力、結果マッピング
- AgentLicenseSearchService: ライセンス検索のビジネスロジック
"""

import logging
from typing import Any

from oss_license_scan.agent.config import AgentConfig
from oss_license_scan.models import AgentSearchResult, DependencyWithLicense
from oss_license_scan.workflow.messages import MessageTemplates
from oss_license_scan.workflow.services.agent_license_service import (
    AgentLicenseSearchService,
)
from oss_license_scan.workflow.state import LicenseScanState

logger = logging.getLogger(__name__)


def agent_search_licenses_node(state: LicenseScanState) -> dict[str, Any]:
    """
    Agentを使用してライセンス不明パッケージのライセンスを検索する。

    Args:
        state: 現在のワークフロー状態

    Returns:
        dict: 更新する状態フィールド
            - dependencies_with_license: 発見したライセンス情報を反映した依存関係リスト
            - agent_results: Agent検索結果リスト
            - warnings: 警告メッセージ
            - errors: エラーメッセージ
    """
    logger.info(MessageTemplates.NODE_START.format(node_name="agent_search_licenses"))

    # Agent機能が無効の場合はスキップ
    agent_config = state.get("agent_config", AgentConfig())
    if not agent_config.enabled:
        logger.info("Agent機能が無効化されています。スキップします。")
        return {"agent_results": []}

    dependencies_with_license = state.get("dependencies_with_license", [])
    mode = state.get("mode", "fast")

    if not dependencies_with_license:
        return {"agent_results": [], "dependencies_with_license": []}

    # Deepモードの場合は全パッケージを検証（複数の観点から確認）
    # Fastモードの場合はライセンス不明のパッケージのみ
    if mode == "deep":
        # Deepモード: 全パッケージを他の観点から検証
        packages_to_search = dependencies_with_license
        logger.info(
            f"[Deep mode] 全{len(packages_to_search)}件のパッケージを追加の観点から検証します。"
        )
    else:
        # Fastモード: ライセンス不明のパッケージのみ
        packages_to_search = [dep for dep in dependencies_with_license if dep.license is None]

        if not packages_to_search:
            logger.info("ライセンス不明のパッケージがありません。Agentをスキップします。")
            return {"agent_results": [], "dependencies_with_license": dependencies_with_license}

        logger.info(
            f"ライセンス不明のパッケージが{len(packages_to_search)}件見つかりました。検索します。"
        )

    agent_results = []
    warnings = []
    errors = []

    # パッケージ名から検索結果へのマッピング
    search_results_by_name: dict[str, AgentSearchResult] = {}

    # 各パッケージに対して検索を実行
    for dep in packages_to_search:
        try:
            logger.info(f"パッケージ '{dep.name}' ({dep.ecosystem}) のライセンスを検索中...")

            # エコシステムに応じた検索を実行
            search_result = _search_license_for_package(dep, agent_config)

            agent_results.append(search_result)
            search_results_by_name[dep.name] = search_result

            if search_result.license_name:
                # Deepモード: 既存のライセンスと比較して不整合を検出
                if mode == "deep" and dep.license and search_result.license_name:
                    if dep.license != search_result.license_name:
                        warning = (
                            f"[Deep mode] パッケージ '{dep.name}' でライセンス不整合を検出: "
                            f"既存='{dep.license}' ({dep.license_source}), "
                            f"Agent検索='{search_result.license_name}' ({search_result.source})"
                        )
                        warnings.append(warning)
                        logger.warning(warning)
                    else:
                        logger.info(
                            f"[Deep mode] パッケージ '{dep.name}' のライセンスを確認: {search_result.license_name} "
                            f"(既存ソースと一致、Agent source: {search_result.source})"
                        )
                else:
                    logger.info(
                        f"パッケージ '{dep.name}' のライセンスを発見: {search_result.license_name} "
                        f"(confidence: {search_result.confidence:.2f}, source: {search_result.source})"
                    )
            else:
                if mode == "deep" and dep.license:
                    # Deepモード: 既存のライセンスがあるがAgentで確認できなかった
                    logger.info(
                        f"[Deep mode] パッケージ '{dep.name}' のAgent検索結果なし "
                        f"(既存ライセンス: {dep.license})"
                    )
                else:
                    warning = f"パッケージ '{dep.name}' のライセンスを見つけられませんでした。"
                    warnings.append(warning)
                    logger.warning(warning)

        except Exception as e:
            error_msg = f"パッケージ '{dep.name}' の検索中にエラーが発生: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
            continue

    logger.info(f"検索完了: {len(agent_results)}件のパッケージを処理しました。")

    # dependencies_with_license を更新（発見したライセンス情報を反映）
    updated_deps = []
    for dep in dependencies_with_license:
        if dep.name in search_results_by_name:
            search_result = search_results_by_name[dep.name]

            # Deepモード: 既存のライセンスがある場合は上書きしない（不整合は警告で報告済み）
            # Fastモード: 新しく発見したライセンスで更新
            if mode == "deep" and dep.license:
                # Deepモード: 既存のライセンスを維持し、Agent検索結果は参照情報として追加
                updated_dep = DependencyWithLicense(
                    name=dep.name,
                    version=dep.version,
                    ecosystem=dep.ecosystem,
                    group_id=dep.group_id,
                    artifact_id=dep.artifact_id,
                    module_path=dep.module_path,
                    license=dep.license,  # 既存のライセンスを維持
                    license_text_url=dep.license_text_url or search_result.license_text_url,
                    homepage_url=dep.homepage_url or search_result.homepage_url,
                    license_source=dep.license_source,  # 既存のソースを維持
                    agent_search=search_result,  # Agent検索結果は参照として追加
                    custom_classification=dep.custom_classification,
                )
            else:
                # Fastモード: ライセンスが発見された場合は更新
                license_source = (
                    search_result.source if search_result.license_name else dep.license_source
                )
                homepage_url = search_result.homepage_url or dep.homepage_url
                license_text_url = search_result.license_text_url or dep.license_text_url
                updated_dep = DependencyWithLicense(
                    name=dep.name,
                    version=dep.version,
                    ecosystem=dep.ecosystem,
                    group_id=dep.group_id,
                    artifact_id=dep.artifact_id,
                    module_path=dep.module_path,
                    license=search_result.license_name
                    if search_result.license_name
                    else dep.license,
                    license_text_url=license_text_url,
                    homepage_url=homepage_url,
                    license_source=license_source,
                    agent_search=search_result,
                    custom_classification=dep.custom_classification,
                )
            updated_deps.append(updated_dep)
        else:
            updated_deps.append(dep)

    return {
        "dependencies_with_license": updated_deps,
        "agent_results": agent_results,
        "warnings": warnings,
        "errors": errors,
    }


def _search_license_for_package(
    dep: DependencyWithLicense, agent_config: AgentConfig
) -> AgentSearchResult:
    """エコシステムに応じた適切なパッケージレポジトリでライセンスを検索する。

    AgentLicenseSearchServiceに検索ロジックを委譲し、結果をAgentSearchResultに変換する。

    検索優先順位:
    1. 公式パッケージレポジトリ (PyPI, npm, RubyGems, pkg.go.dev)
    2. 公式レポジトリでライセンスが見つかった場合はGitHub検索をスキップ
    3. 公式レポジトリで見つからない場合のみGitHub検索（Rate Limit対策）
    4. 最終手段としてAgentを使用（オプション）

    Args:
        dep: 検索対象のパッケージ
        agent_config: Agent設定

    Returns:
        AgentSearchResult: 検索結果
    """
    # サービスを使用してライセンスを検索
    service = AgentLicenseSearchService(agent_config)
    result = service.search_license(dep)

    # LicenseSearchResultをAgentSearchResultに変換
    return AgentSearchResult(
        package_name=dep.name,
        version=dep.version or "unknown",
        license_name=result.license_name,
        confidence=result.confidence,
        source=result.source,
        homepage_url=result.homepage_url,
        license_text_url=result.license_text_url,
        reasoning=result.reasoning[:10],
        tool_calls=[],
    )
