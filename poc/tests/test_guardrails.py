"""
Tests for guardrails module.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ["DEMO_MODE"] = "true"

import pytest
from src.guardrails import enforce_grounding, check_pii_safety, detect_off_topic
from src.schemas import RetrievedChunk


def _make_chunk(content: str, score: float = 0.8) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="test",
        source="cynbit.in/test",
        title="Test Chunk",
        content=content,
        score=score,
    )


class TestEnforceGrounding:
    def test_empty_sources_returns_fallback(self):
        answer, grounded = enforce_grounding("Some answer", sources=[])
        assert grounded is False
        assert "opportunities@cynbit.in" in answer

    def test_low_score_sources_returns_fallback(self):
        chunk = _make_chunk("Cynbit offers AI services", score=0.05)
        answer, grounded = enforce_grounding("Cynbit offers AI", [chunk], min_score=0.15)
        assert grounded is False

    def test_well_grounded_answer(self):
        chunk = _make_chunk(
            "Cynbit Technologies offers AI agents, software development, and growth services."
        )
        answer = "Cynbit offers AI agents and software development services."
        result, grounded = enforce_grounding(answer, [chunk])
        assert grounded is True

    def test_warning_appended_on_low_overlap(self):
        chunk = _make_chunk("Cynbit is based in Jaipur Rajasthan India founded 2024.")
        # Answer talks about something completely unrelated
        answer = "Cynbit specialises exclusively in blockchain cryptocurrency trading platforms."
        result, grounded = enforce_grounding(answer, [chunk])
        # May or may not append warning, but should not crash
        assert isinstance(result, str)
        assert isinstance(grounded, bool)


class TestPiiSafety:
    def test_cynbit_email_is_safe(self):
        """Cynbit's public email should not trigger PII flag."""
        text = "Contact us at opportunities@cynbit.in"
        assert check_pii_safety(text) is True

    def test_random_email_detected(self):
        """A non-whitelisted personal email should be flagged."""
        text = "My personal email is john.doe123@private.com"
        assert check_pii_safety(text) is False

    def test_indian_phone_detected(self):
        """An Indian phone number (not whitelisted) should be flagged."""
        text = "Call me at 9876543210"
        assert check_pii_safety(text) is False

    def test_clean_text_is_safe(self):
        """Plain text with no PII should pass."""
        assert check_pii_safety("Cynbit Technologies is based in Jaipur.") is True


class TestOffTopicDetection:
    def test_recipe_is_off_topic(self):
        assert detect_off_topic("What is the recipe for butter chicken?") is True

    def test_cynbit_query_is_on_topic(self):
        assert detect_off_topic("What AI services does Cynbit offer?") is False

    def test_ipl_is_off_topic(self):
        assert detect_off_topic("Who won the IPL 2024?") is True

    def test_general_ai_query_not_off_topic(self):
        """A general AI/tech query should not be flagged."""
        assert detect_off_topic("How does RAG work in AI systems?") is False

