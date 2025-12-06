"""Adapter layer: 既存APIとLangGraphワークフローを接続"""

import logging
from pathlib import Path

from oss_license_scan.models import ScanReport
from oss_license_scan.workflow.graph import create_scan_workflow
from oss_license_scan.workflow.state import LicenseScanState

logger = logging.getLogger(__name__)


def scan_project_with_langgraph(
    input_file: str | Path,
    project_type: str | None = None,
    policy_file: str | Path | None = None,
    enable_llm: bool = True,
    enable_agent: bool = True,
    verbose: bool = False,
    explain_license: str | None = None,
    license_sources: list[str] | None = None,
    overrides_file: str | Path | None = None,
    mode: str = "fast",
) -> ScanReport:
    """
    LangGraphワークフロー版のscan_project。

    Args:
        input_file: 入力ファイルパス
        project_type: フォーマット指定（None時は自動検出）
        policy_file: ポリシーファイルパス（オプション）
        enable_llm: LLM統合を有効化（デフォルト: True）
        enable_agent: Agent機能を有効化（デフォルト: True）
        verbose: 詳細モード（全ライセンスの要約を生成）
        explain_license: 特定ライセンスの要約を生成（例: "MIT"）
        license_sources: カスタムソース順序リスト（例: ["pypi", "github"]）
        overrides_file: オーバーライド設定ファイルパス（オプション）
        mode: 解決モード（"fast" または "deep"）

    Returns:
        ScanReport: スキャン結果レポート

    Raises:
        RuntimeError: ワークフロー実行中にエラーが発生した場合
    """
    # ワークフロー作成
    workflow = create_scan_workflow()

    # AgentConfigを初期化（環境変数から読み込み、enable_agentで上書き）
    from oss_license_scan.agent.config import load_agent_config_from_env

    agent_config = load_agent_config_from_env()
    agent_config.enabled = enable_agent

    # 初期状態
    initial_state: LicenseScanState = {
        "input_file": str(input_file),
        "project_type": project_type,
        "policy_file": str(policy_file) if policy_file else None,
        "output_format": "json",
        "enable_llm": enable_llm,
        "agent_config": agent_config,
        "verbose": verbose,
        "explain_license": explain_license,
        "llm_inference_count": 0,
        "llm_cache_hits": 0,
        "llm_cache_misses": 0,
        "warnings": [],
        "errors": [],
        "mode": mode,  # type: ignore[typeddict-item]
    }

    # Add custom source order if specified
    if license_sources:
        initial_state["license_sources"] = license_sources

    # Add overrides file if specified
    if overrides_file:
        initial_state["overrides_file"] = str(overrides_file)

    # ワークフロー実行
    logger.debug(f"Starting LangGraph workflow for {input_file}")
    final_state = workflow.invoke(initial_state)

    # エラーチェック（T101: Agent/LLMエラーは継続、ポリシーエラーは例外）
    if final_state.get("errors"):
        errors = final_state["errors"]

        # 致命的エラー（ポリシー検証エラーなど）を検出
        fatal_errors = [
            err
            for err in errors
            if "Failed to load policy from" in err
            or "PolicyValidationError" in err
            or "JSONDecodeError" in err
        ]

        if fatal_errors:
            # 致命的エラーは例外として発生させる
            error_msg = "; ".join(fatal_errors)
            raise RuntimeError(f"Workflow failed: {error_msg}")

        # 非致命的エラー（Agent/LLMエラー）は警告に変換
        logger.warning(f"Workflow completed with non-fatal errors: {'; '.join(errors)}")
        if "warnings" not in final_state:
            final_state["warnings"] = []
        final_state["warnings"].extend(errors)

    # レポート取得
    report = final_state.get("report")
    if report is None:
        raise RuntimeError("Workflow completed but no report was generated")

    logger.debug("LangGraph workflow completed successfully")
    return report
