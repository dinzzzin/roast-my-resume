"""RAG retriever — week-1 stub with the final interface.

Week 2 plan: build_index.py embeds data/kb/{code,resume}/*.md with
all-MiniLM-L6-v2 into a FAISS index at `docker build` time; retrieve()
loads it and returns the top-k passages (same pattern as the class
movie_night_recommender_rag notebook).
"""


def retrieve(query: str, source_type: str, top_k: int = 3) -> str:
    """Return relevant guideline passages joined as text ('' until the index exists)."""
    return ""
