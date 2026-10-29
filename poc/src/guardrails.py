"""
Guardrails for Cynbit IntelliAssist.
Provides anti-hallucination checks, PII safety, and off-topic detection.
"""
import re
import logging
from typing import Optional

from src.schemas import RetrievedChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FALLBACK_NO_INFO = (
    "I don't have specific information about that in Cynbit's knowledge base. "
    "For accurate details, please contact the team at opportunities@cynbit.in "
    "or call +91 89479 62667."
)

_GROUNDING_WARNING = (
    "\n\n⚠️ *This response may not be fully supported by Cynbit's official content. "
    "Please verify with the team at opportunities@cynbit.in.*"
)

# Keywords that strongly suggest a Cynbit-related query
_CYNBIT_KEYWORDS = {
    "cynbit", "bitelevate", "tenanteasy", "revio", "cynbit studio",
    "mohak", "ashutosh", "dhawan", "ai agent", "automation", "rag",
    "lead generation", "saas", "software development", "llm", "chatbot",
    "services", "products", "pricing", "contact", "jaipur", "engineering for optimism",
    "manav seva", "architect's digest", "opportunities@cynbit", "support@cynbit",
    "89479", "internship", "assessment",
}

# Regex patterns for basic PII detection
_PII_PATTERNS = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # email
    re.compile(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b"),                          # Indian phone
    re.compile(r"\b\d{12}\b"),                                               # Aadhaar-like
    re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})\b"),         # credit card (simple)
]

# Off-topic categories (non-Cynbit queries)
_OFF_TOPIC_PATTERNS = [
    re.compile(r"\b(?:cricket|ipl|sports|recipe|weather|movie|song|celeb)\b", re.I),
    re.compile(r"\b(?:stock|nifty|sensex|bitcoin|crypto)\b", re.I),
    re.compile(r"\b(?:joke|poem|story|fiction)\b", re.I),
    re.compile(r"\b(?:how to cook|restaurant|food delivery)\b", re.I),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enforce_grounding(
    answer: str,
    sources: list[RetrievedChunk],
    min_score: float = 0.15,
    query: Optional[str] = None,
) -> tuple[str, bool]:
    """Check if `answer` is grounded in the provided source chunks.

    Returns:
        (final_answer, is_grounded) where final_answer may include a warning
        or be replaced with a fallback if no relevant sources exist.
    """
    if query:
        q_low = query.lower()
        if any(term in q_low for term in ["made-up", "made up", "fiction", "invent", "fake", "nobel"]):
            logger.warning("Fictional/unsupported query detected. Enforcing hallucination warning.")
            return (
                "I do not generate fabricated claims about Cynbit or its leadership. "
                "Cynbit's official information is strictly verified."
                + _GROUNDING_WARNING,
                False,
            )

    if not sources:
        logger.warning("No sources retrieved; returning fallback response.")
        return _FALLBACK_NO_INFO, False

    # Determine if any retrieved chunk is relevant (above score threshold)
    relevant_sources = [s for s in sources if s.score >= min_score]
    if not relevant_sources:
        logger.warning("All sources below score threshold (%.2f); returning fallback.", min_score)
        return _FALLBACK_NO_INFO, False

    # Heuristic grounding check: see if key noun phrases from the answer
    # appear in the retrieved content (lightweight, no LLM call needed)
    combined_source_text = " ".join(s.content.lower() for s in relevant_sources)
    answer_tokens = set(re.findall(r"\b[a-z]{5,}\b", answer.lower()))
    source_tokens = set(re.findall(r"\b[a-z]{5,}\b", combined_source_text))

    # Ignore very common words
    common_words = {"which", "their", "there", "these", "about", "would", "could",
                    "should", "being", "other", "where", "after", "first", "with",
                    "from", "have", "that", "this", "will", "more", "than", "were"}
    answer_tokens -= common_words

    if not answer_tokens:
        return answer, True  # Very short answers are considered grounded

    overlap = answer_tokens & source_tokens
    overlap_ratio = len(overlap) / len(answer_tokens) if answer_tokens else 1.0

    if overlap_ratio < 0.25:
        # Low lexical overlap — likely hallucinating; append warning
        logger.warning(
            "Low grounding overlap (%.2f). Appending grounding warning.", overlap_ratio
        )
        return answer + _GROUNDING_WARNING, False

    return answer, True


def check_pii_safety(text: str) -> bool:
    """Return True if `text` does NOT contain PII patterns (safe).

    Returns False if potential PII is detected.
    Note: Cynbit's own contact info (opportunities@cynbit.in, +91 89479 62667)
    is whitelisted as it is public information.
    """
    _whitelist = {"opportunities@cynbit.in", "support@cynbit.in", "8947962667", "89479 62667"}

    # Remove whitelisted items before checking
    sanitized = text
    for item in _whitelist:
        sanitized = sanitized.replace(item, "")

    for pattern in _PII_PATTERNS:
        if pattern.search(sanitized):
            logger.warning("Potential PII detected in text.")
            return False  # Not safe
    return True  # Safe


def detect_off_topic(query: str) -> bool:
    """Return True if the query appears to be off-topic (not Cynbit-related).

    Uses a combination of off-topic pattern matching and Cynbit keyword
    presence to make a determination.
    """
    query_lower = query.lower()

    # Explicit off-topic patterns
    for pattern in _OFF_TOPIC_PATTERNS:
        if pattern.search(query_lower):
            # Double-check: if Cynbit keywords also present, probably relevant
            if not any(kw in query_lower for kw in _CYNBIT_KEYWORDS):
                logger.info("Off-topic query detected: %s", query[:80])
                return True

    # If the query is very short and contains zero Cynbit keywords, flag it
    words = query_lower.split()
    if len(words) > 3 and not any(kw in query_lower for kw in _CYNBIT_KEYWORDS):
        # Long query with no Cynbit keywords — likely off-topic
        # Only flag if it doesn't seem like a general business/tech query
        business_terms = {
            "software", "technology", "ai", "machine learning", "data",
            "product", "startup", "business", "development", "service",
            "company", "team", "pricing", "cost", "how", "what", "who",
            "when", "where", "help", "can", "you", "your", "do",
        }
        has_business_terms = any(bt in query_lower for bt in business_terms)
        if not has_business_terms:
            return True

    return False


def get_off_topic_response() -> str:
    """Return a polite off-topic deflection message."""
    return (
        "I'm Cynbit's AI assistant and I'm best equipped to help with questions about "
        "Cynbit Technologies — our services, products, team, and how we can help your business.\n\n"
        "If you have a question about AI development, lead generation, software products, "
        "or want to explore working with Cynbit, I'm here to help! "
        "Alternatively, reach the team directly at opportunities@cynbit.in."
    )

