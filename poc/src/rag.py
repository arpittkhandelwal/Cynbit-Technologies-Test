"""
FAISS-based knowledge base for Cynbit IntelliAssist.
Uses sentence-transformers for local embeddings (no API key needed).
Falls back to TF-IDF if sentence-transformers is unavailable.
"""
import json
import logging
import os
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

from src.schemas import RetrievedChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding backends
# ---------------------------------------------------------------------------

def _load_sentence_transformer(model_name: str):
    """Try to load a SentenceTransformer; return None if unavailable.

    Uses a short import timeout guard so that a missing/corrupted model does
    not hang the process indefinitely.
    """
    import importlib.util
    if importlib.util.find_spec("sentence_transformers") is None:
        logger.warning("sentence-transformers not installed. Falling back to TF-IDF.")
        return None
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        # Only load from cache; set TRANSFORMERS_OFFLINE to skip network calls
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
        return SentenceTransformer(model_name)
    except Exception as exc:
        logger.warning("sentence-transformers load failed (%s). Falling back to TF-IDF.", exc)
        return None


def _load_faiss():
    """Try to import FAISS; return None if unavailable."""
    try:
        import faiss  # type: ignore
        return faiss
    except ImportError:
        logger.warning("faiss-cpu not installed. Falling back to numpy cosine similarity.")
        return None


# ---------------------------------------------------------------------------
# KnowledgeBase
# ---------------------------------------------------------------------------

