"""Deep mode license resolution."""

from oss_license_scan.models import DeepResult, LicenseResult, Package
from oss_license_scan.sources.registry import SourceRegistry


def analyze_consistency(
    results: list[LicenseResult],
) -> tuple[str, str | None]:
    """ライセンス結果の整合性を分析する。

    Args:
        results: 各ソースからのライセンス結果リスト

    Returns:
        tuple[status, reason]:
            - status: "consistent" | "divergent" | "unknown"
            - reason: 不整合の場合は詳細理由、それ以外はNone
    """
    if not results:
        return "unknown", "No license information found from any source"

    # 有効なライセンス（Noneでない）を持つ結果をフィルタ
    valid_results = [r for r in results if r.license_spdx is not None]

    if not valid_results:
        return "unknown", "All sources returned unknown license"

    # ユニークなライセンスを収集
    unique_licenses = {r.license_spdx for r in valid_results}

    if len(unique_licenses) == 1:
        return "consistent", None
    else:
        # 不整合の詳細を生成
        details = ", ".join(f"{r.source_name}={r.license_spdx}" for r in valid_results)
        return "divergent", f"License mismatch: {details}"


def resolve_deep(
    packages: list[Package],
    registry: SourceRegistry,
    source_order: list[str] | None = None,
) -> dict[str, DeepResult]:
    """deepモードでパッケージのライセンスを解決する。

    各パッケージについて、すべてのソースからライセンス情報を取得し、
    整合性を分析した結果を返す。

    Args:
        packages: 解決対象のパッケージリスト
        registry: ソースレジストリ
        source_order: ソース優先順序（Noneはデフォルト順序）

    Returns:
        dict[str, DeepResult]: パッケージキー -> DeepResultのマップ
    """
    results: dict[str, DeepResult] = {}

    for pkg in packages:
        deep_result = _resolve_single_package_deep(pkg, registry, source_order)
        results[pkg.key] = deep_result

    return results


def _resolve_single_package_deep(
    pkg: Package,
    registry: SourceRegistry,
    source_order: list[str] | None = None,
) -> DeepResult:
    """単一パッケージのライセンスを全ソースで解決する。

    Args:
        pkg: 対象パッケージ
        registry: ソースレジストリ
        source_order: ソース優先順序

    Returns:
        DeepResult: 包括的ライセンス解決結果
    """
    # ソース順序が指定されている場合はそれを使用
    if source_order is not None:
        sources = registry.get_ordered(source_order)
    else:
        sources = registry.get_for_ecosystem(pkg.ecosystem)

    # 全ソースからライセンス情報を取得
    source_results: list[LicenseResult] = []

    for source in sources:
        # エコシステムフィルタリング（get_orderedの場合のみ必要）
        if source_order is not None and source.ecosystems is not None:
            if pkg.ecosystem not in source.ecosystems:
                continue

        try:
            result = source.resolve(pkg)
            if result is not None:
                source_results.append(result)
        except Exception:
            # エラーは無視して次のソースへ
            continue

    # 整合性を分析
    status, reason = analyze_consistency(source_results)

    # 最終ライセンスを決定
    final_license: str | None = None
    if status == "consistent" and source_results:
        # 全て一致なので最初の有効な結果を使用
        for result in source_results:
            if result.license_spdx is not None:
                final_license = result.license_spdx
                break
    elif status == "divergent":
        # 不整合の場合は最初の信頼度が高い結果を使用
        # （オーバーライドがあればそれが優先される）
        for result in source_results:
            if result.license_spdx is not None:
                final_license = result.license_spdx
                break

    return DeepResult(
        package=pkg,
        final_license=final_license,
        status=status,  # type: ignore
        reason=reason,
        results=source_results,
    )
