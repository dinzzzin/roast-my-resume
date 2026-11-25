"""'Have Mercy' rewrites: drop the persona, fix the work, validate, retry on failure."""
from app.llm.provider import chat, extract_json, is_demo_mode
from app.mercy import equivalence
from app.mercy.validate import validate_bullet, validate_code
from app.rag.retriever import retrieve
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
    guidelines = retrieve(f"{finding.metric}: {finding.detail}", source_type, top_k=2)
    messages = [
        {"role": "system", "content": SYSTEM[source_type]},
        {"role": "user", "content": (
            f"Problems: {finding.detail}\n\nOriginal:\n{finding.snippet}\n\n"
            + (f"Follow these guidelines:\n{guidelines}\n\n" if guidelines else "")
            + "If your rewrite changes behavior in any way (for example, how missing keys "
            "or errors are handled), say so explicitly in the explanation.\n\n"
            'Return ONLY JSON: {"revised": str, "explanation": str}')},
    ]
    revised, explanation, ok, error = finding.snippet, "", False, ""
    check: equivalence.EquivalenceResult | None = None
    cases: list[str] | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        data = extract_json(chat(messages, temperature=0.1, json_mode=True))
        revised, explanation = data.get("revised", ""), data.get("explanation", "")
        ok, error = validate(revised)
        if not ok:
            # Feed the validator error back to the model and try again.
            feedback = f"That failed validation: {error}. Fix it and return the same JSON format."
        else:
            check, cases = _check_behavior(finding.snippet, revised, source_type, cases)
            if check is None or check.equivalent is not False:
                break  # behaves the same, or can't be tested: accept it
            feedback = equivalence.feedback_message(check)
        if attempt < MAX_ATTEMPTS:
            messages += [{"role": "assistant", "content": revised},
                         {"role": "user", "content": feedback}]
    return MercyItem(finding_id=finding.id, original=finding.snippet, revised=revised,
                     explanation=explanation or error, valid=ok, attempts=attempt,
                     equivalent=check.equivalent if check else None,
                     cases_checked=check.cases_checked if check else 0,
                     mismatches=check.mismatches if check else [],
                     equivalence_note=check.note if check else "")


def _check_behavior(original: str, revised: str, source_type: str, cases: list[str] | None):
    """Run the equivalence check for code. Test inputs are generated once and reused."""
    if source_type != "code" or not equivalence.enabled():
        return None, cases
    reason = equivalence.untestable_reason(original)
    if reason:
        return equivalence.EquivalenceResult(None, note=f"not tested: {reason}"), cases
    if cases is None:
        try:
            cases = equivalence.generate_cases(original)
        except Exception as e:  # LLM hiccup: skip the check rather than fail the rewrite
            return equivalence.EquivalenceResult(None, note=f"could not generate inputs: {e}"), []
    return equivalence.run_cases(original, revised, cases), cases


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
