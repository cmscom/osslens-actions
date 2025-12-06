"""resolve_licenses node: 各依存関係のライセンス情報を解決"""

import logging
from pathlib import Path
from typing import Any

from oss_license_scan.models import (
    Dependency,
    DependencyWithLicense,
    LicenseResult,
    OverridesConfig,
    Package,
)
from oss_license_scan.resolver.deep import resolve_deep
from oss_license_scan.resolver.fast import resolve_fast
from oss_license_scan.resolvers.metadata_resolver import resolve_licenses
from oss_license_scan.sources.github_source import GitHubSource
from oss_license_scan.sources.go_source import GoLicensesSource
from oss_license_scan.sources.local_source import LocalLicenseSource
from oss_license_scan.sources.maven_source import MavenCentralSource
from oss_license_scan.sources.npm_source import NpmRegistrySource
from oss_license_scan.sources.overrides_source import OverridesSource, load_overrides_config
from oss_license_scan.sources.pypi_source import PyPISource
from oss_license_scan.sources.registry import SourceRegistry
from oss_license_scan.sources.rubygems_source import RubyGemsSource
from oss_license_scan.workflow.messages import MessageTemplates
from oss_license_scan.workflow.state import LicenseScanState

logger = logging.getLogger(__name__)


def _create_default_registry(
    overrides_config: OverridesConfig | None = None,
) -> SourceRegistry:
    """デフォルトのソースレジストリを作成する。

    すべてのエコシステム用ソースを登録する。

    Args:
        overrides_config: オーバーライド設定（オプション）
    """
    registry = SourceRegistry()
    # 各エコシステム用ソースを登録（優先順位順）
    registry.register(LocalLicenseSource())  # 1. ローカルファイル（最速・オフライン可）
    registry.register(PyPISource())  # 2. Python
    registry.register(NpmRegistrySource())  # Node.js
    registry.register(GoLicensesSource())  # Go
    registry.register(RubyGemsSource())  # Ruby
    registry.register(MavenCentralSource())  # Java/Maven
    registry.register(GitHubSource())  # 3. GitHub (フォールバック、全エコシステム対応)

    # 4. オーバーライドソース（最後に登録して最終上書き）
    if overrides_config is not None:
        registry.register(OverridesSource(overrides_config))

    return registry


def resolve_licenses_node(state: LicenseScanState) -> dict[str, Any]:
    """
    各依存関係のライセンス情報を解決する。

    Args:
        state: 現在のワークフロー状態

    Returns:
        dict: 更新する状態フィールド (dependencies_with_license, warnings, fast_results)
    """
    logger.info(MessageTemplates.NODE_START.format(node_name="resolve_licenses"))

    dependencies = state.get("dependencies", [])
    mode = state.get("mode", "fast")
    source_order = state.get("license_sources")  # カスタムソース順序
    overrides_file = state.get("overrides_file")  # オーバーライドファイルパス

    if not dependencies:
        return {"dependencies_with_license": []}

    # オーバーライド設定を読み込み
    overrides_config: OverridesConfig | None = None
    warnings: list[str] = []
    if overrides_file:
        try:
            overrides_config = load_overrides_config(Path(overrides_file))
            logger.info(f"Loaded overrides from {overrides_file}")
        except FileNotFoundError:
            warning = f"Overrides file not found: {overrides_file}"
            warnings.append(warning)
            logger.warning(warning)
        except ValueError as e:
            warning = f"Invalid overrides file: {e}"
            warnings.append(warning)
            logger.warning(warning)

    try:
        # モードに応じてライセンス解決を実行
        if mode == "fast":
            result = _resolve_fast_mode(dependencies, source_order, overrides_config)
        elif mode == "deep":
            result = _resolve_deep_mode(dependencies, source_order, overrides_config)
        else:
            # レガシーモード（後方互換）
            result = _resolve_legacy_mode(dependencies)

        # オーバーライド読み込み時の警告を追加
        if warnings:
            existing_warnings = result.get("warnings", [])
            result["warnings"] = warnings + existing_warnings

        return result

    except Exception as e:
        # エラーが発生した場合、errorsに記録
        error_msg = f"Failed to resolve licenses: {str(e)}"
        logger.error(error_msg)

        return {"errors": [error_msg], "dependencies_with_license": [], "warnings": warnings}


