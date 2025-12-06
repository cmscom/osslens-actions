"""LangGraphワークフロー定義"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from oss_license_scan.workflow.nodes.agent_check_compatibility import (
    agent_check_compatibility_node,
)
from oss_license_scan.workflow.nodes.agent_classify_custom import (
    agent_classify_custom_node,
)
from oss_license_scan.workflow.nodes.agent_search_licenses import (
    agent_search_licenses_node,
)
from oss_license_scan.workflow.nodes.analyze_divergence import (
    analyze_divergence_node,
)
from oss_license_scan.workflow.nodes.apply_policy import apply_policy_node
from oss_license_scan.workflow.nodes.explain_policy_llm import (
    explain_policy_with_llm_node,
)
from oss_license_scan.workflow.nodes.generate_report import generate_report_node
from oss_license_scan.workflow.nodes.infer_licenses_llm import (
    infer_licenses_with_llm_node,
)
from oss_license_scan.workflow.nodes.parse_input import parse_input_node
from oss_license_scan.workflow.nodes.resolve_licenses import resolve_licenses_node
from oss_license_scan.workflow.nodes.summarize_licenses_llm import (
    summarize_licenses_with_llm_node,
)
from oss_license_scan.workflow.state import LicenseScanState


def should_use_agent(state: LicenseScanState) -> str:
    """
    Agent機能を使用すべきかを判定する条件分岐関数。

    Args:
        state: 現在のワークフロー状態

    Returns:
        str: 次のノード名 ("agent_search_licenses" or "infer_licenses_with_llm")
    """
    agent_config = state.get("agent_config")

    # Agent設定が存在し、有効化されている場合はAgentノードを使用
    if agent_config and agent_config.enabled:
        return "agent_search_licenses"

    # それ以外はLLM推測ノードを使用
    return "infer_licenses_with_llm"


def should_use_deep_mode(state: LicenseScanState) -> str:
    """
    deepモードの不整合分析を実行すべきかを判定する条件分岐関数。

    Args:
        state: 現在のワークフロー状態

    Returns:
        str: 次のノード名 ("analyze_divergence" or "apply_policy")
    """
    mode = state.get("mode", "fast")

    if mode == "deep":
        return "analyze_divergence"

    return "apply_policy"


def create_scan_workflow() -> Any:
    """
    ライセンススキャンワークフローを作成する。

    Returns:
        StateGraph: コンパイル済みワークフロー

    Workflow Structure:
        START → parse_input → resolve_licenses
        → [条件分岐: Agent有効?]
            YES → agent_search_licenses → apply_policy
            NO  → infer_licenses_with_llm → apply_policy
        → apply_policy → agent_classify_custom
        → agent_check_compatibility
        → summarize_licenses_with_llm
        → explain_policy_with_llm → generate_report → END
    """
    # StateGraphを作成
    builder = StateGraph(LicenseScanState)

    # ノード追加
    builder.add_node("parse_input", parse_input_node)
    builder.add_node("resolve_licenses", resolve_licenses_node)
    builder.add_node("analyze_divergence", analyze_divergence_node)  # 🆕 deepモード不整合分析
    builder.add_node("agent_search_licenses", agent_search_licenses_node)  # 🆕 Agent機能
    builder.add_node("infer_licenses_with_llm", infer_licenses_with_llm_node)
    builder.add_node("apply_policy", apply_policy_node)
    builder.add_node(
        "agent_classify_custom", agent_classify_custom_node
    )  # 🆕 カスタムライセンス分類
    builder.add_node(
        "agent_check_compatibility", agent_check_compatibility_node
    )  # 🆕 互換性チェック
    builder.add_node("summarize_licenses_with_llm", summarize_licenses_with_llm_node)
    builder.add_node("explain_policy_with_llm", explain_policy_with_llm_node)
    builder.add_node("generate_report", generate_report_node)

    # エッジ定義
    builder.add_edge(START, "parse_input")
    builder.add_edge("parse_input", "resolve_licenses")

    # resolve_licenses → analyze_divergence（常に経由、fastモードでは何もしない）
    builder.add_edge("resolve_licenses", "analyze_divergence")

    # analyze_divergenceからagent分岐へ
    builder.add_conditional_edges(
        "analyze_divergence",
        should_use_agent,
        {
            "agent_search_licenses": "agent_search_licenses",
            "infer_licenses_with_llm": "infer_licenses_with_llm",
        },
    )

    # 両方のパスからapply_policyに繋がる
    builder.add_edge("agent_search_licenses", "apply_policy")
    builder.add_edge("infer_licenses_with_llm", "apply_policy")

    # apply_policyからカスタムライセンス分類へ
    builder.add_edge("apply_policy", "agent_classify_custom")

    # カスタムライセンス分類から互換性チェックへ
    builder.add_edge("agent_classify_custom", "agent_check_compatibility")

    # 残りのフローは従来通り
    builder.add_edge("agent_check_compatibility", "summarize_licenses_with_llm")
    builder.add_edge("summarize_licenses_with_llm", "explain_policy_with_llm")
    builder.add_edge("explain_policy_with_llm", "generate_report")
    builder.add_edge("generate_report", END)

    # コンパイル
    return builder.compile()
