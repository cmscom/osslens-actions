"""agent_classify_custom node: カスタムライセンスを分類する"""

import logging
from typing import Any

from oss_license_scan.agent.custom_classifier import classify_custom_license
from oss_license_scan.agent.osi_check import is_osi_approved_license
from oss_license_scan.workflow.state import LicenseScanState

logger = logging.getLogger(__name__)

# Known SPDX licenses that don't need classification
KNOWN_SPDX_LICENSES = {
    "MIT",
    "Apache-2.0",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "LGPL-2.1-only",
    "LGPL-2.1-or-later",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "MPL-2.0",
    "AGPL-3.0-only",
    "ISC",
    "Unlicense",
    "0BSD",
}


def agent_classify_custom_node(state: LicenseScanState) -> dict[str, Any]:
    """
    カスタム/未知のライセンスをLLMで分類する。

    このノードは:
    1. Agentが有効かチェック
    2. 既知のSPDXライセンス以外を抽出
    3. カスタムライセンスをLLMで分類
    4. 分類結果を状態に記録

    Args:
        state: 現在のワークフロー状態

    Returns:
        dict: 更新する状態フィールド (custom_classifications)
    """
    # Check if agent is enabled
    agent_config = state.get("agent_config")
    if not agent_config or not agent_config.enabled:
        logger.info("Agent disabled, skipping custom license classification")
        return {"custom_classifications": {}}

    dependencies_with_license = state.get("dependencies_with_license", [])

    # Collect custom licenses (non-SPDX)
    custom_licenses = set()
    for dep in dependencies_with_license:
        if dep.license and dep.license not in KNOWN_SPDX_LICENSES:
            # Check if it's OSI-approved (which means it's likely a known SPDX license)
            if not is_osi_approved_license(dep.license):
                custom_licenses.add(dep.license)

    logger.info(f"Found {len(custom_licenses)} custom licenses to classify")

    # Classify each custom license
    custom_classifications = {}
    for license_name in custom_licenses:
        logger.info(f"Classifying custom license: {license_name}")

        # For now, use the license name as the text
        # In a real implementation, we would fetch the actual license text
        # from the license_text_url or another source
        license_text = f"License: {license_name}"

        try:
            classification = classify_custom_license(license_text)
            custom_classifications[license_name] = classification

            logger.info(
                f"Classified {license_name} as {classification.category} "
                f"(confidence: {classification.confidence:.2f})"
            )

        except Exception as e:
            logger.error(f"Error classifying {license_name}: {e}")
            # Continue with other licenses

    return {"custom_classifications": custom_classifications}
