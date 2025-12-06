"""Data models for OSS license scanning."""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass


class LockFileFormat(str, Enum):
    """サポートされるロックファイル形式"""

    # Python
    REQUIREMENTS_TXT = "requirements_txt"
    PYPROJECT_TOML = "pyproject_toml"
    PYLOCK_TOML = "pylock_toml"

    # Node.js
    PACKAGE_LOCK_JSON = "package_lock_json"

    # Go
    GO_SUM = "go_sum"

    # Ruby
    GEMFILE_LOCK = "gemfile_lock"

    # Java
    POM_XML = "pom_xml"
    GRADLE_LOCKFILE = "gradle_lockfile"


class Ecosystem(str, Enum):
    """パッケージエコシステム"""

    PYTHON = "python"
    NPM = "npm"
    GO = "go"
    RUBY = "ruby"
    MAVEN = "maven"


class Dependency(BaseModel):
    """依存パッケージの基本情報（拡張版）"""

    name: str = Field(..., description="パッケージ名", min_length=1)
    version: str | None = Field(None, description="バージョン指定（任意）")
    ecosystem: Ecosystem | None = Field(None, description="パッケージエコシステム")

    # Java固有フィールド（オプション）
    group_id: str | None = Field(None, description="Maven groupId")
    artifact_id: str | None = Field(None, description="Maven artifactId")

    # Go固有フィールド（オプション）
    module_path: str | None = Field(None, description="Goモジュールパス")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"name": "requests", "version": "2.32.3", "ecosystem": "python"},
                {
                    "name": "commons-lang3",
                    "version": "3.12.0",
                    "ecosystem": "maven",
                    "group_id": "org.apache.commons",
                    "artifact_id": "commons-lang3",
                },
            ]
        }
    }


class LicenseInfo(BaseModel):
    """ライセンス情報"""

    license: str | None = Field(None, description="ライセンス名（SPDX ID推奨）")
    license_text_url: str | None = Field(None, description="ライセンステキストURL")
    homepage_url: str | None = Field(None, description="プロジェクトホームページURL")
    license_source: str | None = Field(
        None,
        description="ライセンス情報の出所（pypi/npm/rubygems/go/github/spdx/llm/metadata）",
    )
    # Agent Integration Fields
    agent_search: "AgentSearchResult | None" = Field(None, description="Agent検索結果（あれば）")
    custom_classification: "CustomLicenseClassification | None" = Field(
        None, description="カスタムライセンス分類（あれば）"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "license": "Apache-2.0",
                    "license_text_url": "https://github.com/psf/requests/blob/main/LICENSE",
                    "homepage_url": "https://requests.readthedocs.io/",
                }
            ]
        }
    }


class DependencyWithLicense(Dependency, LicenseInfo):
    """ライセンス情報を含む依存パッケージ"""

    pass


class PolicyRule(BaseModel):
    """ポリシールール（policy.json内の1つのルール）"""

    license: str = Field(..., description="対象ライセンス名", min_length=1)
    status: Literal["allow", "review", "deny"] = Field(..., description="判定ステータス")
    reason: str | None = Field(None, description="理由・説明")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "license": "GPL-3.0-only",
                    "status": "deny",
                    "reason": "自社プロダクトとのライセンス衝突リスクが高い",
                }
            ]
        }
    }


class PolicyConfig(BaseModel):
    """ポリシー設定ファイル（policy.json）"""

    version: int = Field(default=1, description="ポリシー設定のバージョン", ge=1)
    default_status: Literal["allow", "review", "deny"] = Field(
        default="review", description="デフォルトステータス"
    )
    rules: list[PolicyRule] = Field(default_factory=list, description="ルールリスト")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "version": 1,
                    "default_status": "review",
                    "rules": [
                        {"license": "MIT", "status": "allow", "reason": "商用利用可能"},
                        {"license": "GPL-3.0-only", "status": "deny", "reason": "コピーレフト"},
                    ],
                }
            ]
        }
    }


class PolicyDecision(BaseModel):
    """ポリシー判定結果"""

    status: Literal["allow", "review", "deny"] = Field(..., description="判定結果")
    reason: str | None = Field(None, description="判定理由")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "deny",
                    "reason": "GPL-3.0-only は組織ポリシーで禁止されています。",
                }
            ]
        }
    }


