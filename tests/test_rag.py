"""RAG pipeline tests with a tiny word-hashing embedder, so no model download is needed.
The real sentence-transformers model is exercised by `docker build`."""
import os
import re
from pathlib import Path

import numpy as np
import pytest

os.environ["DEMO_MODE"] = "true"
faiss = pytest.importorskip("faiss")

from app.rag import retriever  # noqa: E402
from app.rag.build_index import build_all, chunk_markdown, load_chunks  # noqa: E402

KB = Path(__file__).parent.parent / "data" / "kb"
DIM = 512


def hash_embed(texts):
    """Bag-of-words hashed into DIM buckets, L2-normalized: lexical stand-in for a real model."""
    out = np.zeros((len(texts), DIM), dtype="float32")
    for row, text in enumerate(texts):
        for word in re.findall(r"[a-z_]+", text.lower()):
            out[row, hash(word) % DIM] += 1
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    return out / np.maximum(norms, 1e-9)


@pytest.fixture(scope="module")
def code_index(tmp_path_factory):
    out = tmp_path_factory.mktemp("index")
    counts = build_all(KB, out, embed=hash_embed)
    index = faiss.read_index(str(out / "code.faiss"))
    import json
    chunks = json.loads((out / "code.json").read_text())
    return counts, (index, chunks)


def test_every_kb_file_is_indexed(code_index):
    counts, (index, chunks) = code_index
    assert counts["code"] == len(load_chunks(KB / "code")) >= 15
    assert index.ntotal == len(chunks)
    assert all(c["title"] and c["text"] for c in chunks)


def test_chunk_metadata():
    chunk = chunk_markdown("# Deep nesting\nApplies to: nesting_depth\n\nUse guard clauses.", "x.md")[0]
    assert chunk["title"] == "Deep nesting" and chunk["applies_to"] == "nesting_depth"


def test_long_file_splits_on_sections():
    text = "# Big\n" + "\n".join(f"## Part {i}\n" + "word " * 200 for i in range(3))
    chunks = chunk_markdown(text, "big.md")
    assert len(chunks) == 3 and all(c["text"].startswith("#") for c in chunks)


def test_search_finds_relevant_guideline(code_index, monkeypatch):
    monkeypatch.setattr(retriever, "MIN_SCORE", 0.05)  # 0.25 is tuned for MiniLM, not hashing
    _, loaded = code_index
    results = retriever.search(["nesting depth guard clauses continue early"], "code",
                               top_k=3, embed=hash_embed, loaded=loaded)
    assert results[0]["source"] == "deep-nesting.md"


def test_search_dedupes_across_queries(code_index, monkeypatch):
    monkeypatch.setattr(retriever, "MIN_SCORE", 0.05)
    _, loaded = code_index
    results = retriever.search(["deep nesting guard clauses", "nesting guard clauses early"],
                               "code", top_k=5, embed=hash_embed, loaded=loaded)
    sources = [r["source"] for r in results]
    assert len(sources) == len(set(sources))


def test_retrieve_fails_soft_without_index(monkeypatch, tmp_path):
    monkeypatch.setattr(retriever, "INDEX_DIR", tmp_path)
    retriever._load.cache_clear()
    assert retriever.retrieve("anything", "nonexistent") == ""
    retriever._load.cache_clear()


def test_llm_errors_become_readable_502(monkeypatch):
    import httpx
    from fastapi.testclient import TestClient
    from openai import APIConnectionError

    import app.main as main

    def boom(*args, **kwargs):
        raise APIConnectionError(request=httpx.Request("POST", "https://api.groq.com"))
    monkeypatch.setattr(main, "generate_roast", boom)
    client = TestClient(main.app)
    analysis = client.post("/analyze/code", json={"code": "def f(a):\n    if a:\n        if a:\n            if a:\n                if a: pass\n"}).json()
    r = client.post("/roast", json={"analysis": analysis, "persona": "gordon_ramsay"})
    assert r.status_code == 502 and "LLM provider error" in r.json()["detail"]
