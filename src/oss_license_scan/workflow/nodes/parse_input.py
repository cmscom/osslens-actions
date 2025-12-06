"""parse_input node: 入力ファイルを解析して依存関係を抽出"""

import logging
from pathlib import Path
from typing import Any

from oss_license_scan.detection.format_detector import FormatDetector
from oss_license_scan.models import LockFileFormat
from oss_license_scan.parsers import ParseError, ParserRegistry
from oss_license_scan.parsers.requirements_parser import parse_requirements_file
from oss_license_scan.utils.security import SecurityValidationError, validate_file_size
from oss_license_scan.workflow.messages import MessageTemplates
from oss_license_scan.workflow.state import LicenseScanState

logger = logging.getLogger(__name__)

# Format detector instance
_format_detector = FormatDetector()


def parse_input_node(state: LicenseScanState) -> dict[str, Any]:
    """
    入力ファイルをパースして依存関係を抽出する。

    Args:
        state: 現在のワークフロー状態

    Returns:
        dict: 更新する状態フィールド (dependencies, warnings, errors)
    """
    logger.info(MessageTemplates.NODE_START.format(node_name="parse_input"))

    input_file = state.get("input_file")
    if not input_file:
        return {"errors": ["Input file not specified"], "dependencies": []}

    file_path = Path(input_file)
    project_type = state.get("project_type")

    # Validate file size to prevent DoS attacks from large files
    try:
        validate_file_size(str(file_path))
    except FileNotFoundError:
        # Let the main try block handle file not found
        pass
    except SecurityValidationError as e:
        error_msg = f"File validation failed: {e.message}"
        logger.error(error_msg)
        return {"errors": [error_msg], "dependencies": []}

    try:
        # Detect format
        detection_result = _format_detector.detect(
            file_path.name,
            explicit_format=project_type,
        )

        if detection_result.format is None:
            error_msg = (
                f"Unable to detect file format for {file_path.name}. Use --format to specify."
            )
            logger.error(error_msg)
            return {"errors": [error_msg], "dependencies": []}

        logger.info(
            f"Detected format: {detection_result.format.value} (method: {detection_result.method})"
        )

        # Use new parser for supported formats
        if detection_result.format in ParserRegistry.all_formats():
            parser = ParserRegistry.get(detection_result.format)
            result = parser.parse_file(file_path)

            logger.info(MessageTemplates.PARSE_INPUT_SUCCESS.format(count=len(result.dependencies)))

            return {
                "dependencies": result.dependencies,
                "warnings": result.warnings,
                "detected_format": detection_result.format.value,
            }

        # Fall back to legacy parser for requirements.txt and pyproject.toml
        if detection_result.format in (
            LockFileFormat.REQUIREMENTS_TXT,
            LockFileFormat.PYPROJECT_TOML,
        ):
            dependencies = parse_requirements_file(file_path)
            logger.info(MessageTemplates.PARSE_INPUT_SUCCESS.format(count=len(dependencies)))
            return {
                "dependencies": dependencies,
                "detected_format": detection_result.format.value,
            }

        # Should not reach here if all formats are handled
        error_msg = f"No parser available for format: {detection_result.format}"
        logger.error(error_msg)
        return {"errors": [error_msg], "dependencies": []}

    except FileNotFoundError as e:
        error_msg = f"Input file not found: {input_file}"
        logger.error(MessageTemplates.PARSE_INPUT_ERROR.format(error=str(e)))
        return {"errors": [error_msg], "dependencies": []}

    except ParseError as e:
        error_msg = f"Failed to parse {file_path.name}: {e}"
        logger.error(MessageTemplates.PARSE_INPUT_ERROR.format(error=str(e)))
        return {"errors": [error_msg], "dependencies": []}

    except ValueError as e:
        error_msg = f"Invalid format specification: {e}"
        logger.error(MessageTemplates.PARSE_INPUT_ERROR.format(error=str(e)))
        return {"errors": [error_msg], "dependencies": []}

    except Exception as e:
        error_msg = f"Failed to parse input file: {str(e)}"
        logger.error(MessageTemplates.PARSE_INPUT_ERROR.format(error=str(e)))
        return {"errors": [error_msg], "dependencies": []}
