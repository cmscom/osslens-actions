"""analyze_divergence node: deepモードで不整合パッケージを分析する"""

import logging
from typing import Any

from oss_license_scan.workflow.messages import MessageTemplates
from oss_license_scan.workflow.state import LicenseScanState

logger = logging.getLogger(__name__)


def analyze_divergence_node(state: LicenseScanState) -> dict[str, Any]:
    """
    deepモードの不整合パッケージを分析し、警告を生成する。

    Args:
        state: 現在のワークフロー状態

    Returns:
        dict: 更新する状態フィールド (warnings)
    """
    logger.info(MessageTemplates.NODE_START.format(node_name="analyze_divergence"))

    mode = state.get("mode", "fast")
    if mode != "deep":
        # deepモード以外では何もしない
        return {}

    divergent_packages = state.get("divergent_packages", [])
    deep_results = state.get("deep_results", {})

    if not divergent_packages:
        logger.info("No divergent packages found - all licenses are consistent")
        return {}

    # 不整合パッケージの詳細な警告を生成
    warnings: list[str] = []

    for pkg_key in divergent_packages:
        deep_result = deep_results.get(pkg_key)
        if deep_result:
            # 各ソースのライセンス情報を収集
            source_licenses = []
            for result in deep_result.results:
                if result.license_spdx:
                    source_licenses.append(f"{result.source_name}={result.license_spdx}")

            if source_licenses:
                warning = f"License divergence detected for {pkg_key}: {', '.join(source_licenses)}"
            else:
                warning = f"License divergence detected for {pkg_key}: {deep_result.reason}"

            warnings.append(warning)
            logger.warning(warning)

    logger.info(
        f"Divergence analysis complete: {len(divergent_packages)} packages with inconsistent licenses"
    )

    return {"warnings": warnings}
