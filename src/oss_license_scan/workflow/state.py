"""LangGraphワークフローの状態管理用TypedDict定義"""

from operator import add
from typing import Annotated, Literal

from typing_extensions import TypedDict

from oss_license_scan.agent.config import AgentConfig
from oss_license_scan.models import (
    AgentSearchResult,
    CustomLicenseClassification,
    DeepResult,
    Dependency,
    DependencyWithLicense,
    DependencyWithPolicy,
    LicenseCompatibility,
    LicenseResult,
    PolicyConfig,
    ScanReport,
)


class LicenseScanState(TypedDict, total=False):
    """
    LangGraphワークフローの状態管理用TypedDict。

    total=False により全フィールドがオプショナル。
    各ノードは必要なフィールドのみを読み書きする。
    """

    # === 入力情報 ===
    input_file: str
    """スキャン対象ファイルパス（requirements.txt / pyproject.toml）"""

    project_type: str | None
    """明示的なファイル形式指定（None時は自動検出）"""

    policy_file: str | None
    """ポリシー設定ファイルパス（オプション）"""

    output_format: str
    """出力フォーマット（json / markdown）"""

    # === parse_inputノードの出力 ===
    dependencies: list[Dependency]
    """解析された依存パッケージリスト"""

    detected_format: str
    """検出されたファイル形式（例: "pylock_toml", "gradle_lockfile"）"""

    # === resolve_licensesノードの出力 ===
    dependencies_with_license: list[DependencyWithLicense]
    """ライセンス情報付き依存パッケージリスト"""

    # === apply_policyノードの入力・出力 ===
    policy_config: PolicyConfig | None
    """ロードされたポリシー設定"""

    dependencies_with_policy: list[DependencyWithPolicy]
    """ポリシー判定付き依存パッケージリスト"""

    # === 警告・エラーの蓄積（全ノードで追加可能） ===
    warnings: Annotated[list[str], add]
    """ワークフロー全体で蓄積される警告メッセージ"""

    errors: Annotated[list[str], add]
    """ワークフロー全体で蓄積されるエラーメッセージ"""

    # === generate_reportノードの出力 ===
    report: ScanReport | None
    """最終的なスキャンレポート"""

    # === LLM統合用フィールド ===
    enable_llm: bool
    """LLM統合の有効化フラグ（デフォルト: True、--no-llmでFalse）"""

    llm_inference_count: int
    """LLM推測実行回数"""

    llm_cache_hits: int
    """キャッシュヒット数"""

    llm_cache_misses: int
    """キャッシュミス数"""

    verbose: bool
    """詳細レポートモード（--verbose）"""

    explain_license: str | None
    """説明対象のライセンス名（--explain-license MIT）"""

    # === Agent統合用フィールド ===
    agent_config: AgentConfig
    """Agent設定"""

    agent_results: Annotated[list[AgentSearchResult], add]
    """Agent検索結果リスト（全ノードで追加可能）"""

    compatibility_checks: Annotated[list[LicenseCompatibility], add]
    """ライセンス互換性チェック結果（全ノードで追加可能）"""

    custom_classifications: dict[str, CustomLicenseClassification]
    """カスタムライセンス分類結果（license_name -> 分類）"""

    # === Multi-Source License Resolution (011-multi-source-license) ===
    mode: Literal["fast", "deep"]
    """実行モード: fast（最初のソースで確定）/ deep（全ソース照合）デフォルト: fast"""

    license_sources: list[str]
    """使用するソース名リスト（優先順）"""

    fast_results: dict[str, LicenseResult]
    """fastモード結果（package.key -> LicenseResult）"""

    deep_results: dict[str, DeepResult]
    """deepモード結果（package.key -> DeepResult）"""

    divergent_packages: list[str]
    """不整合があったパッケージキーのリスト"""

    overrides_file: str | None
    """オーバーライド設定ファイルパス（license_overrides.yml）"""
