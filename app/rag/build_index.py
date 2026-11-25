"""Build one FAISS index per knowledge-base folder.

Run at `docker build` time (see Dockerfile) so the container never downloads
anything at startup:

    python -m app.rag.build_index

data/kb/code/*.md   -> data/index/code.faiss   + data/index/code.json
data/kb/resume/*.md -> data/index/resume.faiss + data/index/resume.json
"""
import json
import os
import re
from pathlib import Path
from typing import Callable

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
KB_DIR = Path(os.getenv("RAG_KB_DIR", ROOT / "data" / "kb"))
INDEX_DIR = Path(os.getenv("RAG_INDEX_DIR", ROOT / "data" / "index"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
MAX_CHARS = 1500

EmbedFn = Callable[[list[str]], np.ndarray]


def chunk_markdown(text: str, source: str) -> list[dict]:
    """One chunk per file, or per '## ' section when a file is long."""
    lines = text.strip().splitlines()
    title = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("#") else source
    applies = ""
    m = re.search(r"^Applies to:\s*(.+)$", text, re.MULTILINE)
    if m:
        applies = m.group(1).strip()

    if len(text) <= MAX_CHARS:
        sections = [text.strip()]
    else:
        sections = [s.strip() for s in re.split(r"\n(?=## )", text) if s.strip()]
        # Drop sections that are only a heading (e.g. the "# Title" line before the first "## ").
        sections = [s for s in sections
                    if any(ln.strip() and not ln.startswith("#") for ln in s.splitlines())]

    chunks = []
    for i, section in enumerate(sections):
        body = section if section.startswith("#") else f"# {title}\n{section}"
        chunks.append({"id": f"{source}#{i}", "source": source, "title": title,
                       "applies_to": applies, "text": body})
    return chunks


def load_chunks(folder: Path) -> list[dict]:
    chunks = []
    for path in sorted(folder.glob("*.md")):
        chunks.extend(chunk_markdown(path.read_text(encoding="utf-8"), path.name))
    return chunks


def sentence_transformer_embedder(model_name: str = EMBED_MODEL) -> EmbedFn:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name, device="cpu")

    def embed(texts: list[str]) -> np.ndarray:
        return model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return embed


def build_folder(folder: Path, out_dir: Path, embed: EmbedFn) -> int:
    import faiss
    chunks = load_chunks(folder)
    if not chunks:
        return 0
    vectors = np.asarray(embed([c["text"] for c in chunks]), dtype="float32")
    index = faiss.IndexFlatIP(vectors.shape[1])  # inner product on unit vectors = cosine
    index.add(vectors)
    out_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(out_dir / f"{folder.name}.faiss"))
    (out_dir / f"{folder.name}.json").write_text(json.dumps(chunks, indent=1), encoding="utf-8")
    return len(chunks)


def build_all(kb_dir: Path = KB_DIR, out_dir: Path = INDEX_DIR,
              embed: EmbedFn | None = None) -> dict[str, int]:
    folders = [f for f in sorted(kb_dir.iterdir()) if f.is_dir() and any(f.glob("*.md"))]
    if not folders:
        print(f"No knowledge-base folders with .md files under {kb_dir}")
        return {}
    embed = embed or sentence_transformer_embedder()
    counts = {f.name: build_folder(f, out_dir, embed) for f in folders}
    for name, n in counts.items():
        print(f"Indexed {n:>3} chunks from data/kb/{name}/")
    return counts


if __name__ == "__main__":
    build_all()