class DependencyWithPolicy(DependencyWithLicense):
    """ポリシー判定を含む依存パッケージ"""

    policy: PolicyDecision | None = Field(None, description="ポリシー判定結果")


class LicenseCount(BaseModel):
    """ライセンスごとの件数"""

    license: str = Field(..., description="ライセンス名")
    count: int = Field(..., ge=0, description="パッケージ数")


class ScanSummary(BaseModel):
    """スキャン結果のサマリー"""

    total_dependencies: int = Field(..., ge=0, description="総依存パッケージ数")
    by_license: list[LicenseCount] = Field(default_factory=list, description="ライセンス別集計")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "total_dependencies": 42,
                    "by_license": [
                        {"license": "MIT", "count": 20},
                        {"license": "Apache-2.0", "count": 15},
                    ],
                }
            ]
        }
    }


class PolicySummary(BaseModel):
    """ポリシー判定のサマリー"""

    applied: bool = Field(..., description="ポリシーが適用されたか")
    by_status: dict[str, int] | None = Field(None, description="ステータス別集計")

    model_config = {
        "json_schema_extra": {
            "examples": [{"applied": True, "by_status": {"allow": 35, "review": 5, "deny": 2}}]
        }
    }


# LLM Integration Models


class LicenseInference(BaseModel):
    """
    LLMによるライセンス推測結果

    Attributes:
        license: 推測されたライセンス名（SPDX ID形式）
        confidence: 信頼度スコア（0.0～1.0）
        reasoning: 推測の根拠（最低10文字）
        sources: 参照した情報源のリスト（PyPI URL、GitHub URLなど）
    """

    license: str = Field(
        description="推測されたライセンス名（SPDX ID形式）",
        examples=["MIT", "Apache-2.0", "BSD-3-Clause", "Unknown"],
    )
    confidence: float = Field(description="信頼度スコア（0.0～1.0）", ge=0.0, le=1.0)
    reasoning: str = Field(description="推測の根拠", min_length=10)
    sources: list[str] = Field(
        default_factory=list,
        description="参照した情報源のURL",
        examples=[["https://pypi.org/project/requests/", "https://github.com/psf/requests"]],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "license": "Apache-2.0",
                    "confidence": 0.95,
                    "reasoning": "requestsはApache-2.0で長年公開されている有名なプロジェクト",
                    "sources": [
                        "https://pypi.org/project/requests/",
                        "https://github.com/psf/requests",
                    ],
                }
            ]
        }
    }


class PolicyExplanation(BaseModel):
    """
    LLMによるポリシー判断の説明

    Attributes:
        explanation: ポリシー判断の説明（50～200文字）
    """

    explanation: str = Field(description="ポリシー判断の説明", min_length=50, max_length=200)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "explanation": "GPL-3.0はコピーレフトライセンスで、派生物も同じライセンスで公開する必要があります。プロプライエタリ製品との組み合わせにリスクがあるため、denyと判定されました。"
                }
            ]
        }
    }


class LicenseSummary(BaseModel):
    """
    LLMによるライセンス要約

    Attributes:
        summary_points: ライセンスの要点（3～5個の箇条書き）
    """

    summary_points: list[str] = Field(
        description="ライセンスの要点（3～5個の箇条書き）", min_length=3, max_length=5
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary_points": [
                        "商用利用可能",
                        "再配布時はライセンステキストとコピーライト表示が必要",
                        "派生物を異なるライセンスで配布可能（Copyleftなし）",
                    ]
                }
            ]
        }
    }


