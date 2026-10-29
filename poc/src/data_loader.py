"""
Data loading and chunking utilities for Cynbit IntelliAssist.
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def load_knowledge_base(path: str) -> list[dict]:
    """Load knowledge base JSON, stripping JS-style comment lines."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Knowledge base not found at: {path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Strip // comment lines (used for the SYNTHETIC DATA header)
    lines = [line for line in content.splitlines() if not line.strip().startswith("//")]
    cleaned = "\n".join(lines)

    docs = json.loads(cleaned)
    logger.info("Loaded %d documents from %s", len(docs), path)
    return docs


def chunk_document(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
) -> list[str]:
    """Split `text` into overlapping fixed-size character chunks.

    Args:
        text: The input text to chunk.
        chunk_size: Maximum characters per chunk.
        overlap: Number of characters to overlap between consecutive chunks.

    Returns:
        List of text chunks.
    """
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]

        # Try to break at sentence boundaries
        if end < len(text):
            break_at = max(
                chunk.rfind(". "),
                chunk.rfind(".\n"),
                chunk.rfind("! "),
                chunk.rfind("? "),
            )
            if break_at > chunk_size // 2:
                chunk = text[start : start + break_at + 1]
                end = start + break_at + 1

        chunks.append(chunk.strip())
        start = end - overlap

    return [c for c in chunks if c]


def prepare_chunks(raw_docs: list[dict], chunk_size: int = 512, overlap: int = 64) -> list[dict]:
    """Split documents with long content into overlapping chunks.

    Documents whose content fits within `chunk_size` are returned as-is.
    Longer documents are split, with each chunk inheriting the parent
    document's metadata and a numeric suffix on its ID.

    Args:
        raw_docs: List of raw document dicts from the knowledge base.
        chunk_size: Maximum characters per chunk.
        overlap: Overlap characters between consecutive chunks.

    Returns:
        Flat list of chunk dicts, each with the same schema as a KB document.
    """
    result: list[dict] = []
    for doc in raw_docs:
        content = doc.get("content", "")
        if len(content) <= chunk_size:
            result.append(doc)
            continue

        sub_chunks = chunk_document(content, chunk_size=chunk_size, overlap=overlap)
        for i, sub_text in enumerate(sub_chunks):
            chunk_doc = {**doc}
            chunk_doc["id"] = f"{doc.get('id', 'chunk')}_{i:02d}"
            chunk_doc["content"] = sub_text
            result.append(chunk_doc)
        logger.debug(
            "Document '%s' split into %d chunks.", doc.get("id"), len(sub_chunks)
        )

    logger.info(
        "prepare_chunks: %d raw docs → %d prepared chunks.", len(raw_docs), len(result)
    )
    return result


def load_and_prepare(
    path: str,
    chunk_size: int = 512,
    overlap: int = 64,
) -> list[dict]:
    """Convenience function: load KB and prepare chunks in one step."""
    raw = load_knowledge_base(path)
    return prepare_chunks(raw, chunk_size=chunk_size, overlap=overlap)

