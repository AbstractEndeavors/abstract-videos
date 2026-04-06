import re
from collections import defaultdict
from typing import Iterable, Dict, List, Tuple


# You can tweak this list – it's a superset of your original categories
CATEGORIES: Dict[str, Dict[str, List[str]]] = {
    "Comedy": {
        "keywords": [
            "comedy", "funny", "humor", "satire", "sketch", "parody",
            "standup", "stand-up", "joke", "memes", "meme"
        ],
        "phrases": [
            "skit", "prank", "reaction compilation"
        ],
        "required": [],
        "negative": ["news", "serious"],
    },
    "Music": {
        "keywords": [
            "music", "song", "album", "track", "single", "mix", "remix",
            "cover", "instrumental", "lyrics", "concert", "live"
        ],
        "phrases": [
            "music video", "live performance", "lyric video"
        ],
        "required": [],
        "negative": ["podcast"],
    },
    "News & Politics": {
        "keywords": [
            "news", "politics", "politic", "breaking", "headline",
            "election", "government", "policy", "debate",
            "interview", "commentary", "analysis"
        ],
        "phrases": [
            "breaking news", "press conference", "panel discussion"
        ],
        "required": [],
        "negative": ["comedy sketch", "parody"],
    },
    "Education": {
        "keywords": [
            "education", "tutorial", "lesson", "howto", "how-to",
            "course", "guide", "lecture", "explained", "explanation",
            "walkthrough", "beginner", "advanced", "tips", "strategy"
        ],
        "phrases": [
            "how to", "step by step", "for beginners"
        ],
        "required": [],
        "negative": [],
    },
    "Gaming": {
        "keywords": [
            "game", "gaming", "esport", "esports", "playthrough",
            "walkthrough", "letsplay", "let's play",
            "multiplayer", "fps", "rpg", "mmorpg", "battle royale"
        ],
        "phrases": [
            "game review", "gameplay", "speedrun"
        ],
        "required": [],
        "negative": ["board meeting"],
    },
    "Sports": {
        "keywords": [
            "sports", "sport", "match", "tournament", "league",
            "highlights", "nba", "nfl", "mlb", "soccer", "football",
            "basketball", "tennis", "ufc", "fight", "boxing"
        ],
        "phrases": [
            "post game", "post-game", "match highlights"
        ],
        "required": [],
        "negative": [],
    },
    "Science & Technology": {
        "keywords": [
            "tech", "technology", "science", "physics", "chemistry",
            "biology", "space", "nasa", "review", "unboxing",
            "product", "ai", "artificial intelligence",
            "software", "hardware", "gadget"
        ],
        "phrases": [
            "product review", "tech review", "deep dive", "code tutorial"
        ],
        "required": [],
        "negative": [],
    },
    "Travel": {
        "keywords": [
            "travel", "journey", "trip", "tourism", "vacation",
            "itinerary", "vlog", "backpacking", "roadtrip", "road trip"
        ],
        "phrases": [
            "travel vlog", "travel guide", "city guide"
        ],
        "required": [],
        "negative": [],
    },
    "Food": {
        "keywords": [
            "food", "cook", "cooking", "recipe", "kitchen",
            "restaurant", "baking", "bake", "meal", "chef"
        ],
        "phrases": [
            "how to cook", "cook with me", "what i eat"
        ],
        "required": [],
        "negative": [],
    },
    "Film & Animation": {
        "keywords": [
            "film", "movie", "cinema", "animation", "animated",
            "short film", "trailer", "review", "screenplay"
        ],
        "phrases": [
            "movie review", "film analysis", "short animation"
        ],
        "required": [],
        "negative": [],
    },
    "Lifestyle & Vlog": {
        "keywords": [
            "vlog", "life", "lifestyle", "daily", "routine",
            "day in the life", "self care", "self-care"
        ],
        "phrases": [
            "day in my life", "morning routine", "night routine"
        ],
        "required": [],
        "negative": [],
    },
    "Podcast & Talk": {
        "keywords": [
            "podcast", "talk", "discussion", "interview", "roundtable",
            "debate", "episode", "radio", "broadcast"
        ],
        "phrases": [
            "podcast episode", "long form conversation", "long-form conversation"
        ],
        "required": [],
        "negative": [],
    },
    "Documentary & Non-fiction": {
        "keywords": [
            "documentary", "docu", "story", "biography", "true story",
            "history", "historical", "exposed", "investigation"
        ],
        "phrases": [
            "the untold story", "inside the", "rise and fall"
        ],
        "required": [],
        "negative": [],
    },
    # Fallback if nothing else matches strongly
    "Entertainment": {
        "keywords": [
            "entertainment", "show", "episode", "series"
        ],
        "phrases": [],
        "required": [],
        "negative": [],
    },
}


WORD_RE = re.compile(r"[a-z0-9']+")


def _normalize_text(*parts: str) -> Tuple[str, set]:
    """
    Join, lowercase, and tokenize the text input.
    Returns the full normalized string and a set of tokens.
    """
    combined = " ".join(p for p in parts if p).lower()
    tokens = set(WORD_RE.findall(combined))
    return combined, tokens


def _score_category(name: str, cfg: Dict[str, List[str]], text: str, tokens: set) -> float:
    """
    Simple scoring:
      +1 per keyword hit
      +2 per phrase hit
      -2 per negative hit
      +1 extra if any 'required' hit (and if present at all)
    Categories with any 'required' terms but none matched get score 0.
    """
    score = 0.0

    required = cfg.get("required", [])
    keywords = cfg.get("keywords", [])
    phrases = cfg.get("phrases", [])
    negative = cfg.get("negative", [])

    # If there are required terms and none appear, ditch category
    if required:
        if not any(req in tokens for req in required):
            return 0.0
        else:
            score += 1.0  # mild boost if requirements satisfied

    # Keyword hits
    for kw in keywords:
        if " " in kw:
            # treat as phrase
            if kw in text:
                score += 1.0
        else:
            if kw in tokens:
                score += 1.0

    # Phrase hits
    for ph in phrases:
        if ph in text:
            score += 2.0

    # Negative hits
    for neg in negative:
        if " " in neg:
            if neg in text:
                score -= 2.0
        else:
            if neg in tokens:
                score -= 2.0

    return score


def classify_category(
    keywords: Iterable[str],
    title: str = "",
    description: str = "",
    *,
    return_scores: bool = False,
    min_confidence: float = 0.5,
) -> str | Tuple[str, Dict[str, float]]:
    """
    More comprehensive heuristic category classifier.

    - Scores each category by keyword/phrase hits
    - Applies negative terms to avoid obvious mislabels
    - Picks the highest scoring category, with a minimum score threshold
    - Optionally returns the full score dict for debugging/tuning.
    """
    # Merge all textual signals
    keyword_text = " ".join(k.lower() for k in (keywords or []))
    full_text, tokens = _normalize_text(keyword_text, title, description)

    scores: Dict[str, float] = {}
    for cat_name, cfg in CATEGORIES.items():
        scores[cat_name] = _score_category(cat_name, cfg, full_text, tokens)

    # Pick best category
    best_cat = max(scores, key=scores.get)
    best_score = scores[best_cat]

    # Very weak match? Optionally force "Entertainment" as neutral
    if best_score < min_confidence:
        best_cat = "Entertainment"

    if return_scores:
        return best_cat, scores
    return best_cat


# Backwards-compatible wrapper mirroring your original API name
def _classify_category(keywords, title: str = "", description: str = "") -> str:
    return classify_category(keywords, title=title, description=description)
classify_category
