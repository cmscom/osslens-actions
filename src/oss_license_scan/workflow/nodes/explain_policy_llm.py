"""explain_policy_with_llm node: LLMを使用してポリシー判断の根拠を説明"""

import logging
from typing import Any

from oss_license_scan.llm.cache import SQLiteCacheWithTTL
from oss_license_scan.llm.config import LLMConfig
from oss_license_scan.llm.prompts import POLICY_EXPLANATION_PROMPT
from oss_license_scan.llm.provider import create_llm
from oss_license_scan.models import DependencyWithLLM, PolicyExplanation
from oss_license_scan.utils.retry import with_retry
from oss_license_scan.workflow.state import LicenseScanState

logger = logging.getLogger(__name__)


def _explain_policy(
    license_name: str, status: str, policy_reason: str, llm: Any, cache: SQLiteCacheWithTTL
) -> PolicyExplanation:
    """
    単一ポリシー判断の説明を生成する。

    Args:
        license_name: ライセンス名
        status: ポリシーステータス (allow/deny/review)
        policy_reason: ポリシールールの理由
        llm: LLMインスタンス
        cache: キャッシュインスタンス

    Returns:
        PolicyExplanation: 生成された説明

    Raises:
        TimeoutError: LLM APIタイムアウト
        Exception: その他のLLMエラー
    """
    # プロンプト生成
    prompt = POLICY_EXPLANATION_PROMPT.format_messages(
        license=license_name, status=status, policy_reason=policy_reason
    )

    # LLMにwith_structured_outputを適用
    structured_llm = llm.with_structured_output(PolicyExplanation)

    # LLM呼び出し（リトライ付き）
    return with_retry(lambda: structured_llm.invoke(prompt), log=logger, context=license_name)


def explain_policy_with_llm_node(state: LicenseScanState) -> dict[str, Any]:
    """
    LLMを使用してポリシー判断の根拠を説明する。

    Args:
        state: 現在のワークフロー状態

    Returns:
        dict: 更新する状態フィールド
            - dependencies_with_policy: ポリシー説明を追加したリスト
            - warnings: 警告メッセージ
    """
    # LLM無効の場合はスキップ
    if not state.get("enable_llm", True):
        logger.info("Policy explanation skipped (enable_llm=False)")
        return {}

    dependencies_with_policy = state.get("dependencies_with_policy", [])

    # ポリシー判断があるパッケージを抽出
    packages_with_policy = [dep for dep in dependencies_with_policy if dep.policy is not None]

    if not packages_with_policy:
        logger.info("No policy decisions found, skipping policy explanation")
        return {}

    logger.info(f"Found {len(packages_with_policy)} packages with policy decisions")

    # LLM設定読み込み
    llm_config = LLMConfig.from_env()

    # LLMインスタンス作成
    try:
        llm = create_llm(
            provider=llm_config.provider,
            timeout=llm_config.timeout,
            with_fallback=llm_config.with_fallback,
        )
    except (OSError, ValueError) as e:
        logger.error(f"Failed to create LLM: {e}")
        return {"warnings": [f"LLM初期化失敗: {e}"]}

    # キャッシュ作成
    cache = SQLiteCacheWithTTL()

    # 警告リスト
    warnings = []

    # 各パッケージに対してLLM説明生成
    updated_deps = []

    for dep in dependencies_with_policy:
        # ポリシー判断がない場合はスキップ
        if dep.policy is None:
            updated_deps.append(dep)
            continue

        try:
            # LLM説明生成
            explanation = _explain_policy(
                license_name=dep.license or "Unknown",
                status=dep.policy.status,
                policy_reason=dep.policy.reason or "",
                llm=llm,
                cache=cache,
            )

            # ポリシー説明を追加（DependencyWithLLMに変換）
            dep_dict = dep.model_dump()
            dep_dict["llm_policy_explanation"] = explanation.explanation
            updated_dep = DependencyWithLLM(**dep_dict)
            updated_deps.append(updated_dep)

            logger.info(
                f"{dep.name}: Policy explanation generated (license={dep.license}, status={dep.policy.status})"
            )

        except TimeoutError as e:
            warning = f"{dep.name}: LLMタイムアウト（ポリシー説明）"
            warnings.append(warning)
            logger.warning(f"{warning}: {e}")
            # 説明なしで継続
            updated_deps.append(dep)
            continue

        except Exception as e:
            warning = f"{dep.name}: ポリシー説明生成失敗"
            warnings.append(warning)
            logger.error(f"{warning}: {e}")
            # 説明なしで継続
            updated_deps.append(dep)
            continue

    return {
        "dependencies_with_policy": updated_deps,
        "warnings": warnings,
    }