class DependencyWithLLM(DependencyWithPolicy):
    """
    LLM推測を含む依存パッケージ（DependencyWithPolicyを拡張）

    Attributes:
        llm_inference: LLMによるライセンス推測結果（オプション）
        llm_policy_explanation: LLMによるポリシー判断の説明（オプション）
        llm_summary: LLMによるライセンス要約（オプション）
    """

    llm_inference: LicenseInference | None = Field(
        default=None, description="LLMによるライセンス推測結果（ライセンス不明の場合のみ）"
    )
    llm_policy_explanation: str | None = Field(
        default=None, description="LLMによるポリシー判断の説明（ポリシー適用時のみ）"
    )
    llm_summary: LicenseSummary | None = Field(
        default=None, description="LLMによるライセンス要約（--verbose時のみ）"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "unknown-lib",
                    "version": "1.0.0",
                    "license": "Apache-2.0",
                    "license_text_url": None,
                    "homepage_url": None,
                    "policy": {"status": "allow", "reason": "Permissive license"},
                    "llm_inference": {
                        "license": "Apache-2.0",
                        "confidence": 0.85,
                        "reasoning": "GitHubリポジトリにAPACHE-2.0ライセンスファイルが存在",
                        "sources": ["https://github.com/example/unknown-lib"],
                    },
                    "llm_policy_explanation": "Apache-2.0は特許条項を含む寛容なライセンスで、商用利用が可能です。",
                    "llm_summary": {
                        "summary_points": [
                            "商用利用可能",
                            "特許権の明示的な許諾",
                            "帰属表示とライセンステキストの保持が必要",
                        ]
                    },
                }
            ]
        }
    }


class LLMStats(BaseModel):
    """
    LLM統計情報

    Attributes:
        inference_count: LLM推測実行回数
        cache_hits: キャッシュヒット数
        cache_misses: キャッシュミス数
        cache_hit_rate: キャッシュヒット率（0.0～1.0）
    """

    inference_count: int = Field(default=0, ge=0, description="LLM推測実行回数")
    cache_hits: int = Field(default=0, ge=0, description="キャッシュヒット数")
    cache_misses: int = Field(default=0, ge=0, description="キャッシュミス数")
    cache_hit_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="キャッシュヒット率")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "inference_count": 10,
                    "cache_hits": 6,
                    "cache_misses": 4,
                    "cache_hit_rate": 0.6,
                }
            ]
        }
    }


# Agent Integration Models


class ToolCallLog(BaseModel):
    """ツール呼び出しログ"""

    tool_name: Literal["pypi_search", "github_search", "spdx_search"] = Field(
        ..., description="ツール名"
    )
    input_params: dict[str, object] = Field(..., description="入力パラメータ")
    output_result: dict[str, object] | None = Field(None, description="出力結果（成功時）")
    error_message: str | None = Field(None, description="エラーメッセージ（失敗時）")
    execution_time_ms: float = Field(..., ge=0.0, description="実行時間（ミリ秒）")
    status: Literal["success", "error", "timeout"] = Field(..., description="実行ステータス")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="実行時刻")

    def is_successful(self) -> bool:
        """成功したか判定"""
        return self.status == "success"

    def get_display_status(self) -> str:
        """表示用ステータス"""
        if self.status == "success":
            return f"✓ {self.tool_name} ({self.execution_time_ms:.0f}ms)"
        elif self.status == "timeout":
            return f"⏱ {self.tool_name} (timeout)"
        else:
            return f"✗ {self.tool_name} ({self.error_message})"


class AgentSearchResult(BaseModel):
    """Agent検索結果"""

    package_name: str = Field(..., description="パッケージ名")
    version: str = Field(..., description="パッケージバージョン")
    license_name: str | None = Field(None, description="推測されたライセンス名")
    confidence: float = Field(..., ge=0.0, le=1.0, description="信頼度スコア（0.0～1.0）")
    source: Literal["pypi", "npm", "rubygems", "go", "github", "spdx", "llm"] = Field(
        ..., description="情報源（pypi/npm/rubygems/go/github/spdx/llm）"
    )
    homepage_url: str | None = Field(None, description="パッケージホームページURL")
    license_text_url: str | None = Field(None, description="ライセンステキストURL")
    reasoning: list[str] = Field(
        default_factory=list, description="推論プロセス（Thoughtステップのリスト）"
    )
    tool_calls: list[ToolCallLog] = Field(default_factory=list, description="ツール呼び出し履歴")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="検索実行時刻"
    )

    def get_display_name(self) -> str:
        """表示用ライセンス名を生成"""
        if not self.license_name:
            return f"Unknown (confidence: {self.confidence:.2f}, manual review required)"

        if self.confidence >= 0.8:
            return f"Inferred: {self.license_name} (confidence: {self.confidence:.2f})"
        elif self.confidence >= 0.5:
            return f"Inferred: {self.license_name} (confidence: {self.confidence:.2f}, verify recommended)"
        else:
            return f"Inferred: {self.license_name} (confidence: {self.confidence:.2f}, manual review required)"


