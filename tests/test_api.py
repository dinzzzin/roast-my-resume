"""Smoke tests — run with `pytest`. They force demo mode so no API key is needed."""
import io
import os
from pathlib import Path

os.environ["DEMO_MODE"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.analyzers.resume_parser import analyze_bullets  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
SAMPLES = Path(__file__).parent.parent / "data" / "samples"
BAD_CODE = (SAMPLES / "bad_code.py").read_text()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["mode"] == "demo"


def test_personas():
    ids = {p["id"] for p in client.get("/personas").json()}
    assert {"gordon_ramsay", "faang_recruiter", "tired_senior_dev"} <= ids


def test_analyze_code_finds_problems():
    r = client.post("/analyze/code", json={"code": BAD_CODE})
    assert r.status_code == 200
    metrics = {f["metric"] for f in r.json()["findings"]}
    assert "nesting_depth" in metrics and "naming" in metrics
    assert all("ok_function" not in f["location"] for f in r.json()["findings"])


def test_analyze_code_rejects_bad_syntax():
    assert client.post("/analyze/code", json={"code": "def broken(:"}).status_code == 422


def test_analyze_code_requires_input():
    assert client.post("/analyze/code", json={}).status_code == 422


def test_bullet_rules():
    bullets = (SAMPLES / "bullets.txt").read_text().splitlines()
    result = analyze_bullets(bullets)
    flagged = {f.snippet for f in result.findings}
    assert bullets[0] in flagged and bullets[1] in flagged
    assert bullets[2] not in flagged  # the strong bullet passes


def test_analyze_resume_pdf():
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i, line in enumerate(["EXPERIENCE", "• Helped the team with things",
                              "• Led migration to AWS, cutting cost 32% for 1.2M users"]):
        c.drawString(72, 750 - 20 * i, line)
    c.save()
    r = client.post("/analyze/resume", files={"file": ("cv.pdf", buf.getvalue(), "application/pdf")})
    assert r.status_code == 200
    assert r.json()["summary"]["bullets_found"] == 2
    assert len(r.json()["findings"]) == 1


def test_full_flow_roast_and_mercy():
    analysis = client.post("/analyze/code", json={"code": BAD_CODE}).json()
    roast = client.post("/roast", json={"analysis": analysis, "persona": "tired_senior_dev"})
    assert roast.status_code == 200
    assert len(roast.json()["roast"]) == len(analysis["findings"])
    mercy = client.post("/mercy", json={"analysis": analysis})
    assert mercy.status_code == 200 and all(i["valid"] for i in mercy.json()["items"])


def test_unknown_persona():
    analysis = client.post("/analyze/code", json={"code": BAD_CODE}).json()
    assert client.post("/roast", json={"analysis": analysis, "persona": "nobody"}).status_code == 404


def test_elif_does_not_inflate_nesting():
    from app.analyzers.code_metrics import analyze_source
    src = "def f(a):\n    if a: pass\n    elif a > 1: pass\n    elif a > 2:\n        if a > 3: pass\n"
    assert analyze_source(src)[0].nesting == 2


def test_lambda_and_comprehension_names_are_not_flagged():
    from app.analyzers.code_metrics import analyze_source
    src = ("def f(rows, d):\n    out = sorted(rows, key=lambda p: p[1])\n"
           "    return [v for v in out if v]\n")
    stats = analyze_source(src)[0]
    assert stats.bad_names == ["d"]  # the real parameter is still caught


def test_indented_method_snippet_is_analyzed():
    method = "    def run(self, xs):\n        for x in xs:\n            if x:\n                if x > 1:\n                    if x > 2:\n                        print(x)\n"
    r = client.post("/analyze/code", json={"code": method})
    assert r.status_code == 200 and r.json()["summary"]["functions"][0]["nesting"] == 4
