"""apply_policy node: ポリシー設定を読み込み、各依存関係に適用"""

import logging
from pathlib import Path
from typing import Any

from oss_license_scan.models import DependencyWithPolicy
from oss_license_scan.workflow.messages import MessageTemplates
from oss_license_scan.workflow.state import LicenseScanState

logger = logging.getLogger(__name__)


def apply_policy_node(state: LicenseScanState) -> dict[str, Any]:
    """
    ポリシー設定を読み込み、各依存関係に適用する。

    Args:
        state: 現在のワークフロー状態

    Returns:
        dict: 更新する状態フィールド (policy_config, dependencies_with_policy, warnings)
    """
    logger.info(MessageTemplates.NODE_START.format(node_name="apply_policy"))

    dependencies_with_license = state.get("dependencies_with_license", [])
    policy_file = state.get("policy_file")

    # ポリシーファイルがない場合
    if not policy_file:
        logger.info(MessageTemplates.POLICY_SKIPPED.format())

        # policyなしでDependencyWithPolicyに変換
        dependencies_with_policy = [
            DependencyWithPolicy(
                name=dep.name,
                version=dep.version,
                ecosystem=dep.ecosystem,
                group_id=dep.group_id,
                artifact_id=dep.artifact_id,
                module_path=dep.module_path,
                license=dep.license,
                license_text_url=dep.license_text_url,
                homepage_url=dep.homepage_url,
                license_source=dep.license_source,
                agent_search=dep.agent_search,
                custom_classification=dep.custom_classification,
                policy=None,
            )
            for dep in dependencies_with_license
        ]

        return {"policy_config": None, "dependencies_with_policy": dependencies_with_policy}

    # ポリシーファイルがある場合
    try:
        from oss_license_scan.policy.checker import apply_policies
        from oss_license_scan.policy.loader import load_policy

        # ポリシーロード
        policy_config = load_policy(Path(policy_file))
        logger.info(MessageTemplates.POLICY_LOADED.format(policy_file=policy_file))

        # ポリシー適用
        dependencies_with_policy = apply_policies(dependencies_with_license, policy_config)

        # ポリシー違反（deny）をwarningsに記録
        warnings = []
        for dep in dependencies_with_policy:
            if dep.policy and dep.policy.status == "deny":
                warning = MessageTemplates.POLICY_VIOLATION.format(
                    package=dep.name, license=dep.license
                )
                warnings.append(warning)
                logger.warning(warning)

        return {
            "policy_config": policy_config,
            "dependencies_with_policy": dependencies_with_policy,
            "warnings": warnings,
        }

    except Exception as e:
        # JSONDecodeErrorやPolicyValidationError等はerrorsに記録
        # （これらは致命的なエラーで、実行を停止すべき）
        import json

        from oss_license_scan.api import PolicyValidationError

        if isinstance(e, (json.JSONDecodeError, PolicyValidationError, FileNotFoundError)):
            error_msg = f"Failed to load policy from {policy_file}: {str(e)}"
            logger.error(error_msg)
            return {"errors": [error_msg], "dependencies_with_policy": []}

        # その他のエラーはwarningsに記録（ベストエフォート）
        error_msg = f"Failed to load policy from {policy_file}: {str(e)}"
        logger.warning(error_msg)

        # ポリシーなしで継続
        dependencies_with_policy = [
            DependencyWithPolicy(
                name=dep.name,
                version=dep.version,
                ecosystem=dep.ecosystem,
                group_id=dep.group_id,
                artifact_id=dep.artifact_id,
                module_path=dep.module_path,
                license=dep.license,
                license_text_url=dep.license_text_url,
                homepage_url=dep.homepage_url,
                license_source=dep.license_source,
                agent_search=dep.agent_search,
                custom_classification=dep.custom_classification,
                policy=None,
            )
            for dep in dependencies_with_license
        ]

        return {
            "policy_config": None,
            "dependencies_with_policy": dependencies_with_policy,
            "warnings": [error_msg],
        }