# AgentConfig is imported from oss_license_scan.agent.config
# See TYPE_CHECKING import at the top of this file


class LicenseCompatibility(BaseModel):
    """ライセンス互換性評価結果"""

    license_a: str = Field(..., description="ライセンスA（例: MIT）")
    license_b: str = Field(..., description="ライセンスB（例: GPL-3.0）")
    status: Literal["compatible", "conditional", "incompatible", "unknown"] = Field(
        ..., description="互換性ステータス"
    )
    explanation: str = Field(..., description="互換性の根拠（自然言語）")
    conditions: list[str] = Field(
        default_factory=list, description="条件付き互換の場合の条件リスト"
    )
    source: Literal["rules", "llm"] = Field(..., description="判定ソース（ルールベース/LLM）")

    def is_compatible(self) -> bool:
        """互換性があるか判定"""
        return self.status in ["compatible", "conditional"]

    def get_display_status(self) -> str:
        """表示用ステータス"""
        icons = {"compatible": "✓", "conditional": "⚠", "incompatible": "✗", "unknown": "?"}
        return f"{icons[self.status]} {self.license_a} ⇄ {self.license_b}: {self.status}"


class CustomLicenseClassification(BaseModel):
    """カスタムライセンス分類結果"""

    license_text: str = Field(..., description="ライセンステキスト（要約版、最大1000文字）")
    category: Literal["permissive", "copyleft", "proprietary", "unknown"] = Field(
        ..., description="推定カテゴリ"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="信頼度スコア（0.0～1.0）")
    rationale: list[str] = Field(
        default_factory=list, description="分類根拠（キーワードや条項の抜粋）"
    )
    key_terms: list[str] = Field(default_factory=list, description="重要な条項リスト")
    risk_level: Literal["low", "medium", "high", "unknown"] = Field(
        "unknown", description="リスクレベル"
    )

    def get_display_category(self) -> str:
        """表示用カテゴリ名"""
        category_names = {
            "permissive": "寛容（Permissive）ライセンス",
            "copyleft": "コピーレフト（Copyleft）ライセンス",
            "proprietary": "プロプライエタリ（Proprietary）ライセンス",
            "unknown": "分類不能（Unknown）",
        }
        return f"{category_names[self.category]} (confidence: {self.confidence:.2f})"

    def get_risk_description(self) -> str:
        """リスクレベルの説明"""
        risk_descriptions = {
            "low": "低リスク: 商用プロジェクトでの使用に問題なし",
            "medium": "中リスク: 条項を確認してから使用を検討",
            "high": "高リスク: 法務チームへの相談を推奨",
            "unknown": "リスク不明: 手動レビューが必要",
        }
        return risk_descriptions[self.risk_level]