def _resolve_fast_mode(
    dependencies: list[Dependency],
    source_order: list[str] | None = None,
    overrides_config: OverridesConfig | None = None,
) -> dict[str, Any]:
    """fastモードでライセンスを解決する。

    Args:
        dependencies: 依存パッケージリスト
        source_order: カスタムソース順序（Noneはデフォルト順序）
        overrides_config: オーバーライド設定（オプション）

    Returns:
        dict: 更新する状態フィールド
    """
    # DependencyをPackageに変換
    packages: list[Package] = []
    conversion_warnings: list[str] = []

    for dep in dependencies:
        try:
            pkg = Package.from_dependency(dep)
            packages.append(pkg)
        except ValueError as e:
            conversion_warnings.append(str(e))
            logger.debug(f"Skipping dependency without version: {dep.name}")

    if not packages:
        return {
            "dependencies_with_license": [],
            "warnings": conversion_warnings,
            "fast_results": {},
        }

    # ソースレジストリを作成してfastモードで解決
    registry = _create_default_registry(overrides_config)
    fast_results = resolve_fast(packages, registry, source_order=source_order)

    # LicenseResultをDependencyWithLicenseに変換
    dependencies_with_license: list[DependencyWithLicense] = []
    warnings: list[str] = list(conversion_warnings)

    for dep in dependencies:
        # 対応するfastモード結果を探す
        if dep.version:
            ecosystem = dep.ecosystem.value if dep.ecosystem else "python"
            pkg_key = f"{ecosystem}:{dep.name}@{dep.version}"
            result = fast_results.get(pkg_key)

            if result and result.license_spdx:
                dep_with_license = DependencyWithLicense(
                    name=dep.name,
                    version=dep.version,
                    ecosystem=dep.ecosystem,
                    group_id=dep.group_id,
                    artifact_id=dep.artifact_id,
                    module_path=dep.module_path,
                    license=result.license_spdx,
                    license_source=result.source_name,
                    license_text_url=result.evidence_path,
                )
            else:
                # 未解決
                dep_with_license = DependencyWithLicense(
                    name=dep.name,
                    version=dep.version,
                    ecosystem=dep.ecosystem,
                    group_id=dep.group_id,
                    artifact_id=dep.artifact_id,
                    module_path=dep.module_path,
                    license=None,
                )
                warnings.append(MessageTemplates.UNRESOLVED_LICENSE.format(package=dep.name))
        else:
            # バージョンなしは未解決
            dep_with_license = DependencyWithLicense(
                name=dep.name,
                version=dep.version,
                ecosystem=dep.ecosystem,
                group_id=dep.group_id,
                artifact_id=dep.artifact_id,
                module_path=dep.module_path,
                license=None,
            )
            warnings.append(MessageTemplates.UNRESOLVED_LICENSE.format(package=dep.name))

        dependencies_with_license.append(dep_with_license)

    # 解決結果をログ
    resolved_count = sum(1 for d in dependencies_with_license if d.license is not None)
    logger.info(
        MessageTemplates.RESOLVE_LICENSES_SUCCESS.format(
            resolved=resolved_count, total=len(dependencies_with_license)
        )
    )

    return {
        "dependencies_with_license": dependencies_with_license,
        "warnings": warnings,
        "fast_results": {k: v for k, v in fast_results.items() if v is not None},
    }


