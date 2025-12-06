"""infer_licenses_with_llm node: LLMを使用してライセンス不明パッケージを推測"""

import json
import logging
from typing import Any

from oss_license_scan.llm.cache import SQLiteCacheWithTTL
from oss_license_scan.llm.config import LLMConfig
from oss_license_scan.llm.prompts import LICENSE_INFERENCE_PROMPT
from oss_license_scan.llm.provider import create_llm
from oss_license_scan.models import DependencyWithLicense, LicenseInference
from oss_license_scan.utils.retry import with_retry
from oss_license_scan.workflow.state import LicenseScanState

logger = logging.getLogger(__name__)


def _infer_license(
    package_name: str,
    version: str | None,
    llm: Any,
    cache: SQLiteCacheWithTTL,
    model_name: str = "gpt-4o",
) -> tuple[LicenseInference, bool]:
    """
    単一パッケージのライセンスを推測する。

    Args:
        package_name: パッケージ名
        version: バージョン
        llm: LLMインスタンス
        cache: キャッシュインスタンス
        model_name: LLMモデル名（キャッシュキー用）

    Returns:
        tuple: (LicenseInference, cache_hit)

    Raises:
        TimeoutError: LLM APIタイムアウト
        Exception: その他のLLMエラー
    """
    # プロンプト生成
    prompt = LICENSE_INFERENCE_PROMPT.format_messages(
        package_name=package_name, version=version or "unknown"
    )

    # キャッシュキーを生成（プロンプト文字列 + モデル名）
    prompt_str = str(prompt)
    llm_string = f"license_inference:{model_name}"

    # キャッシュを確認
    cached_result = cache.lookup(prompt_str, llm_string)
    if cached_result:
        try:
            cached_data = json.loads(cached_result[0].text)
            inference = LicenseInference(**cached_data)
            logger.debug(f"Cache hit for {package_name}")
            return inference, True
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.warning(f"Failed to parse cached result for {package_name}: {e}")
            # キャッシュが壊れている場合は続行してLLMを呼び出す

    # LLMにwith_structured_outputを適用
    structured_llm = llm.with_structured_output(LicenseInference)

    # LLM呼び出し（リトライ付き）
    result = with_retry(lambda: structured_llm.invoke(prompt), log=logger, context=package_name)

    # 結果をキャッシュに保存
    try:
        from langchain_core.outputs import Generation

        result_json = result.model_dump_json()
        cache.update(prompt_str, llm_string, [Generation(text=result_json)])
        logger.debug(f"Cached result for {package_name}")
    except Exception as e:
        logger.warning(f"Failed to cache result for {package_name}: {e}")

    return result, False


def infer_licenses_with_llm_node(state: LicenseScanState) -> dict[str, Any]:
    """
    LLMを使用してライセンス不明パッケージを推測する。

    Args:
        state: 現在のワークフロー状態

    Returns:
        dict: 更新する状態フィールド
            - dependencies_with_license: 推測結果を反映したリスト
            - llm_inference_count: 推測実行回数
            - llm_cache_hits: キャッシュヒット数
            - llm_cache_misses: キャッシュミス数
            - warnings: 警告メッセージ
    """
    # LLM無効の場合はスキップ
    if not state.get("enable_llm", True):
        logger.info("LLM inference skipped (enable_llm=False)")
        return {}

    dependencies_with_license = state.get("dependencies_with_license", [])

    # ライセンス不明パッケージを抽出
    unknown_packages = [dep for dep in dependencies_with_license if dep.license is None]

    if not unknown_packages:
        logger.info("No unknown licenses found, skipping LLM inference")
        return {}

    logger.info(f"Found {len(unknown_packages)} packages with unknown licenses")

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
        return {
            "dependencies_with_license": dependencies_with_license,
            "warnings": [f"LLM初期化失敗: {e}"],
        }

    # キャッシュ作成
    cache = SQLiteCacheWithTTL()

    # 統計情報
    inference_count = state.get("llm_inference_count", 0)
    cache_hits = state.get("llm_cache_hits", 0)
    cache_misses = state.get("llm_cache_misses", 0)
    warnings = []

    # 各パッケージに対してLLM推測実行
    updated_deps = list(dependencies_with_license)

    for i, dep in enumerate(updated_deps):
        if dep.license is not None:
            continue

        # MAX_LLM_CALLS チェック
        if llm_config.max_llm_calls is not None:
            if inference_count >= llm_config.max_llm_calls:
                warning = f"MAX_LLM_CALLS ({llm_config.max_llm_calls}) に到達しました。残りのパッケージはスキップします。"
                warnings.append(warning)
                logger.warning(warning)
                break

        try:
            # LLM推測実行
            inference, cache_hit = _infer_license(
                dep.name, dep.version, llm, cache, llm_config.model_name
            )

            # 統計更新
            inference_count += 1
            if cache_hit:
                cache_hits += 1
            else:
                cache_misses += 1

            # 信頼度チェック
            if inference.confidence < llm_config.min_confidence:
                warning = f"{dep.name}: 信頼度不足 ({inference.confidence:.2f} < {llm_config.min_confidence})"
                warnings.append(warning)
                logger.debug(warning)
                continue

            # ライセンス情報更新
            updated_deps[i] = DependencyWithLicense(
                name=dep.name,
                version=dep.version,
                ecosystem=dep.ecosystem,
                group_id=dep.group_id,
                artifact_id=dep.artifact_id,
                module_path=dep.module_path,
                license=inference.license,
                license_text_url=dep.license_text_url,
                homepage_url=dep.homepage_url,
                license_source="llm",
                agent_search=dep.agent_search,
                custom_classification=dep.custom_classification,
            )

            logger.info(
                f"{dep.name}: Inferred license={inference.license} (confidence={inference.confidence:.2f})"
            )

        except TimeoutError as e:
            warning = f"{dep.name}: LLMタイムアウト"
            warnings.append(warning)
            logger.warning(f"{warning}: {e}")
            continue

        except Exception as e:
            warning = f"{dep.name}: LLM推測失敗"
            warnings.append(warning)
            logger.error(f"{warning}: {e}")
            continue

    return {
        "dependencies_with_license": updated_deps,
        "llm_inference_count": inference_count,
        "llm_cache_hits": cache_hits,
        "llm_cache_misses": cache_misses,
        "warnings": warnings,
    }
