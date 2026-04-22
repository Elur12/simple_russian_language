"""
Yandex AI Studio adapter using the OpenAI-compatible API.

Yandex exposes an OpenAI-compatible endpoint at:
  https://ai.api.cloud.yandex.net/v1

This lets us use the official openai Python SDK instead of hand-rolling
HTTP requests, and gives us proper JSON-mode support.

Model URI format (same for both APIs):
  gpt://<folder_id>/<model_name>/<version>
  e.g. gpt://b1gol8hv57f7puju1obf/gpt-oss-120b/latest
"""

import json
import logging
from typing import Dict, Any

from openai import OpenAI, APIStatusError, APIConnectionError, APITimeoutError

from .prompts import build_full_prompt, build_window_prompt

logger = logging.getLogger(__name__)

YANDEX_OPENAI_BASE_URL = "https://ai.api.cloud.yandex.net/v1"


class YandexAIError(Exception):
    pass


class YandexAITokenError(YandexAIError):
    pass


class YandexAIResponseError(YandexAIError):
    pass


def _folder_id_from_model_uri(model: str) -> str:
    """Extract folder ID from 'gpt://<folder>/<model>/<version>'."""
    try:
        return model.split("://", 1)[1].split("/")[0]
    except (IndexError, AttributeError):
        return ""


class YandexAIAnalyzer:
    DEFAULT_MODEL = "gpt://b1gol8hv57f7puju1obf/yandexgpt-lite/latest"
    DEFAULT_TEMPERATURE = 0.1
    MAX_TOKENS = 4096
    REQUEST_TIMEOUT = 60
    MAX_RETRIES = 3

    def __init__(self, api_token: str, model: str = DEFAULT_MODEL):
        if not api_token or not api_token.strip():
            raise YandexAITokenError("API token is required and cannot be empty")
        if not model or not model.strip():
            raise YandexAIError("Model is required and cannot be empty")
        if not model.startswith("gpt://"):
            raise YandexAIError(
                "YANDEX_MODEL must be a full URI, e.g. gpt://<folder_id>/gpt-oss-120b/latest"
            )

        self.model = model.strip()
        folder_id = _folder_id_from_model_uri(self.model)

        self._client = OpenAI(
            api_key=api_token,
            base_url=YANDEX_OPENAI_BASE_URL,
            # folder_id is passed as the project header (x-yandex-folder-id)
            project=folder_id or None,
            max_retries=self.MAX_RETRIES,
            timeout=self.REQUEST_TIMEOUT,
        )

    def _call(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompts to the model and return the raw text response."""
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                temperature=self.DEFAULT_TEMPERATURE,
                max_tokens=self.MAX_TOKENS,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content or ""
        except APIStatusError as e:
            if e.status_code == 401:
                raise YandexAITokenError("Invalid API token (401 Unauthorized)")
            if e.status_code == 403:
                raise YandexAITokenError("Access forbidden (403 Forbidden)")
            raise YandexAIError(f"API error {e.status_code}: {e.message}") from e
        except APIConnectionError as e:
            raise YandexAIError(f"Connection error: {e}") from e
        except APITimeoutError as e:
            raise YandexAIError("Request timeout") from e

    def analyze_text(self, text: str, mode: str = "paragraph") -> Dict[str, Any]:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        system_prompt, user_prompt = build_full_prompt(text, mode)
        return self._parse_response(self._call(system_prompt, user_prompt))

    def analyze_paragraph_with_context(
        self,
        current_paragraph: str,
        current_index: int,
        total_paragraphs: int,
        prev_paragraph: str = "",
        next_paragraph: str = "",
    ) -> Dict[str, Any]:
        if not current_paragraph or not current_paragraph.strip():
            raise ValueError("Current paragraph cannot be empty")
        system_prompt, user_prompt = build_window_prompt(
            current_paragraph=current_paragraph,
            current_index=current_index,
            total_paragraphs=total_paragraphs,
            prev_paragraph=prev_paragraph,
            next_paragraph=next_paragraph,
        )
        return self._parse_response(self._call(system_prompt, user_prompt))

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:].rsplit("```", 1)[0]
        elif response_text.startswith("```"):
            response_text = response_text[3:].rsplit("```", 1)[0]
        response_text = response_text.strip()

        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error("JSON parse error: %s\nResponse: %.500s", e, response_text)
            raise YandexAIResponseError(f"Invalid JSON in response: {e}") from e

        if not isinstance(result, dict):
            raise YandexAIResponseError("Response root must be a dict")
        if "items" not in result or not isinstance(result["items"], list):
            raise YandexAIResponseError("Response must contain 'items' list")

        result["items"] = self._normalize_items(result["items"])
        return result

    def _normalize_items(self, items: list) -> list:
        allowed_severity = {"green", "orange", "red"}
        normalized = []

        for i, raw_item in enumerate(items):
            if isinstance(raw_item, str):
                raw_item = {
                    "unit_index": i,
                    "source_text": raw_item,
                    "severity": "orange",
                    "violations": [],
                    "overall_comment": "Получен неполный формат ответа модели.",
                }
            elif not isinstance(raw_item, dict):
                logger.warning("Skipping malformed item %s of type %s", i, type(raw_item).__name__)
                continue

            severity = raw_item.get("severity", "orange")
            if severity not in allowed_severity:
                severity = "orange"

            raw_violations = raw_item.get("violations", [])
            if not isinstance(raw_violations, list):
                raw_violations = []

            violations = []
            for v in raw_violations:
                if not isinstance(v, dict):
                    continue
                v_severity = v.get("severity", "orange")
                if v_severity not in allowed_severity:
                    v_severity = "orange"
                violations.append({
                    "rule_id": str(v.get("rule_id", "R1")),
                    "rule_name": str(v.get("rule_name", "")),
                    "severity": v_severity,
                    "problematic_text": str(v.get("problematic_text", "")).strip(),
                    "comment": str(v.get("comment", "")),
                    "suggested_rewrite": str(v.get("suggested_rewrite", "")).strip(),
                })

            unit_index = raw_item.get("unit_index", i)
            if not isinstance(unit_index, int):
                unit_index = i

            normalized.append({
                "unit_index": unit_index,
                "unit_type": raw_item.get("unit_type", "paragraph"),
                "source_text": str(raw_item.get("source_text", "")),
                "severity": severity,
                "violations": violations,
                "overall_comment": str(raw_item.get("overall_comment", raw_item.get("comment", ""))),
                "paragraph_rewrite": str(raw_item.get("paragraph_rewrite", "")).strip(),
                "sentence_findings": raw_item.get("sentence_findings", []),
            })

        return normalized

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
