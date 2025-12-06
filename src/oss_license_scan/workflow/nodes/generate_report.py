"""generate_report node: 最終スキャンレポートを生成"""

import logging
from typing import Any

from oss_license_scan.models import DeepResult
from oss_license_scan.reporters.json_reporter import create_scan_report
from oss_license_scan.workflow.messages import MessageTemplates
from oss_license_scan.workflow.state import LicenseScanState

logger = logging.getLogger(__name__)


def _calculate_deep_source_stats(deep_results: dict[str, DeepResult]) -> dict[str, int]:
    """deepモードの各ソースからの取得結果件数を計算する。

    Args:
        deep_results: パッケージキー -> DeepResultのマップ

    Returns:
        ソース名 -> 取得成功件数のマップ
    """
    source_stats: dict[str, int] = {}

    for deep_result in deep_results.values():
        for result in deep_result.results:
            source_name = result.source_name
            if source_name not in source_stats:
                source_stats[source_name] = 0
            source_stats[source_name] += 1

    return source_stats


def generate_report_node(state: LicenseScanState) -> dict[str, Any]:
    """
    最終スキャンレポートを生成する。

    Args:
        state: 現在のワークフロー状態

    Returns:
        dict: 更新する状態フィールド (report)
    """
    logger.info(MessageTemplates.NODE_START.format(node_name="generate_report"))

    dependencies_with_policy = state.get("dependencies_with_policy", [])
    warnings = state.get("warnings", [])
    policy_config = state.get("policy_config")
    compatibility_checks = state.get("compatibility_checks", [])
    custom_classifications = state.get("custom_classifications", {})
    mode = state.get("mode", "fast")
    divergent_packages = state.get("divergent_packages", [])
    detected_format = state.get("detected_format", "unknown")
    deep_results = state.get("deep_results", {})

    # ポリシーが適用されたか判定
    # policy_configが存在すればTrue（依存関係が0件でもポリシーは適用された）
    if policy_config is not None:
        policy_applied = True
    else:
        # policy_configがNoneの場合は、依存関係にpolicyがあるか確認
        policy_applied = any(dep.policy is not None for dep in dependencies_with_policy)

    # deepモード時のソース統計を計算
    deep_source_stats: dict[str, int] = {}
    if mode == "deep" and deep_results:
        deep_source_stats = _calculate_deep_source_stats(deep_results)

    # レポート生成
    report = create_scan_report(
        project_type=detected_format,
        dependencies=dependencies_with_policy,
        policy_applied=policy_applied,
        warnings=warnings,
        compatibility_checks=compatibility_checks,
        custom_classifications=custom_classifications,
        mode=mode,
        divergent_count=len(divergent_packages),
        deep_source_stats=deep_source_stats,
    )

    logger.info(MessageTemplates.REPORT_GENERATED.format(count=report.summary.total_dependencies))

    return {"report": report}
