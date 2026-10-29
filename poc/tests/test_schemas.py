"""
Tests for Pydantic schemas.
"""
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ["DEMO_MODE"] = "true"

import pytest
from pydantic import ValidationError
from src.schemas import (
    RetrievedChunk,
    RAGResponse,
    LeadProfile,
    ConversationTurn,
    ChatSession,
)


def test_retrieved_chunk_valid():
    """RetrievedChunk should accept valid data."""
    chunk = RetrievedChunk(
        chunk_id="test_001",
        source="cynbit.in/services",
        title="AI Services",
        content="Cynbit offers AI agents.",
        score=0.95,
    )
    assert chunk.chunk_id == "test_001"
    assert chunk.score == 0.95


def test_rag_response_valid():
    """RAGResponse should accept all confidence levels."""
    chunk = RetrievedChunk(
        chunk_id="c1", source="cynbit.in", title="T", content="C", score=0.8
    )
    for confidence in ("high", "medium", "low"):
        resp = RAGResponse(
            answer="Test answer",
            sources=[chunk],
            confidence=confidence,
            grounded=True,
        )
        assert resp.confidence == confidence


def test_lead_profile_score_bounds():
    """LeadProfile qualification_score must be 0–100."""
    with pytest.raises(ValidationError):
        LeadProfile(qualification_score=101, qualification_status="hot", next_action="call")
    with pytest.raises(ValidationError):
        LeadProfile(qualification_score=-1, qualification_status="warm", next_action="email")


def test_lead_profile_defaults():
    """LeadProfile should have sensible defaults."""
    profile = LeadProfile(
        qualification_score=50,
        qualification_status="warm",
        next_action="follow up",
    )
    assert profile.service_interest == []
    assert profile.name is None
    assert isinstance(profile.collected_at, datetime)


def test_chat_session_creation():
    """ChatSession should initialise with empty turns and default LeadProfile."""
    session = ChatSession(session_id="session-xyz")
    assert session.session_id == "session-xyz"
    assert session.turns == []
    assert session.lead_profile.qualification_score == 0
    assert session.lead_profile.qualification_status == "unqualified"

