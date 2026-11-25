"""FastAPI entry point. Routes only — logic lives in analyzers/, llm/, mercy/."""
import json

from fastapi import FastAPI, Request, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from openai import APIError

from app.analyzers.code_metrics import analyze_code
from app.analyzers.resume_parser import analyze_resume
from app.llm.personas import PERSONAS
from app.llm.provider import is_demo_mode, model_name, provider_name
from app.llm.roast import generate_roast
from app.mercy.rewrite import generate_mercy
from app.schemas import (AnalysisResult, AnalyzeCodeRequest, MercyRequest, MercyResponse,
                         Persona, RoastRequest, RoastResponse)

app = FastAPI(
    title="Roast-My-Code & Resume API",
    description="Grounded AI roasts of Python code and resumes, plus validated 'mercy' fixes. "
                "Typical flow: /analyze/* → /roast → /mercy.",
    version="0.1.0",
)


@app.exception_handler(APIError)
async def llm_provider_error(request: Request, exc: APIError):
    """Turn LLM provider failures (bad key, retired model, rate limit) into readable 502s."""
    return JSONResponse(status_code=502, content={
        "detail": f"LLM provider error ({type(exc).__name__}): {exc.message}",
        "hint": "Check /health and the API key / LLM_MODEL in .env, or set DEMO_MODE=true."})


@app.exception_handler(json.JSONDecodeError)
async def llm_bad_json(request: Request, exc: json.JSONDecodeError):
    return JSONResponse(status_code=502, content={
        "detail": "The LLM returned malformed JSON. Try the request again."})


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    demo = is_demo_mode()
    return {"status": "ok", "mode": "demo" if demo else "live",
            "provider": None if demo else provider_name(),
            "model": None if demo else model_name()}


@app.get("/personas", response_model=list[Persona])
def personas():
    return [Persona(id=k, name=v["name"], description=v["description"])
            for k, v in PERSONAS.items()]


@app.post("/analyze/code", response_model=AnalysisResult)
def analyze_code_endpoint(req: AnalyzeCodeRequest):
    try:
        return analyze_code(code=req.code, repo_url=req.repo_url, max_findings=req.max_findings)
    except SyntaxError as e:
        raise HTTPException(422, f"Could not parse Python: {e.msg} (line {e.lineno})")
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:  # network / GitHub errors
        raise HTTPException(502, f"Could not fetch repository: {e}")


@app.post("/analyze/resume", response_model=AnalysisResult)
async def analyze_resume_endpoint(file: UploadFile = File(..., description="Resume PDF"),
                                  max_findings: int = Query(8, ge=1, le=25)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(415, "Please upload a PDF.")
    try:
        return analyze_resume(await file.read(), max_findings=max_findings)
    except Exception as e:
        raise HTTPException(422, f"Could not read PDF: {e}")


@app.post("/roast", response_model=RoastResponse)
def roast(req: RoastRequest):
    if req.persona not in PERSONAS:
        raise HTTPException(404, f"Unknown persona. Options: {list(PERSONAS)}")
    if not req.analysis.findings:
        raise HTTPException(422, "Nothing to roast — the analyzer found no problems. Impressive.")
    return generate_roast(req.analysis, req.persona)


@app.post("/mercy", response_model=MercyResponse)
def mercy(req: MercyRequest):
    return generate_mercy(req.analysis, req.finding_ids)
