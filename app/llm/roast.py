"""Roast generation. Week 1: direct call. Week 3: wrap in the LangGraph router
and add RAG context (style-guide / action-verb passages) to the prompt."""
import json

from app.llm.personas import PERSONAS, system_prompt
from app.llm.provider import chat, extract_json, is_demo_mode
from app.rag.retriever import retrieve
from app.schemas import AnalysisResult, RoastLine, RoastResponse


def _findings_payload(analysis: AnalysisResult) -> str:
    return json.dumps([
        {"finding_id": f.id, "location": f.location, "metric": f.metric,
         "detail": f.detail, "snippet": f.snippet[:800]}
        for f in analysis.findings
    ], indent=2)


def generate_roast(analysis: AnalysisResult, persona_id: str) -> RoastResponse:
    persona = PERSONAS[persona_id]
    valid_ids = {f.id for f in analysis.findings}

    if is_demo_mode():
        return RoastResponse(
            persona=persona_id, opener=persona["opener"], mode="demo",
            roast=[RoastLine(finding_id=f.id, text=persona["demo"].format(
                detail=f.detail, location=f.location)) for f in analysis.findings],
        )

    context = retrieve(" ".join(f.metric for f in analysis.findings), analysis.source_type)
    user_prompt = (
        f"Roast this {analysis.source_type} submission. Findings measured by our analyzer:\n"
        f"{_findings_payload(analysis)}\n\n"
        + (f"Relevant guidelines you may reference:\n{context}\n\n" if context else "")
        + 'Return ONLY JSON: {"opener": str, "roast": [{"finding_id": str, "text": str}]}. '
        "One roast line per finding, 1-3 sentences each, using the exact finding_id values."
    )
    raw = chat([{"role": "system", "content": system_prompt(persona_id)},
                {"role": "user", "content": user_prompt}],
               temperature=persona["temperature"], json_mode=True)
    data = extract_json(raw)
    lines = [RoastLine(**r) for r in data.get("roast", []) if r.get("finding_id") in valid_ids]
    return RoastResponse(persona=persona_id, opener=data.get("opener", ""),
                         roast=lines, mode="live")
