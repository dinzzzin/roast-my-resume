"""Retrieve knowledge-base passages for a prompt.

Fails soft: if the index or embedding model is missing (local dev without the
RAG packages, or before build_index has run), retrieve() returns "" and the
roast/mercy prompts simply go without guideline context.
"""
import json
import logging
from functools import lru_cache

import numpy as np

from app.rag.build_index import INDEX_DIR, EmbedFn, sentence_transformer_embedder

log = logging.getLogger(__name__)
MIN_SCORE = 0.25  # cosine similarity below this is treated as irrelevant


@lru_cache(maxsize=1)
def _embedder() -> EmbedFn | None:
    try:
        return sentence_transformer_embedder()
    except Exception as e:  # package missing, model not cached, etc.
        log.warning("RAG disabled, embedder unavailable: %s", e)
        return None


@lru_cache(maxsize=8)
def _load(source_type: str):
    index_path = INDEX_DIR / f"{source_type}.faiss"
    chunks_path = INDEX_DIR / f"{source_type}.json"
    if not (index_path.exists() and chunks_path.exists()):
        log.warning("RAG disabled for %s: no index at %s", source_type, index_path)
        return None
    import faiss
    return faiss.read_index(str(index_path)), json.loads(chunks_path.read_text(encoding="utf-8"))


def search(queries: list[str], source_type: str, top_k: int = 3,
           embed: EmbedFn | None = None, loaded=None) -> list[dict]:
    """Best chunks across all queries, deduplicated, highest score first."""
    loaded = loaded or _load(source_type)
    embed = embed or _embedder()
    queries = [q for q in queries if q and q.strip()]
    if not (loaded and embed and queries):
        return []
    index, chunks = loaded
    vectors = np.asarray(embed(queries), dtype="float32")
    scores, ids = index.search(vectors, min(top_k, len(chunks)))
    best: dict[int, float] = {}
    for row_scores, row_ids in zip(scores, ids):
        for score, idx in zip(row_scores, row_ids):
            if idx >= 0 and score >= MIN_SCORE:
                best[idx] = max(best.get(idx, -1.0), float(score))
    ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [{**chunks[i], "score": round(s, 3)} for i, s in ranked]


def format_context(results: list[dict]) -> str:
    return "\n\n".join(f"[{r['title']}]\n{r['text']}" for r in results)


def retrieve(query: str | list[str], source_type: str, top_k: int = 3) -> str:
    """Return relevant guideline passages as prompt-ready text ('' if RAG is unavailable)."""
    queries = [query] if isinstance(query, str) else list(query)
    try:
        return format_context(search(queries, source_type, top_k))
    except Exception as e:  # never let retrieval take down a roast
        log.warning("RAG retrieval failed: %s", e)
        return ""
