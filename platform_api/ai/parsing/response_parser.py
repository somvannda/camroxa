"""Provider-agnostic parsing for LLM text responses."""

from __future__ import annotations

import ast
import json
import re
from typing import Any


def clean_llm_text(content: str) -> str:
    """Strip markdown fences and surrounding whitespace from LLM output."""
    text = str(content or "").strip()
    if not text:
        return ""

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return re.sub(r"```\w*\s*", "", text).strip()


def parse_json_value(content: str) -> Any | None:
    """Best-effort parse of JSON or Python-literal content from LLM text."""
    text = clean_llm_text(content)
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start >= 0 and end > start:
            fragment = text[start : end + 1]
            try:
                return json.loads(fragment)
            except json.JSONDecodeError:
                try:
                    return ast.literal_eval(fragment)
                except (ValueError, SyntaxError):
                    if opener == "{":
                        try:
                            return json.loads(fragment.replace("'", '"'))
                        except json.JSONDecodeError:
                            pass
    return None


def parse_json_object(content: str) -> dict[str, Any] | None:
    """Parse a JSON object from LLM text."""
    parsed = parse_json_value(content)
    return parsed if isinstance(parsed, dict) else None


def parse_json_array(content: str) -> list[Any] | None:
    """Parse a JSON array from LLM text."""
    parsed = parse_json_value(content)
    return parsed if isinstance(parsed, list) else None


def parse_string_list(content: str) -> list[str]:
    """Parse a list of strings from JSON array/object or plain lines."""
    parsed_array = parse_json_array(content)
    if parsed_array is not None:
        return [str(item).strip() for item in parsed_array if str(item).strip()]

    parsed_object = parse_json_object(content)
    if parsed_object is not None:
        for key in ("keywords", "tags", "names", "items", "results"):
            value = parsed_object.get(key)
            if isinstance(value, list):
                return [str(item).strip() for item in value if str(item).strip()]

    names: list[str] = []
    for line in clean_llm_text(content).splitlines():
        cleaned = line.strip().strip("[],\"' \t")
        if cleaned:
            names.append(cleaned)
    return names


def _unescape_json_string(value: str) -> str:
    text = str(value or "")
    try:
        return json.loads(f'"{text}"')
    except json.JSONDecodeError:
        return (
            text.replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )


def _strip_wrapping_quotes(text: str) -> str:
    result = text.strip()
    while len(result) >= 2 and result[0] == result[-1] and result[0] in ('"', "'"):
        result = result[1:-1].strip()
    return result.strip('"\'').strip()


def _extract_json_field_value(text: str, field_name: str) -> str | None:
    pattern = rf'["\']?{re.escape(field_name)}["\']?\s*:\s*"(?P<value>(?:[^"\\]|\\.)*)"'
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    return _unescape_json_string(match.group("value")).strip()


def normalize_slot_text(content: str, *field_names: str) -> str:
    """Reduce LLM slot output to plain text without JSON key/value artifacts."""
    text = clean_llm_text(content)
    if not text:
        return ""

    names = field_names or ("value",)
    value = ""

    parsed = parse_json_object(text)
    if parsed is not None:
        lowered = {str(key).lower(): item for key, item in parsed.items()}
        for name in names:
            raw = lowered.get(name.lower())
            if raw is not None and str(raw).strip():
                value = str(raw).strip()
                break
        if not value and len(parsed) == 1:
            only = next(iter(parsed.values()))
            if isinstance(only, (str, int, float)):
                value = str(only).strip()

    if not value:
        for name in names:
            extracted = _extract_json_field_value(text, name)
            if extracted:
                value = extracted
                break

    if not value:
        value = text

    value = _strip_wrapping_quotes(value)
    for name in names:
        value = re.sub(
            rf'^[\s\n]*["\']?{re.escape(name)}["\']?\s*:\s*',
            "",
            value,
            count=1,
            flags=re.IGNORECASE,
        ).strip()
    return _strip_wrapping_quotes(value).strip()


def parse_string_field(content: str, *field_names: str) -> str:
    """Extract a string field from JSON or return cleaned plain text."""
    if field_names:
        return normalize_slot_text(content, *field_names)
    return clean_llm_text(content)


def extract_chat_content(response: dict[str, Any]) -> str:
    """Read assistant message content from an OpenAI-style chat response."""
    choices = response.get("choices", [])
    if not choices:
        return ""

    message = choices[0].get("message", {})
    if not isinstance(message, dict):
        return ""

    content = str(message.get("content") or "").strip()
    if content:
        return content

    for key in ("text", "output", "response"):
        alt = message.get(key)
        if isinstance(alt, str) and alt.strip():
            return alt.strip()

    return ""
