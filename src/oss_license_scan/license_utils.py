"""Utility functions for license name normalization."""

# License name normalization mapping (common variations -> SPDX ID)
LICENSE_NORMALIZATION_MAP: dict[str, str] = {
    # MIT variations
    "MIT License": "MIT",
    "MIT license": "MIT",
    "The MIT License": "MIT",
    "The MIT License (MIT)": "MIT",
    # BSD variations
    "BSD License": "BSD-3-Clause",
    "BSD": "BSD-3-Clause",
    "BSD-3": "BSD-3-Clause",
    "BSD 3-Clause": "BSD-3-Clause",
    "BSD 3-Clause License": "BSD-3-Clause",
    "BSD 3 Clause": "BSD-3-Clause",
    "3-Clause BSD License": "BSD-3-Clause",
    "New BSD License": "BSD-3-Clause",
    "Modified BSD License": "BSD-3-Clause",
    "BSD-2": "BSD-2-Clause",
    "BSD 2-Clause": "BSD-2-Clause",
    "BSD 2-Clause License": "BSD-2-Clause",
    "BSD 2 Clause": "BSD-2-Clause",
    "Simplified BSD License": "BSD-2-Clause",
    "FreeBSD License": "BSD-2-Clause",
    # Apache variations
    "Apache License": "Apache-2.0",
    "Apache License 2.0": "Apache-2.0",
    "Apache License, Version 2.0": "Apache-2.0",
    "Apache Software License": "Apache-2.0",
    "Apache 2.0": "Apache-2.0",
    "Apache-2": "Apache-2.0",
    "Apache 2": "Apache-2.0",
    "ASL 2.0": "Apache-2.0",
    # GPL variations
    "GNU General Public License": "GPL-3.0-only",
    "GNU General Public License v3": "GPL-3.0-only",
    "GNU General Public License v3.0": "GPL-3.0-only",
    "GPL": "GPL-3.0-only",
    "GPL-3": "GPL-3.0-only",
    "GPL-3.0": "GPL-3.0-only",
    "GPL v3": "GPL-3.0-only",
    "GPLv3": "GPL-3.0-only",
    "GPL3": "GPL-3.0-only",
    "GNU General Public License v2": "GPL-2.0-only",
    "GNU General Public License v2.0": "GPL-2.0-only",
    "GPL-2": "GPL-2.0-only",
    "GPL-2.0": "GPL-2.0-only",
    "GPL v2": "GPL-2.0-only",
    "GPLv2": "GPL-2.0-only",
    "GPL2": "GPL-2.0-only",
    # LGPL variations
    "GNU Lesser General Public License": "LGPL-3.0-only",
    "LGPL": "LGPL-3.0-only",
    "LGPL-3": "LGPL-3.0-only",
    "LGPL-3.0": "LGPL-3.0-only",
    "LGPLv3": "LGPL-3.0-only",
    "LGPL-2.1": "LGPL-2.1-only",
    "LGPLv2.1": "LGPL-2.1-only",
    # ISC
    "ISC License": "ISC",
    "ISC license": "ISC",
    # MPL variations
    "Mozilla Public License": "MPL-2.0",
    "Mozilla Public License 2.0": "MPL-2.0",
    "MPL": "MPL-2.0",
    "MPL 2.0": "MPL-2.0",
    # Python Software Foundation
    "Python Software Foundation License": "PSF-2.0",
    "PSF": "PSF-2.0",
    "PSF License": "PSF-2.0",
    # Unlicense
    "The Unlicense": "Unlicense",
    "Public Domain": "Unlicense",
    # CC0
    "CC0 1.0": "CC0-1.0",
    "CC0": "CC0-1.0",
    "CC0 1.0 Universal": "CC0-1.0",
    # Artistic
    "Artistic License": "Artistic-2.0",
    "Artistic-2": "Artistic-2.0",
    "Perl Artistic License": "Artistic-2.0",
    # WTFPL
    "WTFPL": "WTFPL",
    "Do What The F*ck You Want To Public License": "WTFPL",
    # Zlib
    "zlib License": "Zlib",
    "zlib": "Zlib",
    # Eclipse
    "Eclipse Public License": "EPL-1.0",
    "Eclipse Public License 1.0": "EPL-1.0",
    "EPL": "EPL-1.0",
    "Eclipse Public License 2.0": "EPL-2.0",
    "EPL-2": "EPL-2.0",
}


def normalize_license_name(license_name: str | None) -> str | None:
    """
    Normalize license name to SPDX ID format.

    Args:
        license_name: License name to normalize (may be None)

    Returns:
        Normalized SPDX ID or original name if no mapping found.
        Returns None if input is None.

    Examples:
        >>> normalize_license_name("MIT License")
        'MIT'
        >>> normalize_license_name("BSD 3-Clause License")
        'BSD-3-Clause'
        >>> normalize_license_name("Apache-2.0")
        'Apache-2.0'
        >>> normalize_license_name(None)
        None
    """
    if license_name is None:
        return None

    # Strip whitespace
    license_name = license_name.strip()

    # If already in SPDX format, return as-is
    if license_name in LICENSE_NORMALIZATION_MAP.values():
        return license_name

    # Try exact match first
    if license_name in LICENSE_NORMALIZATION_MAP:
        return LICENSE_NORMALIZATION_MAP[license_name]

    # Try case-insensitive match
    license_lower = license_name.lower()
    for key, value in LICENSE_NORMALIZATION_MAP.items():
        if key.lower() == license_lower:
            return value

    # No match found, return original
    return license_name
