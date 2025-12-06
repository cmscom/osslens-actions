"""OSI (Open Source Initiative) license approval checker.

This module provides functionality to check if a license is OSI-approved.
It uses the existing OSI approval data from the SPDX search module.
"""

from oss_license_scan.agent.tools.spdx_search import is_osi_approved as _is_osi_approved


def is_osi_approved_license(license_name: str) -> bool:
    """
    Check if a license is OSI-approved.

    Args:
        license_name: SPDX license identifier (e.g., "MIT", "Apache-2.0")

    Returns:
        True if the license is OSI-approved, False otherwise

    Examples:
        >>> is_osi_approved_license("MIT")
        True
        >>> is_osi_approved_license("Apache-2.0")
        True
        >>> is_osi_approved_license("Proprietary")
        False
    """
    return _is_osi_approved(license_name)
