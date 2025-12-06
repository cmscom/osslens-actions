"""Custom license classifier using LLM.

This module provides functionality to classify custom/unknown licenses
into categories (permissive/copyleft/proprietary/unknown) using LLM analysis.
"""

import json
import logging
import re

from oss_license_scan.llm.provider import create_llm
from oss_license_scan.models import CustomLicenseClassification

logger = logging.getLogger(__name__)


def _strip_markdown_fences(text: str) -> str:
    """マークダウンコードフェンスを除去する。

    LLMがJSONをマークダウンコードブロックで囲んで返す場合に対応。

    Args:
        text: 処理対象のテキスト

    Returns:
        コードフェンスを除去したテキスト
    """
    # ```json ... ``` または ``` ... ``` パターンを検出
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    match = re.match(pattern, text.strip(), re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


# Classification prompt template
CLASSIFICATION_PROMPT = """Analyze the following software license text and classify it into one of these categories:
1. permissive: Allows free use, modification, and distribution with minimal restrictions (like MIT, Apache, BSD)
2. copyleft: Requires derivative works to be distributed under the same license (like GPL, AGPL)
3. proprietary: Restricts use, modification, or distribution
4. unknown: Cannot determine category from the text

License text:
```
{license_text}
```

Analyze this license and respond ONLY with a valid JSON object in this exact format:
{{
  "category": "permissive|copyleft|proprietary|unknown",
  "confidence": 0.0 to 1.0,
  "rationale": ["reason 1", "reason 2"],
  "key_terms": ["term1", "term2"],
  "risk_level": "low|medium|high|unknown"
}}

Risk level guidelines:
- low: Permissive licenses, safe for commercial use
- medium: Weak copyleft or licenses with specific conditions
- high: Strong copyleft or highly restrictive proprietary licenses
- unknown: Cannot determine risk

Respond with ONLY the JSON object, no other text."""


def classify_custom_license(license_text: str) -> CustomLicenseClassification:
    """
    Classify a custom license using LLM analysis.

    Args:
        license_text: The license text to classify

    Returns:
        CustomLicenseClassification: Classification result with category, confidence, etc.
    """
    # Truncate long license text
    max_length = 1000
    if len(license_text) > max_length:
        truncated_text = license_text[:max_length]
        logger.warning(
            f"License text truncated from {len(license_text)} to {max_length} characters"
        )
    else:
        truncated_text = license_text

    try:
        # Get LLM instance
        llm = create_llm()

        # Format prompt
        prompt = CLASSIFICATION_PROMPT.format(license_text=truncated_text)

        # Invoke LLM
        response = llm.invoke(prompt)
        response_text = (getattr(response, "content", "") or "").strip()

        # 空レスポンスのチェック
        if not response_text:
            logger.warning("LLM returned empty response for license classification")
            return CustomLicenseClassification(
                license_text=truncated_text,
                category="unknown",
                confidence=0.0,
                rationale=["LLMから空のレスポンスが返されました"],
                key_terms=[],
                risk_level="unknown",
            )

        # マークダウンコードフェンスを除去
        response_text = _strip_markdown_fences(response_text)

        # Parse JSON response
        try:
            result_data = json.loads(response_text)

            # Validate required fields
            category = result_data.get("category", "unknown")
            confidence = float(result_data.get("confidence", 0.0))
            rationale = result_data.get("rationale", [])
            key_terms = result_data.get("key_terms", [])
            risk_level = result_data.get("risk_level", "unknown")

            # Ensure types are correct
            if not isinstance(rationale, list):
                rationale = [str(rationale)]
            if not isinstance(key_terms, list):
                key_terms = [str(key_terms)]

            return CustomLicenseClassification(
                license_text=truncated_text,
                category=category,  # type: ignore
                confidence=confidence,
                rationale=rationale,
                key_terms=key_terms,
                risk_level=risk_level,  # type: ignore
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"LLM response: {response_text}")

            # Return unknown classification
            return CustomLicenseClassification(
                license_text=truncated_text,
                category="unknown",
                confidence=0.0,
                rationale=["Failed to parse LLM response"],
                key_terms=[],
                risk_level="unknown",
            )

    except Exception as e:
        logger.error(f"Error during license classification: {e}")

        # Return unknown classification on error
        return CustomLicenseClassification(
            license_text=truncated_text,
            category="unknown",
            confidence=0.0,
            rationale=[f"Classification error: {str(e)}"],
            key_terms=[],
            risk_level="unknown",
        )
