"""Deterministic resume analysis with pdfplumber.

Week-1 version: extracts bullet lines and flags rule-based weaknesses.
Person B will extend with section detection and the RAG verb knowledge base.
"""
import io
import re

import pdfplumber

from app.schemas import AnalysisResult, Finding

# "(cid:N)" is what pdfplumber emits when a font's bullet glyph has no unicode mapping.
BULLET_RE = re.compile(r"^\s*(?:[•●▪◦■\-\*–]|\(cid:\d+\))\s*(.*)")
WEAK_OPENERS = ["responsible for", "helped", "worked on", "assisted", "participated in",
                "involved in", "duties included", "tasked with", "handled", "was part of"]
VAGUE_WORDS = ["various", "several", "many", "etc", "stuff", "things", "successfully"]
NUMBER_RE = re.compile(r"\d|%|\$")
MIN_WORDS, MAX_WORDS = 6, 30


def extract_bullets(pdf_bytes: bytes) -> list[str]:
    bullets: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                m = BULLET_RE.match(line)
                if m:
                    bullets.append(m.group(1).strip())
                elif bullets and line[:1].islower():
                    bullets[-1] += " " + line.strip()  # wrapped continuation line
    return bullets


def check_bullet(text: str) -> list[tuple[str, str, float, str]]:
    """Return (metric, value, severity, detail) tuples for one bullet."""
    issues = []
    lower = text.lower()
    words = text.split()
    opener = next((w for w in WEAK_OPENERS if lower.startswith(w)), None)
    if opener:
        issues.append(("weak_verb", opener, 0.7, f"opens with '{opener}'"))
    if not NUMBER_RE.search(text):
        issues.append(("no_metrics", "none", 0.5, "no number, %, or $ to show impact"))
    vague = [w for w in VAGUE_WORDS if re.search(rf"\b{w}\b", lower)]
    if vague:
        issues.append(("vague_language", ", ".join(vague), 0.4, f"vague words: {', '.join(vague)}"))
    if len(words) > MAX_WORDS:
        issues.append(("too_long", len(words), 0.4, f"{len(words)} words"))
    elif len(words) < MIN_WORDS:
        issues.append(("too_short", len(words), 0.3, f"only {len(words)} words"))
    return issues


def analyze_bullets(bullets: list[str], max_findings: int = 8) -> AnalysisResult:
    findings = []
    for idx, bullet in enumerate(bullets, 1):
        issues = check_bullet(bullet)
        if not issues:
            continue
        # One finding per bullet; severity grows with the number of problems.
        severity = min(1.0, max(i[2] for i in issues) + 0.1 * (len(issues) - 1))
        findings.append(Finding(
            id="", location=f"bullet {idx}", metric="+".join(i[0] for i in issues),
            value=len(issues), severity=round(severity, 2), snippet=bullet,
            detail="; ".join(i[3] for i in issues),
        ))
    findings.sort(key=lambda f: f.severity, reverse=True)
    findings = findings[:max_findings]
    for i, f in enumerate(findings, 1):
        f.id = f"f{i}"
    flagged = sum(1 for b in bullets if check_bullet(b))
    summary = {
        "bullets_found": len(bullets),
        "bullets_flagged": flagged,
        "pct_with_metrics": round(100 * sum(bool(NUMBER_RE.search(b)) for b in bullets)
                                  / len(bullets), 1) if bullets else 0,
    }
    return AnalysisResult(source_type="resume", findings=findings, summary=summary)


def analyze_resume(pdf_bytes: bytes, max_findings: int = 8) -> AnalysisResult:
    return analyze_bullets(extract_bullets(pdf_bytes), max_findings)
