"""Hotel policy search: Project 1's keyword retrieval (copied into src/policy/) over Project 1's synthetic documents.

The index isn't committed; it is built on first use and rebuilt whenever a document changes (fingerprint check).
"""

import threading

from src.policy.config import USE_EMBEDDINGS

_LOCK = threading.Lock()
_CACHE: dict = {}


def retriever():
    from src.policy.ingest import build_index, docs_fingerprint, index_is_current
    from src.policy.retrieve import Retriever

    with _LOCK:
        fingerprint = docs_fingerprint(USE_EMBEDDINGS)
        if _CACHE.get("fingerprint") != fingerprint:
            if not index_is_current(USE_EMBEDDINGS):
                build_index(use_embeddings=USE_EMBEDDINGS)
            _CACHE.update(fingerprint=fingerprint, retriever=Retriever(use_embeddings=USE_EMBEDDINGS))
        return _CACHE["retriever"]


def search(question: str, prop: str, k: int = 3) -> list[dict]:
    """Top passages for this property plus brand-wide documents. Each passage keeps its source and section."""
    return retriever().search(question, prop, k=k)


def keyword_matches(text: str, prop: str) -> int:
    """How many passages share at least one keyword with the text (used by the off-topic check)."""
    return retriever().signals(text, prop)["keyword_matches"]
