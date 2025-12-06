"""LangChain PromptTemplateを使用したログメッセージテンプレート定義"""

from langchain_core.prompts import PromptTemplate


class MessageTemplates:
    """ワークフローのログメッセージテンプレート"""

    # スキャン開始
    SCAN_START = PromptTemplate.from_template("ライセンススキャンを開始します: {input_file}")

    # ノード開始・完了
    NODE_START = PromptTemplate.from_template("Starting {node_name} node")
    NODE_COMPLETE = PromptTemplate.from_template("{node_name} node completed: {result_summary}")

    # parse_input
    PARSE_INPUT_SUCCESS = PromptTemplate.from_template("Parsed {count} dependencies")
    PARSE_INPUT_ERROR = PromptTemplate.from_template("Failed to parse input file: {error}")

    # resolve_licenses
    RESOLVE_LICENSES_SUCCESS = PromptTemplate.from_template("Resolved licenses: {resolved}/{total}")
    UNRESOLVED_LICENSE = PromptTemplate.from_template("Package {package} has unresolved license")

    # apply_policy
    POLICY_LOADED = PromptTemplate.from_template("Applied policy from {policy_file}")
    POLICY_SKIPPED = PromptTemplate.from_template("Policy check skipped (no policy file)")
    POLICY_VIOLATION = PromptTemplate.from_template(
        "ポリシー違反: {package} のライセンス {license} は禁止されています"
    )

    # generate_report
    REPORT_GENERATED = PromptTemplate.from_template("Generated report with {count} dependencies")

    # エラー
    WORKFLOW_ERROR = PromptTemplate.from_template("Workflow error at {node_name}: {error}")
