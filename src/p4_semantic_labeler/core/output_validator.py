"""NFC + code-point counting; avoid splitting words and common emoji clusters."""

from __future__ import annotations

import unicodedata

from p4_semantic_labeler.core.errors import ProviderFailure


def normalize_label(text: str) -> str:
    if not isinstance(text, str):
        raise ProviderFailure("provider returned non-text")
    # One-line, bounded, no code fences or quote wrapping.
    cleaned = " ".join(unicodedata.normalize("NFC", text).split()).strip(" `\"'\t")
    if not cleaned:
        raise ProviderFailure("provider returned empty text")
    return cleaned


def _unsafe_split(text: str, position: int) -> bool:
    if position >= len(text):
        return False
    next_ch = text[position]
    prev_ch = text[position - 1]
    return (
        bool(unicodedata.combining(next_ch))
        or next_ch in "\ufe0e\ufe0f\u200d"
        or prev_ch == "\u200d"
        or 0x1F3FB <= ord(next_ch) <= 0x1F3FF
        or (0x1F1E6 <= ord(prev_ch) <= 0x1F1FF and 0x1F1E6 <= ord(next_ch) <= 0x1F1FF)
    )


def truncate_label(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    prefix = text[:max_chars]
    # Prefer whole words, provided this would retain meaningful text.
    boundary = prefix.rfind(" ")
    if boundary >= 1 and boundary >= max_chars // 2:
        prefix = prefix[:boundary]
    else:
        while prefix and _unsafe_split(text, len(prefix)):
            prefix = prefix[:-1]
    prefix = prefix.rstrip()
    if not prefix:
        raise ProviderFailure("unable to truncate output safely")
    return prefix
