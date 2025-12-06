"""Security utilities for input validation and secret masking."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Maximum file size for dependency files (10MB)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Pattern for valid package names (alphanumeric, hyphens, underscores, dots)
VALID_PACKAGE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$|^[a-zA-Z0-9]$")

# Pattern for valid GitHub repo format (owner/repo)
VALID_GITHUB_REPO_PATTERN = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?/[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$"
)

# Dangerous path traversal patterns
PATH_TRAVERSAL_PATTERNS = [
    "..",
    "./",
    "//",
    "%2e%2e",
    "%2f",
    "\\",
]


class SecurityValidationError(Exception):
    """Exception raised when security validation fails."""

    def __init__(self, message: str, field: str | None = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


def mask_secret(secret: str | None, visible_chars: int = 4) -> str:
    """Mask a secret value for safe logging.

    Args:
        secret: The secret value to mask
        visible_chars: Number of characters to show at the end

    Returns:
        Masked string like "***abc1" or "[EMPTY]" if None/empty
    """
    if not secret:
        return "[EMPTY]"

    if len(secret) <= visible_chars:
        return "*" * len(secret)

    return "*" * (len(secret) - visible_chars) + secret[-visible_chars:]


def validate_github_repo(repo: str) -> bool:
    """Validate GitHub repository format and check for path traversal.

    Args:
        repo: Repository in "owner/repo" format

    Returns:
        True if valid, False otherwise

    Raises:
        SecurityValidationError: If path traversal attempt detected
    """
    if not repo:
        return False

    # Check for path traversal attempts
    repo_lower = repo.lower()
    for pattern in PATH_TRAVERSAL_PATTERNS:
        if pattern in repo_lower:
            logger.warning(
                f"Path traversal attempt detected in github_repo: {mask_secret(repo, 8)}"
            )
            raise SecurityValidationError(
                "Invalid github_repo: path traversal pattern detected",
                field="github_repo",
            )

    # Validate format
    if not VALID_GITHUB_REPO_PATTERN.match(repo):
        logger.debug(f"Invalid github_repo format: {mask_secret(repo, 8)}")
        return False

    return True


def validate_package_name(name: str) -> bool:
    """Validate package name format.

    Args:
        name: Package name to validate

    Returns:
        True if valid, False otherwise
    """
    if not name:
        return False

    # Check length limits
    if len(name) > 256:
        logger.warning(f"Package name too long: {len(name)} characters")
        return False

    # Check for path traversal
    name_lower = name.lower()
    for pattern in PATH_TRAVERSAL_PATTERNS:
        if pattern in name_lower:
            logger.warning(f"Path traversal attempt in package name: {mask_secret(name, 8)}")
            return False

    # Validate format (allow scoped packages like @scope/name)
    if name.startswith("@"):
        # Scoped package: @scope/name
        parts = name[1:].split("/", 1)
        if len(parts) != 2:
            return False
        scope, pkg_name = parts
        return bool(
            VALID_PACKAGE_NAME_PATTERN.match(scope) and VALID_PACKAGE_NAME_PATTERN.match(pkg_name)
        )

    return bool(VALID_PACKAGE_NAME_PATTERN.match(name))


def escape_like_pattern(value: str) -> str:
    """Escape special characters for SQL LIKE queries.

    Args:
        value: The value to escape

    Returns:
        Escaped value safe for LIKE queries
    """
    # Escape SQL LIKE special characters: %, _, [
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace("%", "\\%")
    escaped = escaped.replace("_", "\\_")
    escaped = escaped.replace("[", "\\[")
    return escaped


def validate_file_size(file_path: str, max_size: int = MAX_FILE_SIZE_BYTES) -> bool:
    """Validate file size is within limits.

    Args:
        file_path: Path to the file
        max_size: Maximum allowed size in bytes

    Returns:
        True if file size is within limits

    Raises:
        SecurityValidationError: If file is too large
        FileNotFoundError: If file does not exist (re-raised for upstream handling)
    """
    import os

    try:
        file_size = os.path.getsize(file_path)
        if file_size > max_size:
            logger.warning(
                f"File size {file_size} bytes exceeds limit {max_size} bytes: {file_path}"
            )
            raise SecurityValidationError(
                f"File size ({file_size} bytes) exceeds maximum allowed size ({max_size} bytes)",
                field="file_path",
            )
        return True
    except FileNotFoundError:
        # Re-raise FileNotFoundError for upstream handling
        raise
    except OSError as e:
        logger.error(f"Failed to check file size: {e}")
        raise SecurityValidationError(f"Failed to check file size: {e}", field="file_path") from e


def sanitize_log_value(value: Any, max_length: int = 100) -> str:
    """Sanitize a value for safe logging.

    Args:
        value: Value to sanitize
        max_length: Maximum length of output

    Returns:
        Sanitized string safe for logging
    """
    if value is None:
        return "[None]"

    str_value = str(value)

    # Remove potential log injection characters
    sanitized = str_value.replace("\n", "\\n").replace("\r", "\\r")

    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[: max_length - 3] + "..."

    return sanitized
