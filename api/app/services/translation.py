"""Localized translation service with a bundled fallback dictionary.

Works fully offline for core UI terms and common agri phrases, so layouts
function before any dynamic cloud translation API is wired up.
"""

from api.app.mocks.translations import FALLBACK_DICTIONARY, SUPPORTED_DIALECTS

DIALECTS = SUPPORTED_DIALECTS


def translate(text: str, dialect: str = "en") -> str:
    if dialect in ("en", "") or dialect not in DIALECTS:
        return text
    table = FALLBACK_DICTIONARY.get(dialect, {})
    # Exact-match first, then token-level replacement to handle inflected strings.
    if text.strip() in table:
        return table[text.strip()]
    tokens = str(text).split()
    translated = [table.get(token, token) for token in tokens]
    return " ".join(translated)


def translate_pairs(dialect: str) -> dict[str, str]:
    return FALLBACK_DICTIONARY.get(dialect, {})
