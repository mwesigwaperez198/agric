"""Domain guardrails: keep the agribusiness assistant strictly on-topic."""

AGRICULTURE_KEYWORDS = {
    "crop", "coffee", "maize", "vanilla", "banana", "livestock", "cattle", "poultry",
    "soil", "fertilizer", "pest", "disease", "rust", "blight", "harvest", "seed",
    "irrigation", "yield", "market", "price", "farmer", "farm", "weather", "rainfall",
    "biosensor", "mycotoxin", "aflatoxin", "ochratoxin", "pesticide", "residue",
    "moisture", "agronomy", "manure", "compost", "organic", "plough", "tilling",
}

BLOCKED_TOPICS = {
    "politics", "elections", "religion", "war", "weapons", "gambling",
    "crypto trading", "drugs", "alcohol abuse",
}

DEFAULT_RESPONSE = (
    "This assistant only answers questions about farming, coffee, livestock, "
    "and agri-food safety. Please ask about crops, disease, weather, or market prices."
)


def is_agri_query(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in AGRICULTURE_KEYWORDS)


def has_blocked_topic(text: str) -> bool:
    lowered = text.lower()
    return any(topic in lowered for topic in BLOCKED_TOPICS)


def guard_query(text: str) -> tuple[bool, str]:
    """Returns (passed, reason_or_response)."""
    if has_blocked_topic(text):
        return False, DEFAULT_RESPONSE
    if not is_agri_query(text):
        return False, DEFAULT_RESPONSE
    return True, ""
