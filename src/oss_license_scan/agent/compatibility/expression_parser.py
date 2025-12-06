"""SPDX license expression parser."""

from itertools import product
from typing import Any

from license_expression import ExpressionError, get_spdx_licensing


def parse_spdx_expression(expression: str) -> list[list[str]]:
    """
    Parse SPDX license expression into license combinations.

    This function handles:
    - Simple licenses: "MIT" → [["MIT"]]
    - OR expressions: "MIT OR Apache-2.0" → [["MIT"], ["Apache-2.0"]]
    - AND expressions: "MIT AND Apache-2.0" → [["MIT", "Apache-2.0"]]
    - Complex expressions: "(MIT OR Apache-2.0) AND BSD-3-Clause" →
      [["MIT", "BSD-3-Clause"], ["Apache-2.0", "BSD-3-Clause"]]
    - WITH operator: "GPL-2.0-only WITH Classpath-exception-2.0" →
      [["GPL-2.0-only WITH Classpath-exception-2.0"]]

    Args:
        expression: SPDX license expression string

    Returns:
        list[list[str]]: List of license combinations.
        Each combination is a list of licenses that must all be satisfied.
        Multiple combinations represent alternatives (OR).

    Examples:
        >>> parse_spdx_expression("MIT")
        [["MIT"]]
        >>> parse_spdx_expression("MIT OR Apache-2.0")
        [["MIT"], ["Apache-2.0"]]
        >>> parse_spdx_expression("MIT AND Apache-2.0")
        [["MIT", "Apache-2.0"]]
    """
    # Handle empty or whitespace
    if not expression or not expression.strip():
        return []

    # Get SPDX licensing parser
    licensing = get_spdx_licensing()

    try:
        # Parse the expression
        parsed = licensing.parse(expression.strip())

        # Convert to combinations
        combinations = _expression_to_combinations(parsed)

        return combinations

    except ExpressionError:
        # If parsing fails, treat as single license
        return [[expression.strip()]]


def _expression_to_combinations(expr: Any) -> list[list[str]]:
    """
    Convert a parsed license expression to combinations.

    Args:
        expr: Parsed expression object from license-expression library

    Returns:
        list[list[str]]: List of license combinations
    """
    # Base case: LicenseSymbol or LicenseWithExceptionSymbol
    if hasattr(expr, "key"):
        # Single license
        return [[str(expr)]]

    # OR expression - creates alternatives
    if hasattr(expr, "operator") and expr.operator.strip() == "OR":
        # OR can have multiple arguments (n-ary operator)
        all_combos = []
        for arg in expr.args:
            combos = _expression_to_combinations(arg)
            all_combos.extend(combos)
        return all_combos

    # AND expression - creates requirements
    if hasattr(expr, "operator") and expr.operator.strip() == "AND":
        # AND can have multiple arguments (n-ary operator)
        # Get combinations for each argument
        all_arg_combos = []
        for arg in expr.args:
            combos = _expression_to_combinations(arg)
            all_arg_combos.append(combos)

        # Compute Cartesian product of all combinations
        result = []
        for combo_tuple in product(*all_arg_combos):
            # Flatten the tuple of combinations into a single list
            combined = []
            for combo in combo_tuple:
                combined.extend(combo)
            result.append(combined)

        return result

    # WITH operator - treated as single license
    if hasattr(expr, "operator") and expr.operator.strip() == "WITH":
        # Keep as single license string
        return [[str(expr)]]

    # Fallback: convert to string
    return [[str(expr)]]
