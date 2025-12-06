"""Markdown reporter for scan results."""

from pathlib import Path

from oss_license_scan.models import DependencyWithLLM, ScanReport


def generate_markdown(report: ScanReport) -> str:
    """
    Generate Markdown format report from scan results.

    Args:
        report: ScanReport object

    Returns:
        Markdown formatted string
    """
    lines: list[str] = []

    # タイトル
    lines.append("# ライセンススキャンレポート")
    lines.append("")
    lines.append(f"**プロジェクトタイプ**: {report.project_type}")
    lines.append(f"**生成日時**: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**解決モード**: {report.mode}")
    lines.append("")

    # サマリーセクション
    lines.append("## サマリー")
    lines.append("")
    lines.append(f"**依存パッケージ総数**: {report.summary.total_dependencies}")

    # deepモード時の不整合情報とソース統計
    if report.mode == "deep":
        if report.divergent_count > 0:
            lines.append(f"**⚠️ 不整合パッケージ数**: {report.divergent_count}")
        else:
            lines.append("**✅ 不整合パッケージ数**: 0（全て一致）")

        # ソース別取得結果を表示
        if report.deep_source_stats:
            lines.append("")
            lines.append("### 参照ソース別取得結果")
            lines.append("")
            lines.append("| ソース | 取得成功件数 |")
            lines.append("|--------|-------------|")
            for source_name, count in sorted(report.deep_source_stats.items()):
                lines.append(f"| {source_name} | {count} |")
        else:
            lines.append("")
            lines.append("*deepモードで参照したソースからの取得結果はありません。*")

    lines.append("")

    # ライセンス集計テーブル
    if report.summary.by_license:
        lines.append("### ライセンス別集計")
        lines.append("")
        lines.append("| ライセンス | 件数 |")
        lines.append("|-----------|------|")

        for license_count in report.summary.by_license:
            license_name = license_count.license if license_count.license else "Unknown"
            lines.append(f"| {license_name} | {license_count.count} |")

        lines.append("")

    # LLM統計セクション（LLM推測が実行された場合）
    if report.llm_stats and report.llm_stats.inference_count > 0:
        lines.append("### LLM推測統計")
        lines.append("")
        lines.append(f"**推測実行回数**: {report.llm_stats.inference_count}")
        lines.append(f"**キャッシュヒット**: {report.llm_stats.cache_hits}")
        lines.append(f"**キャッシュミス**: {report.llm_stats.cache_misses}")
        lines.append(f"**キャッシュヒット率**: {report.llm_stats.cache_hit_rate:.1%}")
        lines.append("")

    # 依存パッケージ一覧
    lines.append("## 依存パッケージ")
    lines.append("")

    if report.dependencies:
        # ポリシーが適用されている場合は列を追加
        if report.policy_summary.applied:
            lines.append(
                "| パッケージ名 | バージョン | ライセンス | 出所元 | ポリシー | ホームページ |"
            )
            lines.append("|-------------|-----------|-----------|--------|---------|-------------|")

            for dep in report.dependencies:
                name = dep.name
                version = dep.version if dep.version else "N/A"
                license_name = dep.license if dep.license else "Unknown"
                license_source = dep.license_source if dep.license_source else "N/A"
                homepage = dep.homepage_url if dep.homepage_url else "N/A"

                # ポリシーステータス
                policy_status = "N/A"
                if dep.policy:
                    status = dep.policy.status
                    # 絵文字でステータスを表現
                    if status == "allow":
                        policy_status = "✅ allow"
                    elif status == "deny":
                        policy_status = "❌ deny"
                    elif status == "review":
                        policy_status = "⚠️ review"
                    elif status == "warn":
                        policy_status = "⚠️ warn"
                    else:
                        policy_status = status

                # Markdownリンク形式に変換
                if homepage and homepage != "N/A":
                    homepage_link = f"[Link]({homepage})"
                else:
                    homepage_link = "N/A"

                lines.append(
                    f"| {name} | {version} | {license_name} | {license_source} | {policy_status} | {homepage_link} |"
                )
        else:
            # ポリシーなしの場合
            lines.append("| パッケージ名 | バージョン | ライセンス | 出所元 | ホームページ |")
            lines.append("|-------------|-----------|-----------|--------|-------------|")

            for dep in report.dependencies:
                name = dep.name
                version = dep.version if dep.version else "N/A"
                license_name = dep.license if dep.license else "Unknown"
                license_source = dep.license_source if dep.license_source else "N/A"
                homepage = dep.homepage_url if dep.homepage_url else "N/A"

                # Markdownリンク形式に変換
                if homepage and homepage != "N/A":
                    homepage_link = f"[Link]({homepage})"
                else:
                    homepage_link = "N/A"

                lines.append(
                    f"| {name} | {version} | {license_name} | {license_source} | {homepage_link} |"
                )

        lines.append("")
    else:
        lines.append("依存パッケージはありません。")
        lines.append("")

    # ポリシーサマリー（適用されている場合）
    if report.policy_summary.applied:
        lines.append("## ポリシーチェック結果")
        lines.append("")

        if report.policy_summary.by_status:
            lines.append("| ステータス | 件数 |")
            lines.append("|-----------|------|")

            for status, count in report.policy_summary.by_status.items():
                lines.append(f"| {status} | {count} |")

            lines.append("")

    # 互換性チェック結果セクション
    if report.compatibility_summary:
        lines.append("## ライセンス互換性チェック")
        lines.append("")

        # サマリーテーブル
        lines.append("### 互換性サマリー")
        lines.append("")
        lines.append("| ステータス | 件数 |")
        lines.append("|-----------|------|")

        status_emoji = {
            "compatible": "✅",
            "conditional": "⚠️",
            "incompatible": "❌",
            "unknown": "❓",
        }

        for status in ["compatible", "conditional", "incompatible", "unknown"]:
            count = report.compatibility_summary.get(status, 0)
            emoji = status_emoji.get(status, "")
            status_label = {
                "compatible": "互換性あり",
                "conditional": "条件付き互換",
                "incompatible": "非互換",
                "unknown": "不明",
            }.get(status, status)
            lines.append(f"| {emoji} {status_label} | {count} |")

        lines.append("")

    # カスタムライセンス分類セクション
    if report.custom_classifications:
        lines.append("## カスタムライセンス分類")
        lines.append("")
        lines.append("LLMによるカスタムライセンスの分類結果:")
        lines.append("")

        # カテゴリー別の絵文字
        category_emoji = {
            "permissive": "✅",
            "copyleft": "⚠️",
            "proprietary": "❌",
            "unknown": "❓",
        }

        # リスクレベル別の絵文字
        risk_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🔴",
            "unknown": "⚪",
        }

        for license_name, classification in sorted(report.custom_classifications.items()):
            category = classification.category
            risk_level = classification.risk_level

            cat_emoji = category_emoji.get(category, "")
            risk_em = risk_emoji.get(risk_level, "")

            category_label = {
                "permissive": "Permissive（寛容）",
                "copyleft": "Copyleft（継承必須）",
                "proprietary": "Proprietary（独占）",
                "unknown": "Unknown（不明）",
            }.get(category, category)

            risk_label = {
                "low": "低",
                "medium": "中",
                "high": "高",
                "unknown": "不明",
            }.get(risk_level, risk_level)

            lines.append(f"### {license_name}")
            lines.append("")
            lines.append(f"**カテゴリー**: {cat_emoji} {category_label}")
            lines.append(f"**リスクレベル**: {risk_em} {risk_label}")
            lines.append(f"**信頼度**: {classification.confidence:.0%}")
            lines.append("")

            if classification.rationale:
                lines.append("**判定理由**:")
                for reason in classification.rationale:
                    lines.append(f"- {reason}")
                lines.append("")

            if classification.key_terms:
                lines.append(f"**キーワード**: {', '.join(classification.key_terms)}")
                lines.append("")

        lines.append("")

    # LLMライセンス要約セクション（LLM有効でライセンス要約がある場合）
    if report.dependencies:
        # ライセンス要約があるパッケージを抽出
        deps_with_summary = [
            dep
            for dep in report.dependencies
            if isinstance(dep, DependencyWithLLM) and dep.llm_summary
        ]

        if deps_with_summary:
            lines.append("## LLMライセンス要約")
            lines.append("")

            for dep in deps_with_summary:
                lines.append(f"### {dep.name} ({dep.license})")
                lines.append("")

                # 要約ポイントを箇条書きで表示
                if dep.llm_summary:  # Type guard
                    for point in dep.llm_summary.summary_points:
                        lines.append(f"- {point}")

                lines.append("")

    # LLMポリシー説明セクション（LLM有効でポリシー説明がある場合）
    if report.dependencies:
        # ポリシー説明があるパッケージを抽出
        deps_with_explanation = [
            dep
            for dep in report.dependencies
            if isinstance(dep, DependencyWithLLM) and dep.llm_policy_explanation
        ]

        if deps_with_explanation:
            lines.append("## LLMポリシー説明")
            lines.append("")

            for dep in deps_with_explanation:
                lines.append(f"### {dep.name} ({dep.license})")
                lines.append("")
                if dep.policy:
                    status_emoji = {
                        "allow": "✅",
                        "deny": "❌",
                        "review": "⚠️",
                        "warn": "⚠️",
                    }.get(dep.policy.status, "")
                    lines.append(f"**ポリシーステータス**: {status_emoji} {dep.policy.status}")
                    lines.append("")
                if dep.llm_policy_explanation:  # Type guard
                    lines.append(dep.llm_policy_explanation)
                lines.append("")

    # 警告セクション
    if report.warnings:
        lines.append("## 警告")
        lines.append("")

        for warning in report.warnings:
            lines.append(f"⚠️ {warning}")

        lines.append("")

    return "\n".join(lines)


def export_markdown(report: ScanReport, output_path: Path | str) -> str:
    """
    Export scan report to Markdown file.

    Args:
        report: ScanReport to export
        output_path: Path to write Markdown file

    Returns:
        Markdown string that was written
    """
    markdown_str = generate_markdown(report)

    path = Path(output_path)
    path.write_text(markdown_str, encoding="utf-8")

    return markdown_str