class ScanReport(BaseModel):
    """スキャン結果レポート全体"""

    project_type: str = Field(..., description="プロジェクトタイプ")
    generated_at: datetime = Field(..., description="生成日時")
    summary: ScanSummary = Field(..., description="スキャンサマリー")
    dependencies: list[DependencyWithPolicy] = Field(default_factory=list, description="依存リスト")
    policy_summary: PolicySummary = Field(..., description="ポリシーサマリー")
    warnings: list[str] = Field(default_factory=list, description="警告メッセージリスト")
    llm_stats: LLMStats | None = Field(default=None, description="LLM統計情報（LLM統合時のみ）")
    # Agent Integration Fields
    compatibility_summary: dict[str, int] = Field(
        default_factory=dict,
        description="互換性チェックサマリー（compatible/conditional/incompatible/unknown件数）",
    )
    custom_classifications: dict[str, "CustomLicenseClassification"] = Field(
        default_factory=dict,
        description="カスタムライセンス分類結果（ライセンス名 → 分類結果）",
    )
    agent_statistics: dict[str, object] = Field(
        default_factory=dict,
        description="Agent統計情報（平均ツール呼び出し数、キャッシュヒット率等）",
    )
    # Deep Mode Fields
    mode: str = Field(
        default="fast",
        description="解決モード: fast（最初のソースで確定）/ deep（全ソース照合）",
    )
    divergent_count: int = Field(
        default=0,
        description="不整合パッケージ数（deepモード時のみ意味がある）",
    )
    deep_source_stats: dict[str, int] = Field(
        default_factory=dict,
        description="deepモード時の各ソースからの取得結果件数（例: {'pypi': 8, 'github': 0}）",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "project_type": "python-requirements",
                    "generated_at": "2025-11-21T12:34:56Z",
                    "summary": {
                        "total_dependencies": 42,
                        "by_license": [{"license": "MIT", "count": 20}],
                    },
                    "dependencies": [],
                    "policy_summary": {"applied": False, "by_status": None},
                    "warnings": [],
                    "llm_stats": None,
                    "compatibility_summary": {},
                    "custom_classifications": {},
                    "agent_statistics": {},
                }
            ]
        }
    }


class ParseResult(BaseModel):
    """パース結果"""

    format: LockFileFormat = Field(..., description="検出されたファイル形式")
    ecosystem: Ecosystem = Field(..., description="パッケージエコシステム")
    dependencies: list[Dependency] = Field(default_factory=list, description="依存パッケージリスト")
    warnings: list[str] = Field(default_factory=list, description="警告メッセージ")
    metadata: dict[str, object] = Field(default_factory=dict, description="追加メタデータ")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "format": "pylock_toml",
                    "ecosystem": "python",
                    "dependencies": [{"name": "requests", "version": "2.32.3"}],
                    "warnings": [],
                    "metadata": {},
                }
            ]
        }
    }


class FormatDetectionResult(BaseModel):
    """ファイル形式検出結果"""

    format: LockFileFormat | None = Field(None, description="検出された形式（不明時はNone）")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="検出信頼度")
    method: str = Field("unknown", description="検出方法（filename/content/explicit）")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "format": "pylock_toml",
                    "confidence": 1.0,
                    "method": "filename",
                }
            ]
        }
    }


# === Multi-Source License Resolution Models (011-multi-source-license) ===


class Package(BaseModel):
    """エコシステム共通のパッケージ情報モデル。

    マルチエコシステム対応のライセンス解決で使用する統一モデル。
    """

    ecosystem: str = Field(
        ...,
        description="パッケージエコシステム: python, npm, go, ruby, maven",
        min_length=1,
    )
    name: str = Field(..., description="パッケージ名", min_length=1)
    version: str = Field(..., description="バージョン文字列", min_length=1)
    extra: dict[str, object] = Field(
        default_factory=dict,
        description="エコシステム固有情報（groupId, artifactId, module_path等）",
    )

    @property
    def key(self) -> str:
        """一意識別子: ecosystem:name@version"""
        return f"{self.ecosystem}:{self.name}@{self.version}"

    @classmethod
    def from_dependency(cls, dep: "Dependency") -> "Package":
        """DependencyモデルからPackageモデルに変換する。

        Args:
            dep: 変換元のDependency

        Returns:
            Package: 変換後のPackageインスタンス

        Raises:
            ValueError: バージョンが指定されていない場合
        """
        if dep.version is None:
            raise ValueError(f"Package version is required: {dep.name}")

        # エコシステムを決定（Dependencyにecosystemがあればそれを使用、なければpython）
        ecosystem = dep.ecosystem.value if dep.ecosystem else "python"

        # エコシステム固有情報をextraに格納
        extra: dict[str, object] = {}
        if dep.group_id:
            extra["group_id"] = dep.group_id
        if dep.artifact_id:
            extra["artifact_id"] = dep.artifact_id
        if dep.module_path:
            extra["module_path"] = dep.module_path

        # GitHubリポジトリ情報を抽出（GitHubSourceフォールバック用）
        github_repo = cls._extract_github_repo(dep.name, ecosystem)
        if github_repo:
            extra["github_repo"] = github_repo

        return cls(
            ecosystem=ecosystem,
            name=dep.name,
            version=dep.version,
            extra=extra,
        )

    @staticmethod
    def _extract_github_repo(name: str, ecosystem: str) -> str | None:
        """パッケージ名からGitHubリポジトリ情報を抽出する。

        Args:
            name: パッケージ名
            ecosystem: エコシステム名

        Returns:
            GitHubリポジトリ（owner/repo形式）、抽出できない場合はNone
        """
        # Goモジュール: github.com/owner/repo/... → owner/repo
        if ecosystem == "go" and name.startswith("github.com/"):
            parts = name.split("/")
            if len(parts) >= 3:
                return f"{parts[1]}/{parts[2]}"

        # npmパッケージ: @scope/name形式の場合、scopeがGitHub orgの可能性
        # ただし、npmの場合はレジストリから取得する方が確実なので、ここでは抽出しない

        return None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"ecosystem": "python", "name": "requests", "version": "2.31.0"},
                {
                    "ecosystem": "maven",
                    "name": "commons-lang3",
                    "version": "3.12.0",
                    "extra": {
                        "group_id": "org.apache.commons",
                        "artifact_id": "commons-lang3",
                    },
                },
            ]
        }
    }


