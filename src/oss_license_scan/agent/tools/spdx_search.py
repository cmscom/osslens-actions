"""SPDX License Database search tool for LangChain Agent."""

from typing import Any

from langchain_core.tools import tool
from license_expression import ExpressionError, Licensing, get_spdx_licensing

# Common license name mappings for normalization
COMMON_MAPPINGS = {
    "bsd": "BSD-3-Clause",
    "lgpl": "LGPL-3.0-only",
    "gpl": "GPL-3.0-only",
    "apache": "Apache-2.0",
    "mpl": "MPL-2.0",
    "agpl": "AGPL-3.0-only",
    "cc0": "CC0-1.0",
    "unlicense": "Unlicense",
}

# OSI-approved licenses (curated list based on https://opensource.org/licenses/)
OSI_APPROVED_LICENSES = {
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
    "ISC",
    "MPL-2.0",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
    "Artistic-2.0",
    "EPL-1.0",
    "EPL-2.0",
    "EUPL-1.2",
    "CC0-1.0",
    "Unlicense",
    "0BSD",
    "AAL",
    "AFL-3.0",
    "APL-1.0",
    "APSL-2.0",
    "BSL-1.0",
    "CATOSL-1.1",
    "ECL-2.0",
    "EFL-2.0",
    "Entessa",
    "EUPL-1.1",
    "Fair",
    "Frameworx-1.0",
    "HPND",
    "Intel",
    "IPA",
    "LiLiQ-P-1.1",
    "LiLiQ-R-1.1",
    "LiLiQ-Rplus-1.1",
    "LPL-1.02",
    "LPPL-1.3c",
    "MirOS",
    "MS-PL",
    "MS-RL",
    "MulanPSL-2.0",
    "NASA-1.3",
    "NCSA",
    "NGPL",
    "Nokia",
    "NPOSL-3.0",
    "NTP",
    "OCLC-2.0",
    "OFL-1.1",
    "OGTSL",
    "OSL-3.0",
    "PHP-3.0",
    "PostgreSQL",
    "Python-2.0",
    "RPL-1.5",
    "RPSL-1.0",
    "RSCPL",
    "SimPL-2.0",
    "Sleepycat",
    "SPL-1.0",
    "UPL-1.0",
    "VSL-1.0",
    "W3C",
    "Watcom-1.0",
    "Xnet",
    "Zlib",
    "ZPL-2.0",
}


def normalize_license_name(license_text: str) -> str | None:
    """
    Normalize license name using SPDX license list.

    Args:
        license_text: License name or identifier to normalize

    Returns:
        Normalized SPDX license identifier, or None if not found
    """
    if not license_text:
        return None

    # Get SPDX licensing object with official license list
    spdx = get_spdx_licensing()

    # Try exact match first (case-insensitive)
    license_key = license_text.strip()

    try:
        # Validate against SPDX license list
        validated = spdx.validate(license_key)
        # Check if validation succeeded (normalized_expression is not None and no errors)
        if validated and validated.normalized_expression and not validated.errors:
            return validated.normalized_expression
    except (ExpressionError, AttributeError):
        pass

    # Try common mappings
    lower_key = license_key.lower()
    if lower_key in COMMON_MAPPINGS:
        return COMMON_MAPPINGS[lower_key]

    # License not found
    return None


def is_osi_approved(license_name: str) -> bool:
    """
    Check if a license is OSI-approved.

    Args:
        license_name: SPDX license identifier

    Returns:
        True if OSI-approved, False otherwise
    """
    if not license_name:
        return False

    # Check against our curated list of OSI-approved licenses
    return license_name in OSI_APPROVED_LICENSES


@tool
def spdx_search(license_text: str) -> dict[str, Any]:
    """
    Search SPDX License Database for license information.

    Use this tool to validate and normalize license identifiers using the
    official SPDX license list. It supports common license name mappings
    and OSI approval checking.

    Args:
        license_text: License name or identifier to search for

    Returns:
        Dictionary with:
        - success: bool - whether the search succeeded
        - license_name: str | None - normalized SPDX license identifier
        - is_osi_approved: bool - whether the license is OSI-approved
        - source: str - always "spdx"
        - confidence: float - confidence score (0.0-1.0)
        - error: str | None - error message if search failed
    """
    if not license_text or not license_text.strip():
        return {
            "success": False,
            "license_name": None,
            "is_osi_approved": False,
            "source": "spdx",
            "confidence": 0.0,
            "error": "Empty license text provided",
        }

    license_text = license_text.strip()

    # Handle SPDX expressions (AND/OR/WITH operators)
    # Extract first valid license from expression
    licensing = Licensing()
    try:
        expr = licensing.parse(license_text)

        # If it's a complex expression, extract individual licenses
        if expr is not None and hasattr(expr, "symbols") and expr.symbols:
            # symbols is a set, convert to list and take first element
            symbols_list = list(expr.symbols)
            if symbols_list:
                first_license = str(symbols_list[0])
                license_text = first_license
    except ExpressionError:
        # Not a valid SPDX expression, treat as simple license name
        pass

    # Normalize the license name
    normalized = normalize_license_name(license_text)

    if normalized:
        # Check OSI approval
        osi_approved = is_osi_approved(normalized)

        # Determine confidence based on match type
        confidence = 1.0  # Exact SPDX match

        # Lower confidence for common mappings
        if license_text.lower() in COMMON_MAPPINGS:
            confidence = 0.8

        return {
            "success": True,
            "license_name": normalized,
            "is_osi_approved": osi_approved,
            "source": "spdx",
            "confidence": confidence,
            "error": None,
        }

    # License not found in SPDX database
    return {
        "success": False,
        "license_name": None,
        "is_osi_approved": False,
        "source": "spdx",
        "confidence": 0.0,
        "error": f"License '{license_text}' not found in SPDX license list",
    }