def _resolve_deep_mode(
    dependencies: list[Dependency],
    source_order: list[str] | None = None,
    overrides_config: OverridesConfig | None = None,
) -> dict[str, Any]:
    """deepモードでライセンスを解決する。

    Args:
        dependencies: 依存パッケージリスト
        source_order: カスタムソース順序（Noneはデフォルト順序）
        overrides_config: オーバーライド設定（オプション）

    Returns:
        dict: 更新する状態フィールド
    """
    # DependencyをPackageに変換
    packages: list[Package] = []
    conversion_warnings: list[str] = []

    for dep in dependencies:
        try:
            pkg = Package.from_dependency(dep)
            packages.append(pkg)
        except ValueError as e:
            conversion_warnings.append(str(e))
            logger.debug(f"Skipping dependency without version: {dep.name}")

    if not packages:
        return {
            "dependencies_with_license": [],
            "warnings": conversion_warnings,
            "deep_results": {},
            "divergent_packages": [],
        }

    # ソースレジストリを作成してdeepモードで解決
    registry = _create_default_registry(overrides_config)
    deep_results = resolve_deep(packages, registry, source_order=source_order)

    # DeepResultをDependencyWithLicenseに変換
    dependencies_with_license: list[DependencyWithLicense] = []
    warnings: list[str] = list(conversion_warnings)
    divergent_packages: list[str] = []

    for dep in dependencies:
        # 対応するdeepモード結果を探す
        if dep.version:
            ecosystem = dep.ecosystem.value if dep.ecosystem else "python"
            pkg_key = f"{ecosystem}:{dep.name}@{dep.version}"
            deep_result = deep_results.get(pkg_key)

            if deep_result:
                # 不整合パッケージを記録
                if deep_result.status == "divergent":
                    divergent_packages.append(pkg_key)

                if deep_result.final_license:
                    # 最も信頼度の高いソース結果を取得
                    best_result: LicenseResult | None = None
                    for result in deep_result.results:
                        if result.license_spdx == deep_result.final_license:
                            if best_result is None or result.confidence > best_result.confidence:
                                best_result = result

                    dep_with_license = DependencyWithLicense(
                        name=dep.name,
                        version=dep.version,
                        ecosystem=dep.ecosystem,
                        group_id=dep.group_id,
                        artifact_id=dep.artifact_id,
                        module_path=dep.module_path,
                        license=deep_result.final_license,
                        license_source=best_result.source_name if best_result else None,
                        license_text_url=best_result.evidence_path if best_result else None,
                    )
                else:
                    # 未解決
                    dep_with_license = DependencyWithLicense(
                        name=dep.name,
                        version=dep.version,
                        ecosystem=dep.ecosystem,
                        group_id=dep.group_id,
                        artifact_id=dep.artifact_id,
                        module_path=dep.module_path,
                        license=None,
                    )
                    warnings.append(MessageTemplates.UNRESOLVED_LICENSE.format(package=dep.name))
            else:
                # 結果なし
                dep_with_license = DependencyWithLicense(
                    name=dep.name,
                    version=dep.version,
                    ecosystem=dep.ecosystem,
                    group_id=dep.group_id,
                    artifact_id=dep.artifact_id,
                    module_path=dep.module_path,
                    license=None,
                )
                warnings.append(MessageTemplates.UNRESOLVED_LICENSE.format(package=dep.name))
        else:
            # バージョンなしは未解決
            dep_with_license = DependencyWithLicense(
                name=dep.name,
                version=dep.version,
                ecosystem=dep.ecosystem,
                group_id=dep.group_id,
                artifact_id=dep.artifact_id,
                module_path=dep.module_path,
                license=None,
            )
            warnings.append(MessageTemplates.UNRESOLVED_LICENSE.format(package=dep.name))

        dependencies_with_license.append(dep_with_license)

    # 解決結果をログ
    resolved_count = sum(1 for d in dependencies_with_license if d.license is not None)
    logger.info(
        MessageTemplates.RESOLVE_LICENSES_SUCCESS.format(
            resolved=resolved_count, total=len(dependencies_with_license)
        )
    )

    if divergent_packages:
        logger.warning(f"Found {len(divergent_packages)} packages with divergent licenses")

    return {
        "dependencies_with_license": dependencies_with_license,
        "warnings": warnings,
        "deep_results": deep_results,
        "divergent_packages": divergent_packages,
    }


def _resolve_legacy_mode(dependencies: list[Dependency]) -> dict[str, Any]:
    """既存リゾルバを使用してライセンスを解決する（後方互換）。

    Args:
        dependencies: 依存パッケージリスト

    Returns:
        dict: 更新する状態フィールド
    """
    # 既存リゾルバを再利用
    dependencies_with_license = resolve_licenses(dependencies)

    # 未解決のライセンスをカウント
    unresolved = [dep for dep in dependencies_with_license if dep.license is None]
    resolved_count = len(dependencies_with_license) - len(unresolved)

    logger.info(
        MessageTemplates.RESOLVE_LICENSES_SUCCESS.format(
            resolved=resolved_count, total=len(dependencies_with_license)
        )
    )

    # 未解決がある場合、warningsに記録
    warnings = []
    for dep in unresolved:
        warning = MessageTemplates.UNRESOLVED_LICENSE.format(package=dep.name)
        warnings.append(warning)
        logger.debug(warning)

    return {"dependencies_with_license": dependencies_with_license, "warnings": warnings}
