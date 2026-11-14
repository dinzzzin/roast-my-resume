# Roast-My-Code & Resume Assistant

Grounded AI roasts of Python code and resumes, delivered by comedic personas, plus
validated "Have Mercy" fixes. The roast is not generic. Before any LLM call, a
deterministic analyzer measures the submission (AST complexity, nesting, naming;
resume bullet strength). The persona can only joke about problems that were actually
measured.

## Run it (Docker)

```bash
docker build -t roast-api .
cp .env.example .env        # optional: add ONE free API key (Groq recommended)
docker run --rm -p 8000:8000 --env-file .env roast-api
```

Then open **http://localhost:8000/docs** to try every endpoint in the browser.

**No API key?** The server starts in demo mode. Every endpoint still responds,
the analyzers run for real, and roast/mercy return canned text. `GET /health`
shows which mode is active.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Status, mode (live/demo), provider |
| GET | `/personas` | Available reviewers |
| POST | `/analyze/code` | AST metrics for pasted code or a public GitHub repo (no LLM) |
| POST | `/analyze/resume` | Upload a PDF, get bullet-level weakness findings (no LLM) |
| POST | `/roast` | Analysis + persona, returns a grounded roast |
| POST | `/mercy` | Analysis, returns before/after rewrites, validated (`ast.parse` for code) |

### Example

```bash
# 1. Analyze
curl -s -X POST localhost:8000/analyze/code \
  -H "Content-Type: application/json" \
  -d '{"code": "def f(d):\n    for x in d:\n        if x:\n            if x > 1:\n                if x > 2:\n                    print(x)"}' \
  > analysis.json

# 2. Roast (wrap the analysis with a persona)
python3 -c "import json;print(json.dumps({'analysis':json.load(open('analysis.json')),'persona':'tired_senior_dev'}))" \
  | curl -s -X POST localhost:8000/roast -H "Content-Type: application/json" -d @-

# Resume
curl -s -X POST localhost:8000/analyze/resume -F "file=@my_resume.pdf"
```

## Project structure

```
app/
  main.py              FastAPI routes only
  schemas.py           Pydantic models: the JSON contract between all modules
  analyzers/           code_metrics.py (ast), resume_parser.py (pdfplumber)
  llm/                 provider.py (multi-provider + demo mode), personas.py, roast.py
  mercy/               rewrite.py (validate-and-retry loop), validate.py
  rag/                 retriever.py (FAISS index, week 2)
data/samples/          test inputs
eval/                  evaluation harness (week 4)
tests/                 pytest smoke tests (run in demo mode, no key needed)
```

## Development

```bash
pip install -r requirements-dev.txt
pytest
uvicorn app.main:app --reload
```

## Roadmap

- [x] Week 1: JSON contract, analyzers, provider + demo mode, all endpoints, Docker
- [ ] Week 2: RAG knowledge bases (PEP 8, action verbs) + FAISS index built in Docker
- [ ] Week 3: LangGraph router for persona/source routing, live roast + mercy tuning
- [ ] Week 4: Eval harness: rule checks, LLM-as-judge with human calibration, safety
- [ ] Week 5: Report, presentation, video
