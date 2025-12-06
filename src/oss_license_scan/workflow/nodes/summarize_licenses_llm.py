"""summarize_licenses_with_llm node: LLMを使用してライセンステキストを要約"""

import logging
from typing import Any

from oss_license_scan.llm.cache import SQLiteCacheWithTTL
from oss_license_scan.llm.config import LLMConfig
from oss_license_scan.llm.prompts import LICENSE_SUMMARY_PROMPT
from oss_license_scan.llm.provider import create_llm
from oss_license_scan.models import DependencyWithLLM, LicenseSummary
from oss_license_scan.utils.retry import with_retry
from oss_license_scan.workflow.state import LicenseScanState

logger = logging.getLogger(__name__)


def _summarize_license(
    license_name: str, license_url: str | None, llm: Any, cache: SQLiteCacheWithTTL
) -> LicenseSummary:
    """
    単一ライセンスの要約を生成する。

    Args:
        license_name: ライセンス名
        license_url: ライセンステキストURL（オプション）
        llm: LLMインスタンス
        cache: キャッシュインスタンス

    Returns:
        LicenseSummary: 生成された要約

    Raises:
        TimeoutError: LLM APIタイムアウト
        Exception: その他のLLMエラー
    """
    # プロンプト生成
    prompt = LICENSE_SUMMARY_PROMPT.format_messages(
        license=license_name, license_url=license_url or "N/A"
    )

    # LLMにwith_structured_outputを適用
    structured_llm = llm.with_structured_output(LicenseSummary)

    # LLM呼び出し（リトライ付き）
    return with_retry(lambda: structured_llm.invoke(prompt), log=logger, context=license_name)


def summarize_licenses_with_llm_node(state: LicenseScanState) -> dict[str, Any]:
    """
    LLMを使用してライセンステキストを要約する。

    Args:
        state: 現在のワークフロー状態

    Returns:
        dict: 更新する状態フィールド
            - dependencies_with_policy: ライセンス要約を追加したリスト
            - warnings: 警告メッセージ
    """
    # LLM無効の場合はスキップ
    if not state.get("enable_llm", True):
        logger.info("License summary skipped (enable_llm=False)")
        return {}

    # verbose=FalseかつexplainLicense=Noneの場合はスキップ
    verbose = state.get("verbose", False)
    explain_license = state.get("explain_license")

    if not verbose and not explain_license:
        logger.info("License summary skipped (verbose=False and explain_license=None)")
        return {}

    dependencies_with_policy = state.get("dependencies_with_policy", [])

    if not dependencies_with_policy:
        logger.info("No dependencies found, skipping license summary")
        return {}

    # 要約対象のパッケージを決定
    if explain_license:
        # 特定ライセンスのみ
        packages_to_summarize = [
            dep for dep in dependencies_with_policy if dep.license == explain_license
        ]
        logger.info(f"Summarizing licenses for: {explain_license}")
    else:
        # verbose=True: 全パッケージ
        packages_to_summarize = dependencies_with_policy
        logger.info(
            f"Summarizing licenses for {len(packages_to_summarize)} packages (verbose mode)"
        )

    if not packages_to_summarize:
        logger.info("No packages to summarize")
        return {}

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

    # 各パッケージに対してLLM要約生成
    updated_deps = []

    for dep in dependencies_with_policy:
        # 要約対象でない場合はスキップ
        if dep not in packages_to_summarize:
            updated_deps.append(dep)
            continue

        # ライセンスがない場合はスキップ
        if not dep.license:
            updated_deps.append(dep)
            continue

        try:
            # LLM要約生成
            summary = _summarize_license(
                license_name=dep.license,
                license_url=dep.license_text_url,
                llm=llm,
                cache=cache,
            )

            # ライセンス要約を追加（DependencyWithLLMに変換）
            dep_dict = dep.model_dump()
            dep_dict["llm_summary"] = summary
            updated_dep = DependencyWithLLM(**dep_dict)
            updated_deps.append(updated_dep)

            logger.info(
                f"{dep.name}: License summary generated (license={dep.license}, points={len(summary.summary_points)})"
            )

        except TimeoutError as e:
            warning = f"{dep.name}: LLMタイムアウト（ライセンス要約）"
            warnings.append(warning)
            logger.warning(f"{warning}: {e}")
            # 要約なしで継続
            updated_deps.append(dep)
            continue

        except Exception as e:
            warning = f"{dep.name}: ライセンス要約生成失敗"
            warnings.append(warning)
            logger.error(f"{warning}: {e}")
            # 要約なしで継続
            updated_deps.append(dep)
            continue

    return {
        "dependencies_with_policy": updated_deps,
        "warnings": warnings,
    }
