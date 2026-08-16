"""Domain guardrails: keep the agribusiness assistant on-topic while being permissive."""

import difflib

AGRICULTURE_KEYWORDS = {
    # Crops
    "crop", "coffee", "maize", "banana", "bean", "cassava", "vanilla", "tea", "rice",
    "millet", "sorghum", "groundnut", "soybean", "sesame", "sunflower", "wheat",
    "sweet potato", "irish potato", "simsim", "matooke", "plantain", "cocoyam",
    "corn", "posho", "simb", "wolimawo",
    # Livestock
    "chicken", "poultry", "goat", "cattle", "cow", "sheep", "pig", "rabbit",
    "duck", "fish", "livestock", "animal", "egg", "hen", "cock", "dairy", "beef",
    "nkoko", "farming",
    # Actions
    "plant", "grow", "sow", "harvest", "prune", "weed", "irrigate", "fertilize",
    "spray", "plough", "till", "mulch", "thin", "transplant", "cure", "dry",
    "store", "feed", "vaccinate", "deworm", "castrate", "breed", "milk",
    # Science / inputs
    "soil", "seed", "compost", "manure", "pesticide", "fungicide", "herbicide",
    "fertilizer", "nutrient", "ph", "drainage", "rotation", "intercrop",
    "npk", "can", "dap", "urea",
    # Disease / pests
    "rust", "blight", "wilt", "mosaic", "spots", "yellowing", "wilting", "pest",
    "insect", "aphid", "beetle", "worm", "caterpillar", "locust", "nematode",
    "fungus", "bacterial", "disease", "infestation", "fall armyworm",
    # Market / economy
    "price", "market", "sell", "buy", "cost", "money", "worth", "cooperative",
    "middleman", "export", "import", "profit", "revenue", "income", "trade",
    "vendor", "shop", "dealer", "agro-dealer", "naads",
    # Weather / environment
    "rain", "rainfall", "weather", "season", "drought", "flood", "dry", "wet",
    "temperature", "climate", "sunshine", "wind", "cloudy",
    # Infrastructure
    "farm", "farmer", "field", "garden", "village", "extension",
    "nursery", "storage", "silo", "granary",
    # Luganda / local words
    "kawa", "kafifi", "cafe", "banna", "banas", "muhogo", "njugu",
    "nkwology", "lentil", "cowp",
}

BLOCKED_TOPICS = {
    "politics", "election", "elections", "vote", "voting", "religion", "war",
    "weapons", "gambling", "crypto trading", "drugs", "alcohol abuse",
}

GREETING_WORDS = {
    "hello", "hi", "hey", "good morning", "good evening", "good afternoon",
    "namaste", "jambo", "webale", "nno", "olunaku", "muno", "nambye",
    "how are you", "what's up", "sup",
}

DEFAULT_RESPONSE = (
    "I'm NOVA, your farming assistant. I can help with crops, livestock, "
    "soil, weather, market prices, and pest control. What would you like to know?"
)


def has_blocked_topic(text: str) -> bool:
    lowered = text.lower()
    return any(topic in lowered for topic in BLOCKED_TOPICS)


def has_greeting(text: str) -> bool:
    lowered = text.lower()
    return any(g in lowered for g in GREETING_WORDS)


def is_agri_query(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in AGRICULTURE_KEYWORDS)


def has_fuzzy_agri_match(text: str) -> bool:
    words = text.lower().split()
    for word in words:
        if len(word) < 4:
            continue
        matches = difflib.get_close_matches(word, AGRICULTURE_KEYWORDS, n=1, cutoff=0.75)
        if matches:
            return True
    return False


def guard_query(text: str) -> tuple[bool, str]:
    if has_blocked_topic(text):
        return False, "I can only help with farming questions — crops, livestock, weather, market prices, and soil management."
    if has_greeting(text):
        return True, ""
    if is_agri_query(text):
        return True, ""
    if has_fuzzy_agri_match(text):
        return True, ""
    return True, ""