class KnowledgeBase:
    """Vector-store backed knowledge base using FAISS + sentence-transformers.

    Falls back gracefully to TF-IDF + numpy cosine similarity if the
    heavyweight dependencies are not installed.
    """

    def __init__(
        self,
        data_path: str,
        embedding_model: str = "all-MiniLM-L6-v2",
        index_dir: Optional[str] = None,
    ) -> None:
        self.data_path = data_path
        self.embedding_model_name = embedding_model
        self.index_dir = Path(index_dir or os.getenv("FAISS_INDEX_PATH", "data/faiss_index"))

        self._chunks: list[dict] = []
        self._embeddings: Optional[np.ndarray] = None
        self._faiss_index = None
        self._tfidf_vectorizer = None
        self._tfidf_matrix = None
        self._st_model = None
        self._faiss = _load_faiss()

        self._build_or_load_index()

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    def _build_or_load_index(self) -> None:
        index_path = self.index_dir / "index.pkl"
        if index_path.exists():
            logger.info("Loading cached FAISS index from %s", index_path)
            self._load_index(index_path)
        else:
            logger.info("Building index from %s", self.data_path)
            self._build_index()
            self._save_index(index_path)

    def _load_chunks(self) -> list[dict]:
        with open(self.data_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Strip JSON-style comment lines (// ...)
        lines = [l for l in content.splitlines() if not l.strip().startswith("//")]
        return json.loads("\n".join(lines))

    def _build_index(self) -> None:
        self._chunks = self._load_chunks()
        texts = [c["content"] for c in self._chunks]

        self._st_model = _load_sentence_transformer(self.embedding_model_name)

        if self._st_model is not None and self._faiss is not None:
            self._build_faiss_index(texts)
        elif self._st_model is not None:
            # FAISS unavailable – keep raw numpy embeddings
            self._embeddings = self._st_model.encode(texts, normalize_embeddings=True).astype("float32")
        else:
            self._build_tfidf_index(texts)

    def _build_faiss_index(self, texts: list[str]) -> None:
        faiss = self._faiss
        self._embeddings = self._st_model.encode(texts, normalize_embeddings=True).astype("float32")
        dim = self._embeddings.shape[1]
        self._faiss_index = faiss.IndexFlatIP(dim)  # inner-product = cosine for normalised vecs
        self._faiss_index.add(self._embeddings)
        logger.info("FAISS index built with %d vectors (dim=%d).", len(texts), dim)

    def _build_tfidf_index(self, texts: list[str]) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
        from sklearn.metrics.pairwise import cosine_similarity  # type: ignore  # noqa: F401

        self._tfidf_vectorizer = TfidfVectorizer(stop_words="english")
        self._tfidf_matrix = self._tfidf_vectorizer.fit_transform(texts)
        logger.info("TF-IDF fallback index built with %d documents.", len(texts))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_index(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "chunks": self._chunks,
            "embeddings": self._embeddings,
            "tfidf_vectorizer": self._tfidf_vectorizer,
            "tfidf_matrix": self._tfidf_matrix,
            "embedding_model_name": self.embedding_model_name,
        }
        # FAISS index saved separately (binary format)
        if self._faiss_index is not None:
            faiss_path = path.parent / "faiss.index"
            self._faiss.write_index(self._faiss_index, str(faiss_path))
            payload["faiss_index_path"] = str(faiss_path)

        with open(path, "wb") as f:
            pickle.dump(payload, f)
        logger.info("Index saved to %s.", path)

    def _load_index(self, path: Path) -> None:
        with open(path, "rb") as f:
            payload = pickle.load(f)

        self._chunks = payload["chunks"]
        self._embeddings = payload.get("embeddings")
        self._tfidf_vectorizer = payload.get("tfidf_vectorizer")
        self._tfidf_matrix = payload.get("tfidf_matrix")

        faiss_path = payload.get("faiss_index_path")
        model_name = payload.get("embedding_model_name", self.embedding_model_name)
        if faiss_path and self._faiss and Path(faiss_path).exists():
            self._faiss_index = self._faiss.read_index(faiss_path)
            self._st_model = _load_sentence_transformer(model_name)
        elif self._embeddings is not None:
            self._st_model = _load_sentence_transformer(model_name)

        # Fallback if no backend is operational
        if (
            (self._faiss_index is None or self._st_model is None)
            and (self._embeddings is None or self._st_model is None)
            and (self._tfidf_vectorizer is None or self._tfidf_matrix is None)
        ):
            logger.info("Rebuilding index because no usable model/index was found...")
            texts = [c["content"] for c in self._chunks]
            self._build_tfidf_index(texts)

        logger.info("Index loaded: %d chunks.", len(self._chunks))

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(self, query: str, k: int = 3) -> list[RetrievedChunk]:
        """Return the top-k most relevant chunks for `query`."""
        if not self._chunks:
            return []

        k = min(k, len(self._chunks))

        if self._faiss_index is not None and self._st_model is not None:
            return self._faiss_retrieve(query, k)
        elif self._embeddings is not None and self._st_model is not None:
            return self._numpy_retrieve(query, k)
        elif self._tfidf_vectorizer is not None:
            return self._tfidf_retrieve(query, k)
        else:
            logger.warning("No retrieval backend available.")
            return []

    def _faiss_retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        q_emb = self._st_model.encode([query], normalize_embeddings=True).astype("float32")
        scores, indices = self._faiss_index.search(q_emb, k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            chunk = self._chunks[idx]
            results.append(self._make_chunk(chunk, float(score)))
        return results

    def _numpy_retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        q_emb = self._st_model.encode([query], normalize_embeddings=True).astype("float32")
        scores = (self._embeddings @ q_emb.T).squeeze()
        top_k = np.argsort(scores)[::-1][:k]
        return [self._make_chunk(self._chunks[i], float(scores[i])) for i in top_k]

    def _tfidf_retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        from sklearn.metrics.pairwise import cosine_similarity  # type: ignore

        q_vec = self._tfidf_vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self._tfidf_matrix).squeeze()
        top_k = np.argsort(scores)[::-1][:k]
        return [self._make_chunk(self._chunks[i], float(scores[i])) for i in top_k]

    @staticmethod
    def _make_chunk(chunk: dict, score: float) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=chunk.get("id", ""),
            source=chunk.get("source", ""),
            title=chunk.get("title", ""),
            content=chunk.get("content", ""),
            score=score,
        )
