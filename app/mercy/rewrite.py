"""'Have Mercy' rewrites: drop the persona, fix the work, validate, retry on failure."""
from app.llm.provider import chat, extract_json, is_demo_mode
from app.mercy.validate import validate_bullet, validate_code
from app.schemas import AnalysisResult, Finding, MercyItem, MercyResponse

MAX_ATTEMPTS = 3

SYSTEM = {
    "code": ("You are a precise senior Python engineer. Refactor the given function to fix the "
             "stated problems while preserving behavior. Return complete, valid Python."),
    "resume": ("You are a professional resume editor. Rewrite the bullet with a strong action "
               "verb, concrete scope, and a measurable result. Never invent specific numbers — "
               "use a bracketed placeholder like [X%] when the original has no figure. "
               "Keep it under 30 words."),
}


def _rewrite_one(finding: Finding, source_type: str) -> MercyItem:
    validate = validate_code if source_type == "code" else validate_bullet
    messages = [
        {"role": "system", "content": SYSTEM[source_type]},
        {"role": "user", "content": (
            f"Problems: {finding.detail}\n\nOriginal:\n{finding.snippet}\n\n"
            'Return ONLY JSON: {"revised": str, "explanation": str}')},
    ]
    revised, explanation, ok, error = finding.snippet, "", False, ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        data = extract_json(chat(messages, temperature=0.1, json_mode=True))
        revised, explanation = data.get("revised", ""), data.get("explanation", "")
        ok, error = validate(revised)
        if ok:
            break
        # Feed the validator error back to the model and try again.
        messages += [{"role": "assistant", "content": revised},
                     {"role": "user", "content": f"That failed validation: {error}. Fix it and "
                                                 "return the same JSON format."}]
    return MercyItem(finding_id=finding.id, original=finding.snippet, revised=revised,
                     explanation=explanation or error, valid=ok, attempts=attempt)


def _demo_item(finding: Finding, source_type: str) -> MercyItem:
    note = ("# DEMO MODE: set an LLM API key in .env for a real refactor\n"
            if source_type == "code" else "[DEMO MODE] ")
    return MercyItem(finding_id=finding.id, original=finding.snippet,
                     revised=note + finding.snippet,
                     explanation=f"Would fix: {finding.detail}", valid=True, attempts=0)


def generate_mercy(analysis: AnalysisResult, finding_ids: list[str] | None = None) -> MercyResponse:
    targets = [f for f in analysis.findings if not finding_ids or f.id in finding_ids]
    # Several findings can point at the same function — rewrite each snippet once.
    seen, unique = set(), []
    for f in targets:
        if f.snippet not in seen:
            seen.add(f.snippet)
            unique.append(f)
    if is_demo_mode():
        return MercyResponse(items=[_demo_item(f, analysis.source_type) for f in unique],
                             mode="demo")
    return MercyResponse(items=[_rewrite_one(f, analysis.source_type) for f in unique],
                         mode="live")
