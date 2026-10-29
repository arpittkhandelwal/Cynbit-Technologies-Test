"""
Tests for KnowledgeBase (RAG retrieval).
"""
import os
import sys
from pathlib import Path

# Project root on path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ["DEMO_MODE"] = "true"

import pytest
from src.rag import KnowledgeBase
from src.schemas import RetrievedChunk

KB_PATH = str(Path(__file__).parent.parent / "data" / "cynbit_knowledge_base.json")


@pytest.fixture(scope="module")
def kb():
    """Build the knowledge base once for all tests in this module."""
    return KnowledgeBase(data_path=KB_PATH)


def test_kb_loads(kb):
    """Knowledge base should load without errors."""
    assert kb._chunks, "Knowledge base should have loaded chunks"
    assert len(kb._chunks) >= 20, "Should have at least 20 knowledge chunks"


def test_retrieve_returns_list(kb):
    """retrieve() should return a list of RetrievedChunk objects."""
    results = kb.retrieve("AI services", k=3)
    assert isinstance(results, list)
    assert len(results) > 0
    assert all(isinstance(r, RetrievedChunk) for r in results)


def test_retrieve_top_k(kb):
    """retrieve() should not return more chunks than requested."""
    results = kb.retrieve("Cynbit contact information", k=2)
    assert len(results) <= 2


def test_retrieve_scores_are_valid(kb):
    """All retrieved chunks should have a non-negative score."""
    results = kb.retrieve("BitElevate adaptive learning", k=3)
    for chunk in results:
        assert chunk.score >= 0.0, "Score should be non-negative"


def test_retrieve_cynbit_contact(kb):
    """Query about contact should retrieve the contact chunk."""
    results = kb.retrieve("email contact Cynbit", k=3)
    combined_content = " ".join(r.content for r in results).lower()
    assert "opportunities@cynbit.in" in combined_content or "contact" in combined_content

