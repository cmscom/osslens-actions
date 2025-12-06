"""Fast mode license resolution."""

from oss_license_scan.models import LicenseResult, Package
from oss_license_scan.sources.registry import SourceRegistry


def resolve_fast(
    packages: list[Package],
    registry: SourceRegistry,
    source_order: list[str] | None = None,
) -> dict[str, LicenseResult | None]:
    """fastモードでパッケージのライセンスを解決する。

    各パッケージについて、ソースを優先順位順に試行し、
    最初に成功したソースの結果を返す。

    Args:
        packages: 解決対象のパッケージリスト
        registry: ソースレジストリ
        source_order: ソース優先順序（Noneはデフォルト順序）

    Returns:
        dict[str, LicenseResult | None]: パッケージキー -> 解決結果のマップ
            解決できなかったパッケージはNone
    """
    results: dict[str, LicenseResult | None] = {}

    for pkg in packages:
        result = _resolve_single_package(pkg, registry, source_order)
        results[pkg.key] = result

    return results


def _resolve_single_package(
    pkg: Package,
    registry: SourceRegistry,
    source_order: list[str] | None = None,
) -> LicenseResult | None:
    """単一パッケージのライセンスを解決する。

    Args:
        pkg: 対象パッケージ
        registry: ソースレジストリ
        source_order: ソース優先順序

    Returns:
        LicenseResult | None: 解決結果、または失敗時None
    """
    # ソース順序が指定されている場合はそれを使用
    if source_order is not None:
        sources = registry.get_ordered(source_order)
    else:
        sources = registry.get_for_ecosystem(pkg.ecosystem)

    for source in sources:
        # エコシステムフィルタリング（get_orderedの場合のみ必要）
        if source_order is not None and source.ecosystems is not None:
            if pkg.ecosystem not in source.ecosystems:
                continue

        try:
            result = source.resolve(pkg)
            if result is not None:
                return result
        except Exception:
            # エラーは無視して次のソースへ
            continue

    return None
