"""Deterministic code analysis with Python's ast module.

Measures every function, turns threshold breaches into Findings, and keeps
only the worst ones — those are what the persona roasts.
"""
import ast
import io
import zipfile
from dataclasses import dataclass

import httpx

from app.schemas import AnalysisResult, Finding

# Thresholds — tune these and cite them in the report.
MAX_FUNC_LINES = 40
MAX_NESTING = 3
MAX_COMPLEXITY = 10
OK_SHORT_NAMES = {"i", "j", "k", "x", "y", "z", "n", "_", "e", "f", "df"}
MAX_FILES = 40
MAX_FILE_BYTES = 200_000

NESTING_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)
BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.With,
                ast.AsyncWith, ast.IfExp, ast.comprehension, ast.Assert)


@dataclass
class FunctionStats:
    file: str
    name: str
    start: int
    end: int
    length: int
    nesting: int
    complexity: int
    bad_names: list[str]
    source: str


def _is_elif(parent: ast.AST, child: ast.AST) -> bool:
    """ast stores `elif` as an If inside the parent If's orelse — same visual level."""
    return (isinstance(parent, ast.If) and isinstance(child, ast.If)
            and len(parent.orelse) == 1 and parent.orelse[0] is child)


def _max_nesting(node: ast.AST, depth: int = 0) -> int:
    best = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue  # nested defs are measured on their own
        if _is_elif(node, child):
            d = depth  # node already counted this level
        else:
            d = depth + 1 if isinstance(child, NESTING_NODES) else depth
        best = max(best, _max_nesting(child, d))
    return best


def _complexity(node: ast.AST) -> int:
    """McCabe-style approximation: 1 + branches + extra boolean operands."""
    score = 1
    for child in ast.walk(node):
        if isinstance(child, BRANCH_NODES):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += len(child.values) - 1
        elif isinstance(child, ast.match_case):
            score += 1
    return score


def _bad_names(func: ast.AST) -> list[str]:
    names = set()
    for child in ast.walk(func):
        if isinstance(child, ast.arg):
            names.add(child.arg)
        elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
            names.add(child.id)
    bad = [n for n in names if (len(n) <= 2 and n not in OK_SHORT_NAMES)
           or n.lower() in {"data", "temp", "tmp", "stuff", "thing", "foo", "bar", "obj"}]
    return sorted(bad)


def analyze_source(source: str, filename: str = "snippet.py") -> list[FunctionStats]:
    tree = ast.parse(source)
    lines = source.splitlines()
    stats = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            stats.append(FunctionStats(
                file=filename, name=node.name, start=node.lineno, end=end,
                length=end - node.lineno + 1,
                nesting=_max_nesting(node),
                complexity=_complexity(node),
                bad_names=_bad_names(node),
                source="\n".join(lines[node.lineno - 1:end]),
            ))
    return stats


def _findings_for(fs: FunctionStats) -> list[Finding]:
    loc = f"{fs.file}:{fs.start}-{fs.end} ({fs.name})"
    out = []
    checks = [
        ("function_length", fs.length, MAX_FUNC_LINES, f"{fs.length} lines long"),
        ("nesting_depth", fs.nesting, MAX_NESTING, f"nested {fs.nesting} levels deep"),
        ("cyclomatic_complexity", fs.complexity, MAX_COMPLEXITY, f"complexity {fs.complexity}"),
    ]
    for metric, value, limit, detail in checks:
        if value > limit:
            severity = min(1.0, (value - limit) / limit + 0.3)
            out.append(Finding(id="", location=loc, metric=metric, value=value, threshold=limit,
                               severity=round(severity, 2), snippet=fs.source, detail=detail))
    if fs.bad_names:
        out.append(Finding(id="", location=loc, metric="naming", value=", ".join(fs.bad_names),
                           severity=round(min(1.0, 0.2 + 0.1 * len(fs.bad_names)), 2), snippet=fs.source,
                           detail=f"unhelpful names: {', '.join(fs.bad_names)}"))
    return out


def fetch_repo_python_files(repo_url: str) -> dict[str, str]:
    """Download a public GitHub repo's default branch and return {path: source}."""
    parts = repo_url.rstrip("/").removesuffix(".git").split("github.com/")[-1].split("/")
    if len(parts) < 2:
        raise ValueError("repo_url must look like https://github.com/owner/repo")
    owner, repo = parts[0], parts[1]
    resp = httpx.get(f"https://api.github.com/repos/{owner}/{repo}/zipball",
                     follow_redirects=True, timeout=30)
    resp.raise_for_status()
    files = {}
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for info in zf.infolist():
            name = info.filename.split("/", 1)[-1]  # strip the "owner-repo-sha/" prefix
            if (name.endswith(".py") and info.file_size <= MAX_FILE_BYTES
                    and not any(p in name for p in ("test", "venv", "site-packages", "migrations"))):
                files[name] = zf.read(info).decode("utf-8", errors="ignore")
            if len(files) >= MAX_FILES:
                break
    return files


def analyze_code(code: str | None = None, repo_url: str | None = None,
                 max_findings: int = 8) -> AnalysisResult:
    sources = fetch_repo_python_files(repo_url) if repo_url else {"snippet.py": code or ""}
    all_stats, skipped = [], []
    for path, src in sources.items():
        try:
            all_stats.extend(analyze_source(src, path))
        except SyntaxError:
            if not repo_url:
                raise  # pasted code must parse; in a repo we just skip the bad file
            skipped.append(path)

    findings = [f for fs in all_stats for f in _findings_for(fs)]
    findings.sort(key=lambda f: f.severity, reverse=True)
    findings = findings[:max_findings]
    for i, f in enumerate(findings, 1):
        f.id = f"f{i}"

    summary = {
        "files_analyzed": len(sources) - len(skipped),
        "files_skipped_syntax_error": skipped,
        "functions_analyzed": len(all_stats),
        "avg_complexity": round(sum(s.complexity for s in all_stats) / len(all_stats), 2)
        if all_stats else 0,
        "worst_function": max(all_stats, key=lambda s: s.complexity).name if all_stats else None,
    }
    return AnalysisResult(source_type="code", findings=findings, summary=summary)
