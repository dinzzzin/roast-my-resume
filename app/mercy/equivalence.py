"""Behavior-equivalence check for code rewrites.

ast.parse only proves a rewrite is valid Python. This module checks that it
still does the same thing: run the original and the rewrite on the same test
inputs and compare return values (or exception types).

Test inputs come from the LLM as Python literals and are parsed with
ast.literal_eval, which cannot execute code. The functions themselves run in a
separate, time- and memory-limited process (see _runner.py).
"""
import ast
import builtins
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from app.llm.provider import chat, extract_json

RUNNER = Path(__file__).with_name("_runner.py")
TIMEOUT_SECONDS = 10
MAX_CASES = 12


def enabled() -> bool:
    return os.getenv("EQUIVALENCE_CHECK", "true").lower() == "true"


@dataclass
class EquivalenceResult:
    equivalent: bool | None  # None = could not be tested
    cases_checked: int = 0
    mismatches: list[dict] = field(default_factory=list)
    note: str = ""


def _main_function(source: str, preferred: str | None = None) -> ast.FunctionDef | None:
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return None
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    for f in funcs:
        if f.name == preferred:
            return f
    return funcs[-1] if funcs else None  # helpers usually come first, the entry point last


def outside_names(func: ast.FunctionDef) -> list[str]:
    """Names the function reads that it never defines: imports, globals, other helpers."""
    bound = {func.name} | set(dir(builtins))
    for node in ast.walk(func):
        if isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            bound.update((a.asname or a.name).split(".")[0] for a in node.names)
    loaded = {n.id for n in ast.walk(func) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    return sorted(loaded - bound)


def untestable_reason(source: str) -> str | None:
    func = _main_function(source)
    if func is None:
        return "no top-level function found"
    missing = outside_names(func)
    if missing:
        return f"depends on code outside the snippet ({', '.join(missing)})"
    if func.args.args and func.args.args[0].arg in {"self", "cls"}:
        return "methods need a class instance"
    if any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(func)):
        return "generators are not compared"
    return None


def generate_cases(source: str) -> list[str]:
    """Ask the LLM for test inputs; keep only safe, parseable literal tuples."""
    prompt = (
        "Write test inputs for this Python function. Return ONLY JSON: "
        '{"cases": ["(arg1, arg2, ...)", ...]} where each case is a Python literal tuple '
        f"of positional arguments. Give {MAX_CASES - 2} to {MAX_CASES} cases: typical inputs, "
        "boundaries, empty collections, None values, and missing or None dictionary keys. "
        "Use only literals (numbers, strings, None, True/False, lists, tuples, dicts, sets).\n\n"
        f"{textwrap.dedent(source)}"
    )
    data = extract_json(chat([{"role": "user", "content": prompt}], temperature=0.2,
                             json_mode=True))
    cases = []
    for case in data.get("cases", [])[:MAX_CASES]:
        try:
            if isinstance(ast.literal_eval(case), tuple):
                cases.append(case)
        except (ValueError, SyntaxError, TypeError):
            continue  # not a literal: drop it rather than ever executing it
    return cases


def run_cases(original: str, revised: str, cases: list[str]) -> EquivalenceResult:
    original, revised = textwrap.dedent(original), textwrap.dedent(revised)
    orig_fn = _main_function(original)
    rev_fn = _main_function(revised, preferred=orig_fn.name if orig_fn else None)
    if not (orig_fn and rev_fn):
        return EquivalenceResult(None, note="could not find the function to compare")
    if not cases:
        return EquivalenceResult(None, note="no usable test inputs")

    n_defaults = len(orig_fn.args.defaults)
    payload = json.dumps({"original": original, "original_name": orig_fn.name,
                          "revised": revised, "revised_name": rev_fn.name, "cases": cases,
                          "required": len(orig_fn.args.args) - n_defaults,
                          "has_defaults": n_defaults > 0})
    with tempfile.TemporaryDirectory() as workdir:
        try:
            proc = subprocess.run([sys.executable, "-I", str(RUNNER)], input=payload,
                                  capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
                                  cwd=workdir)
        except subprocess.TimeoutExpired:
            return EquivalenceResult(None, note=f"timed out after {TIMEOUT_SECONDS}s")
    try:
        result = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return EquivalenceResult(None, note="test run crashed or hit its resource limit")
    if "load_error" in result:
        return EquivalenceResult(None, note=f"could not load functions: {result['load_error']}")

    runs = result["cases"]
    # Backstop for dependencies the static check can't see (e.g. names built dynamically).
    if runs and all(r["original"].get("error") == "NameError" for r in runs):
        return EquivalenceResult(None, note="function depends on code outside the snippet")

    mismatches = [{"input": r["input"], "original": _describe(r["original"]),
                   "revised": _describe(r["revised"])}
                  for r in runs if r["original"] != r["revised"]]
    # Same result per call, different result on a repeat call = shared state changed
    # (e.g. a mutable default argument was fixed). Reported, never fed back as an error,
    # because the retry loop would otherwise push the model to restore the bug.
    state_diffs = [r for r in runs if r["original"] == r["revised"]
                   and r["original_again"] != r["revised_again"]]
    notes = []
    if mismatches:
        notes.append(f"{len(mismatches)} of {len(runs)} inputs behave differently")
    default_diffs = [r for r in runs if "default_probe" in r
                     and r["default_probe"]["original"] != r["default_probe"]["revised"]]
    if state_diffs:
        r = state_diffs[0]
        notes.append(f"state changed: calling with {r['input']} then {r['follow_up']}, the original "
                     f"{_describe(r['original_again'])} but the rewrite "
                     f"{_describe(r['revised_again'])} (shared state was removed or added)")
    elif default_diffs:
        r = default_diffs[0]
        o, v = r["default_probe"]["original"], r["default_probe"]["revised"]
        notes.append(f"state changed: calling twice with default arguments, the original "
                     f"{_describe(o[1])} on the second call but the rewrite {_describe(v[1])} "
                     f"(shared state in a default argument was removed or added)")
    return EquivalenceResult(not mismatches, cases_checked=len(runs), mismatches=mismatches,
                             note="; ".join(notes))


def _describe(outcome: dict) -> str:
    return f"returned {outcome['value']}" if outcome["ok"] else f"raised {outcome['error']}"


def feedback_message(result: EquivalenceResult, limit: int = 3) -> str:
    lines = [f"- input {m['input']}: original {m['original']}, yours {m['revised']}"
             for m in result.mismatches[:limit]]
    return ("Your rewrite behaves differently from the original:\n" + "\n".join(lines)
            + "\nMake it behave exactly like the original on these inputs, including which "
              "exceptions are raised, and return the same JSON format.")
