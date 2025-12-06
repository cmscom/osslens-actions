"""Environment variable validation utilities."""

import logging
import os
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T", int, float, bool, str)


class EnvValidationError(Exception):
    """Exception raised when environment variable validation fails."""

    def __init__(self, var_name: str, value: str, expected_type: str, message: str | None = None):
        self.var_name = var_name
        self.value = value
        self.expected_type = expected_type
        self.message = (
            message or f"Invalid value for {var_name}: '{value}' is not a valid {expected_type}"
        )
        super().__init__(self.message)


def parse_int_env(
    var_name: str,
    default: int,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    """
    Parse an integer environment variable with validation.

    Args:
        var_name: Environment variable name
        default: Default value if not set or invalid
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)

    Returns:
        Parsed integer value or default

    Logs a warning if the value is invalid and falls back to default.
    """
    value_str = os.getenv(var_name)
    if value_str is None or value_str.strip() == "":
        return default

    try:
        value = int(value_str)
    except ValueError:
        logger.warning(
            f"Invalid integer value for {var_name}: '{value_str}'. Using default: {default}"
        )
        return default

    if min_value is not None and value < min_value:
        logger.warning(
            f"{var_name}={value} is below minimum ({min_value}). Using minimum: {min_value}"
        )
        return min_value

    if max_value is not None and value > max_value:
        logger.warning(
            f"{var_name}={value} is above maximum ({max_value}). Using maximum: {max_value}"
        )
        return max_value

    return value


def parse_float_env(
    var_name: str,
    default: float,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    """
    Parse a float environment variable with validation.

    Args:
        var_name: Environment variable name
        default: Default value if not set or invalid
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)

    Returns:
        Parsed float value or default

    Logs a warning if the value is invalid and falls back to default.
    """
    value_str = os.getenv(var_name)
    if value_str is None or value_str.strip() == "":
        return default

    try:
        value = float(value_str)
    except ValueError:
        logger.warning(
            f"Invalid float value for {var_name}: '{value_str}'. Using default: {default}"
        )
        return default

    if min_value is not None and value < min_value:
        logger.warning(
            f"{var_name}={value} is below minimum ({min_value}). Using minimum: {min_value}"
        )
        return min_value

    if max_value is not None and value > max_value:
        logger.warning(
            f"{var_name}={value} is above maximum ({max_value}). Using maximum: {max_value}"
        )
        return max_value

    return value


def parse_bool_env(var_name: str, default: bool) -> bool:
    """
    Parse a boolean environment variable with validation.

    Args:
        var_name: Environment variable name
        default: Default value if not set or invalid

    Returns:
        Parsed boolean value or default

    Recognizes: "true", "1" as True (case-insensitive)
                "false", "0" as False (case-insensitive)
    Other values will log a warning and return the default.
    """
    value_str = os.getenv(var_name)
    if value_str is None or value_str.strip() == "":
        return default

    value_lower = value_str.strip().lower()

    if value_lower in ("true", "1"):
        return True
    elif value_lower in ("false", "0"):
        return False
    else:
        logger.warning(
            f"Invalid boolean value for {var_name}: '{value_str}'. "
            f"Expected 'true', 'false', '1', or '0'. Using default: {default}"
        )
        return default


def parse_str_env(
    var_name: str,
    default: str | None = None,
    allowed_values: list[str] | None = None,
) -> str | None:
    """
    Parse a string environment variable with optional validation.

    Args:
        var_name: Environment variable name
        default: Default value if not set
        allowed_values: List of allowed values (optional)

    Returns:
        Parsed string value or default

    Logs a warning if the value is not in allowed_values and falls back to default.
    """
    value_str = os.getenv(var_name)
    if value_str is None or value_str.strip() == "":
        return default

    value = value_str.strip()

    if allowed_values is not None and value not in allowed_values:
        logger.warning(
            f"Invalid value for {var_name}: '{value}'. "
            f"Allowed values: {allowed_values}. Using default: {default}"
        )
        return default

    return value


def parse_optional_int_env(
    var_name: str,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int | None:
    """
    Parse an optional integer environment variable with validation.

    Args:
        var_name: Environment variable name
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)

    Returns:
        Parsed integer value or None if not set or invalid
    """
    value_str = os.getenv(var_name)
    if value_str is None or value_str.strip() == "":
        return None

    try:
        value = int(value_str)
    except ValueError:
        logger.warning(f"Invalid integer value for {var_name}: '{value_str}'. Ignoring.")
        return None

    if min_value is not None and value < min_value:
        logger.warning(
            f"{var_name}={value} is below minimum ({min_value}). Using minimum: {min_value}"
        )
        return min_value

    if max_value is not None and value > max_value:
        logger.warning(
            f"{var_name}={value} is above maximum ({max_value}). Using maximum: {max_value}"
        )
        return max_value

    return value