class LicenseResult(BaseModel):
    """ライセンス情報取得結果。

    各LicenseSourceからの取得結果を統一的に表現する。
    """

    source_name: str = Field(..., description="取得元ソース名")
    package: Package = Field(..., description="対象パッケージ")
    license_spdx: str | None = Field(None, description="SPDX ID（正規化後）。正規化失敗時はNone")
    raw_license: str | None = Field(None, description="元のライセンス文字列（正規化前）")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="信頼度スコア（0.0〜1.0）")
    evidence_path: str | None = Field(None, description="証拠となるファイルパスまたはURL")
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="取得日時"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source_name": "pypi",
                    "package": {
                        "ecosystem": "python",
                        "name": "requests",
                        "version": "2.31.0",
                    },
                    "license_spdx": "Apache-2.0",
                    "raw_license": "Apache License 2.0",
                    "confidence": 1.0,
                    "evidence_path": "https://pypi.org/project/requests/",
                }
            ]
        }
    }


class DeepResult(BaseModel):
    """deepモード用の包括的ライセンス解決結果。

    全ソースからの取得結果を集約し、整合性を分析した結果。
    """

    package: Package = Field(..., description="対象パッケージ")
    final_license: str | None = Field(None, description="最終決定ライセンス（SPDX ID）")
    status: Literal["consistent", "divergent", "unknown"] = Field(
        ...,
        description="整合性ステータス: consistent=全ソース一致, divergent=不一致, unknown=情報なし",
    )
    reason: str | None = Field(None, description="ステータスの理由（divergent時は差分詳細）")
    results: list[LicenseResult] = Field(
        default_factory=list, description="各ソースからの取得結果一覧"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "package": {
                        "ecosystem": "python",
                        "name": "requests",
                        "version": "2.31.0",
                    },
                    "final_license": "Apache-2.0",
                    "status": "consistent",
                    "reason": None,
                    "results": [],
                }
            ]
        }
    }


class OverrideEntry(BaseModel):
    """単一のオーバーライドエントリ。

    license_overrides.yml内の1つのオーバーライド設定。
    """

    pattern: str = Field(..., description="パッケージ名パターン（正規表現可）")
    ecosystem: str | None = Field(None, description="対象エコシステム（Noneは全て）")
    license: str = Field(..., description="上書きするライセンス（SPDX ID）")
    reason: str | None = Field(None, description="オーバーライド理由")


class OverridesConfig(BaseModel):
    """license_overrides.yml全体の設定モデル。"""

    version: int = Field(default=1, description="設定バージョン")
    overrides: list[OverrideEntry] = Field(
        default_factory=list, description="オーバーライドエントリリスト"
    )


# Rebuild models to resolve forward references
LicenseInfo.model_rebuild()
AgentSearchResult.model_rebuild()
Package.model_rebuild()
LicenseResult.model_rebuild()
DeepResult.model_rebuild()
