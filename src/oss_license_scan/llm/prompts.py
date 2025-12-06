"""LLM prompt templates for license analysis."""

from langchain_core.prompts import ChatPromptTemplate

# System prompt for license inference
LICENSE_INFERENCE_SYSTEM_PROMPT = """あなたはOSSライセンス分析の専門家です。
Pythonパッケージの名前とバージョンから、最も可能性の高いライセンスを推測してください。

制約条件:
- ライセンス名はSPDX ID形式で回答（例: MIT, Apache-2.0, GPL-3.0-only）
- 信頼度スコア（confidence）は0.0-1.0の範囲で提供
- 推測根拠（reasoning）を明確に説明（最低10文字）
- 情報が不足している場合は信頼度を下げ、"Unknown"を返す
- PyPI、GitHub、公式ドキュメントなどの情報源を参照
"""

# Few-shot examples for license inference (using {{ }} to escape braces)
LICENSE_INFERENCE_EXAMPLES = """
例1:
パッケージ: numpy
バージョン: 1.24.0
推測結果: {{"license": "BSD-3-Clause", "confidence": 0.95, "reasoning": "numpyは長年BSD-3-Clauseライセンスで公開されている著名なプロジェクト", "sources": ["https://pypi.org/project/numpy/", "https://github.com/numpy/numpy"]}}

例2:
パッケージ: requests
バージョン: 2.31.0
推測結果: {{"license": "Apache-2.0", "confidence": 0.95, "reasoning": "requestsはApache-2.0ライセンスで長年公開されている人気プロジェクト", "sources": ["https://pypi.org/project/requests/", "https://github.com/psf/requests"]}}

例3:
パッケージ: unknown-package-12345
バージョン: 0.0.1
推測結果: {{"license": "Unknown", "confidence": 0.1, "reasoning": "情報が非常に少なく、信頼できる推測ができない", "sources": []}}
"""

# License inference prompt template
LICENSE_INFERENCE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", LICENSE_INFERENCE_SYSTEM_PROMPT),
        ("assistant", LICENSE_INFERENCE_EXAMPLES),
        ("user", "パッケージ: {package_name}\nバージョン: {version}"),
    ]
)

# System prompt for policy explanation
POLICY_EXPLANATION_SYSTEM_PROMPT = """あなたはソフトウェアライセンスポリシーの専門家です。
ライセンスとポリシールールに基づいて、なぜそのような判断になったのかを説明してください。

制約条件:
- 説明は簡潔に（50-200文字）
- ビジネスリスクや法的観点を含める
- 技術者でない人にも理解できる表現を使う
- ライセンスの主要な特徴（コピーレフト、特許条項など）を説明
"""

# Policy explanation prompt template
POLICY_EXPLANATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", POLICY_EXPLANATION_SYSTEM_PROMPT),
        (
            "user",
            """ライセンス: {license}
ポリシーステータス: {status}
ポリシー理由: {policy_reason}

上記に基づいて、このライセンスがなぜこのステータスと判定されたのかを説明してください。""",
        ),
    ]
)

# System prompt for license summary
LICENSE_SUMMARY_SYSTEM_PROMPT = """あなたはライセンステキストの要約専門家です。
複雑なライセンステキストを開発者向けに箇条書きで要約してください。

制約条件:
- 3-5個の箇条書きで要約
- 商用利用可否、再配布条件、派生物の扱いを含める
- 専門用語は避け、平易な日本語を使う
- 重要な義務事項を明確に記載
"""

# License summary prompt template
LICENSE_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", LICENSE_SUMMARY_SYSTEM_PROMPT),
        (
            "user",
            "ライセンス: {license}\n\nこのライセンスの要点を3-5個の箇条書きで要約してください。",
        ),
    ]
)
