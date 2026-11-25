"""Behavior-equivalence check. Uses the two real mercy rewrites from our live runs."""
import json
import os
from pathlib import Path

os.environ["DEMO_MODE"] = "true"

import pytest  # noqa: E402

from app.mercy import equivalence, rewrite  # noqa: E402
from app.schemas import Finding  # noqa: E402

ORIGINAL = (Path(__file__).parent.parent / "data" / "samples" / "bad_code.py").read_text()
ORIGINAL = ORIGINAL.split("\n\n\ndef ok_function")[0]  # just process()

# Live mercy output BEFORE RAG: swapped strict x["type"] for .get(), silently skipping.
PRE_RAG = '''def process(d, t, flag):
    result = []
    for entry in d:
        if entry is None:
            continue
        if flag:
            if entry.get("type") != t:
                continue
            for k in entry.get("items", []):
                if (0 < k < 100) or k == -1:
                    result.append(k)
                elif k >= 100:
                    result.append(k // 2 if k % 2 == 0 else k * 3 + 1)
        else:
            items = entry.get("items")
            if items is not None:
                result.extend(items)
    return result'''

# Live mercy output AFTER RAG: strict where the original was strict, but skips items=None.
POST_RAG = '''def process(d, t, flag):
    result = []
    for entry in d:
        if entry is None:
            continue
        if flag:
            if entry["type"] != t:
                continue
            items = entry["items"]
            for k in items:
                if (0 < k < 100) or k == -1:
                    result.append(k)
                elif k >= 100:
                    result.append(k // 2 if k % 2 == 0 else k * 3 + 1)
        else:
            items = entry.get("items")
            if items is not None:
                result.extend(items)
    return result'''

TYPICAL = ["([{'type': 'a', 'items': [1, 150, 151, -5, -1]}], 'a', True)",
           "([None, {'type': 'b', 'items': [7]}], 'b', True)",
           "([{'items': [1, 2]}], 'a', False)",
           "([], 'a', True)"]
MISSING_TYPE = "([{'items': [5]}], 'a', True)"
ITEMS_NONE = "([{'type': 'a', 'items': None}], 'a', False)"


def test_typical_inputs_match_for_both_rewrites():
    for revised in (PRE_RAG, POST_RAG):
        result = equivalence.run_cases(ORIGINAL, revised, TYPICAL)
        assert result.equivalent is True and result.cases_checked == len(TYPICAL)


def test_catches_pre_rag_keyerror_change():
    result = equivalence.run_cases(ORIGINAL, PRE_RAG, TYPICAL + [MISSING_TYPE])
    assert result.equivalent is False
    assert result.mismatches == [{"input": MISSING_TYPE, "original": "raised KeyError",
                                  "revised": "returned []"}]


def test_post_rag_fixes_keyerror_but_misses_items_none():
    assert equivalence.run_cases(ORIGINAL, POST_RAG, [MISSING_TYPE]).equivalent is True
    result = equivalence.run_cases(ORIGINAL, POST_RAG, [ITEMS_NONE])
    assert result.equivalent is False
    assert result.mismatches[0]["original"] == "raised TypeError"


def test_printing_code_does_not_break_the_runner():
    noisy = "def f(x):\n    print('hello', x)\n    return x * 2\n"
    assert equivalence.run_cases(noisy, "def f(x):\n    return x + x\n", ["(3,)"]).equivalent


def test_outside_dependencies_are_untestable():
    src = "def f(x):\n    return helper(x)\n"
    result = equivalence.run_cases(src, src, ["(1,)", "(2,)"])
    assert result.equivalent is None and "outside the snippet" in result.note


def test_infinite_loop_times_out(monkeypatch):
    monkeypatch.setattr(equivalence, "TIMEOUT_SECONDS", 2)
    result = equivalence.run_cases("def f(x):\n    while True:\n        pass\n",
                                   "def f(x):\n    return x\n", ["(1,)"])
    assert result.equivalent is None and "timed out" in result.note


def test_methods_and_generators_are_skipped():
    assert "class instance" in equivalence.untestable_reason("    def m(self, x):\n        return x\n")
    assert "generators" in equivalence.untestable_reason("def g(n):\n    yield n\n")
    assert equivalence.untestable_reason(ORIGINAL) is None


def test_generated_cases_only_keep_safe_literals(monkeypatch):
    reply = json.dumps({"cases": ["(1, 2)", "__import__('os').system('ls')", "[1, 2]", "(None,)"]})
    monkeypatch.setattr(equivalence, "chat", lambda *a, **k: reply)
    assert equivalence.generate_cases("def f(a, b=None): pass") == ["(1, 2)", "(None,)"]


def test_mercy_retries_until_behavior_matches(monkeypatch):
    """First rewrite changes behavior; the loop feeds back the mismatch; second one is right."""
    replies = iter([json.dumps({"revised": PRE_RAG, "explanation": "v1"}),
                    json.dumps({"revised": ORIGINAL.replace("r = []", "r = list()"),
                                "explanation": "v2"})])
    sent = []

    def fake_chat(messages, **kwargs):
        sent.append(messages[-1]["content"])
        return next(replies)
    monkeypatch.setattr(rewrite, "chat", fake_chat)
    monkeypatch.setattr(rewrite, "retrieve", lambda *a, **k: "")
    monkeypatch.setattr(equivalence, "chat",
                        lambda *a, **k: json.dumps({"cases": TYPICAL + [MISSING_TYPE]}))
    finding = Finding(id="f1", location="x", metric="nesting_depth", value=7, severity=1.0,
                      snippet=ORIGINAL, detail="nested 7 levels deep")
    item = rewrite._rewrite_one(finding, "code")
    assert item.attempts == 2 and item.equivalent is True and item.explanation == "v2"
    assert "raised KeyError" in sent[1]  # the mismatch was fed back to the model
