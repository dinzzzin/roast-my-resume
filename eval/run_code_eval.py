"""Code-track evaluation: run every benchmark sample through the live API.

For each file in eval/code_samples/:
  1. /analyze/code  -> did the analyzer catch the labeled problem? (controls: no findings)
  2. /mercy         -> syntax-valid? behavior-equivalent? attempts? latency?
  3. /analyze/code on the rewrite -> did nesting/complexity/length actually drop?

Standard library only. Start the server first (docker run ... roast-api), then:

    python3 eval/run_code_eval.py
    python3 eval/run_code_eval.py --only 01,07     # just some samples

Writes eval/results/code_eval_<timestamp>.{csv,md,json}.
"""
import argparse
import csv
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
METRICS = ("nesting", "complexity", "length")
METRIC_FOR_FINDING = {"nesting_depth": "nesting", "cyclomatic_complexity": "complexity",
                      "function_length": "length"}


def call(api: str, path: str, body: dict | None = None, retries: int = 3) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(api + path, data=data, method="POST" if body else "GET",
                                 headers={"Content-Type": "application/json"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            payload = json.loads(e.read() or b"{}")
            rate_limited = e.code == 502 and "RateLimit" in payload.get("detail", "")
            if rate_limited and attempt < retries:
                wait = 30 * (attempt + 1)
                print(f"    rate limited, waiting {wait}s...", flush=True)
                time.sleep(wait)
                continue
            return e.code, payload
    return 0, {}


def function_name(location: str) -> str | None:
    m = re.search(r"\((\w+)\)$", location)
    return m.group(1) if m else None


def worst(functions: list[dict]) -> dict:
    return {m: max((f[m] for f in functions), default=0) for m in METRICS}


def evaluate_sample(api: str, path: Path) -> dict:
    src = path.read_text()
    label = re.search(r"Expected:\s*(.+)", src)
    expected = {x.strip() for x in label.group(1).split(",")} - {"none"} if label else set()
    row: dict = {"sample": path.stem, "expected": ", ".join(sorted(expected)) or "none"}

    status, analysis = call(api, "/analyze/code", {"code": src})
    if status != 200:
        return {**row, "error": f"analyze {status}: {analysis.get('detail')}"}
    found = {f["metric"] for f in analysis["findings"]}
    row.update(found=", ".join(sorted(found)) or "none",
               caught=expected <= found if expected else None,
               false_alarm=bool(found) if not expected else None,
               extra=", ".join(sorted(found - expected)))
    if not analysis["findings"]:
        return row

    start = time.time()
    status, mercy = call(api, "/mercy", {"analysis": analysis})
    row["mercy_seconds"] = round(time.time() - start, 1)
    if status != 200:
        return {**row, "error": f"mercy {status}: {mercy.get('detail')}"}

    items = []
    by_id = {f["id"]: f for f in analysis["findings"]}
    for item in mercy["items"]:
        finding = by_id[item["finding_id"]]
        name = function_name(finding["location"])
        before = worst([f for f in analysis["summary"]["functions"] if f["name"] == name])
        targeted = {f["metric"] for f in analysis["findings"] if f["snippet"] == finding["snippet"]}
        result = {"valid": item["valid"], "equivalent": item.get("equivalent"),
                  "attempts": item["attempts"], "cases": item.get("cases_checked", 0),
                  "note": item.get("equivalence_note", ""), "before": before,
                  "revised": item["revised"], "explanation": item.get("explanation", ""),
                  "mismatches": item.get("mismatches", []),
                  "targeted": sorted(targeted)}
        if item["valid"]:
            s2, after = call(api, "/analyze/code", {"code": item["revised"]})
            if s2 == 200:
                result["after"] = worst(after["summary"]["functions"])
                remaining = {f["metric"] for f in after["findings"]}
                result["resolved"] = sorted(targeted - remaining)
                result["unresolved"] = sorted(targeted & remaining)
        items.append(result)
    row["items"] = items
    return row


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "n/a"


def summarize(rows: list[dict], meta: dict) -> str:
    labeled = [r for r in rows if r.get("caught") is not None]
    controls = [r for r in rows if r.get("false_alarm") is not None]
    items = [i for r in rows for i in r.get("items", [])]
    tested = [i for i in items if i["equivalent"] is not None]
    measured = [i for i in items if "after" in i]
    targeted = sum(len(i["targeted"]) for i in measured)
    resolved = sum(len(i["resolved"]) for i in measured)
    latencies = [r["mercy_seconds"] for r in rows if "mercy_seconds" in r]

    out = [f"# Code-track evaluation, {meta['when']}", "",
           f"Model: `{meta['model']}` · {len(rows)} samples · {meta['api']}", "",
           "## Analyzer", "",
           "| Metric | Result |", "|---|---|",
           f"| Labeled problem caught | {pct(sum(r['caught'] for r in labeled), len(labeled))} |",
           f"| Clean controls with no findings | "
           f"{pct(sum(not r['false_alarm'] for r in controls), len(controls))} |",
           f"| Samples with extra findings | {sum(1 for r in labeled if r.get('extra'))} |", "",
           "## Mercy rewrites", "",
           "| Metric | Result |", "|---|---|",
           f"| Syntax-valid | {pct(sum(i['valid'] for i in items), len(items))} |",
           f"| Behavior-equivalent (of testable) | "
           f"{pct(sum(i['equivalent'] is True for i in tested), len(tested))} |",
           f"| Not testable | {len(items) - len(tested)} |",
           f"| Shared-state changes flagged | "
           f"{sum(1 for i in items if 'state changed' in i['note'])} |",
           f"| Fixed by the retry loop | "
           f"{sum(1 for i in tested if i['equivalent'] and i['attempts'] > 1)} |",
           f"| Average attempts | "
           f"{statistics.mean(i['attempts'] for i in items):.2f} |" if items else "",
           f"| Median mercy latency | {statistics.median(latencies):.1f}s |" if latencies else "",
           f"| Targeted findings resolved | {pct(resolved, targeted)} |", "",
           "## Before vs. after (worst function)", "",
           "| Metric | Before (avg) | After (avg) |", "|---|---|---|"]
    for m in METRICS:
        if measured:
            b = statistics.mean(i["before"][m] for i in measured)
            a = statistics.mean(i["after"][m] for i in measured)
            out.append(f"| {m} | {b:.1f} | {a:.1f} |")
    out += ["", "## Per sample", "",
            "| Sample | Expected | Found | Valid | Equivalent | Attempts | Resolved | Note |",
            "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r.get("error"):
            out.append(f"| {r['sample']} | {r['expected']} | ERROR | | | | | {r['error']} |")
            continue
        its = r.get("items") or [{}]
        for i in its:
            eq = {True: "yes", False: "NO", None: "n/a"}[i.get("equivalent")] if i else ""
            out.append(f"| {r['sample']} | {r['expected']} | {r.get('found', '')} | "
                       f"{'yes' if i.get('valid') else ('' if not i else 'NO')} | {eq} | "
                       f"{i.get('attempts', '')} | {', '.join(i.get('resolved', [])) or ''} | "
                       f"{i.get('note', '')} |")
    return "\n".join(line for line in out if line is not None) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--samples", default=str(HERE / "code_samples"))
    parser.add_argument("--only", help="comma-separated sample prefixes, e.g. 01,07")
    parser.add_argument("--delay", type=float, default=3, help="seconds between samples")
    parser.add_argument("--allow-demo", action="store_true", help="run against demo mode")
    args = parser.parse_args()

    try:
        _, health = call(args.api, "/health")
    except urllib.error.URLError:
        sys.exit(f"Can't reach {args.api}. Is the Docker server running?")
    if health.get("mode") != "live" and not args.allow_demo:
        sys.exit("Server is in demo mode, so mercy results would be meaningless. Start it "
                 "with --env-file .env (or pass --allow-demo for a smoke test).")

    paths = sorted(Path(args.samples).glob("*.py"))
    if args.only:
        prefixes = tuple(p.strip() for p in args.only.split(","))
        paths = [p for p in paths if p.name.startswith(prefixes)]

    rows = []
    for n, path in enumerate(paths, 1):
        print(f"[{n}/{len(paths)}] {path.stem}", flush=True)
        row = evaluate_sample(args.api, path)
        rows.append(row)
        for i in row.get("items", []):
            print(f"    valid={i['valid']} equivalent={i['equivalent']} attempts={i['attempts']}"
                  + (f" note={i['note'][:80]}" if i["note"] else ""), flush=True)
        if row.get("error"):
            print(f"    ERROR {row['error'][:120]}", flush=True)
        if n < len(paths):
            time.sleep(args.delay)

    meta = {"when": datetime.now().strftime("%Y-%m-%d %H:%M"), "api": args.api,
            "model": health.get("model") or health.get("mode")}
    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    (out_dir / f"code_eval_{stamp}.json").write_text(json.dumps({"meta": meta, "rows": rows},
                                                                 indent=1))
    with open(out_dir / f"code_eval_{stamp}.csv", "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["sample", "expected", "found", "caught", "valid", "equivalent",
                         "attempts", "cases", "resolved", "unresolved", "mercy_seconds",
                         *[f"{m}_before" for m in METRICS], *[f"{m}_after" for m in METRICS],
                         "note", "error"])
        for r in rows:
            for i in r.get("items") or [{}]:
                writer.writerow([r["sample"], r["expected"], r.get("found"), r.get("caught"),
                                 i.get("valid"), i.get("equivalent"), i.get("attempts"),
                                 i.get("cases"), ";".join(i.get("resolved", [])),
                                 ";".join(i.get("unresolved", [])), r.get("mercy_seconds"),
                                 *[i.get("before", {}).get(m) for m in METRICS],
                                 *[i.get("after", {}).get(m) for m in METRICS],
                                 i.get("note"), r.get("error")])
    summary = summarize(rows, meta)
    (out_dir / f"code_eval_{stamp}.md").write_text(summary)
    print("\n" + summary)
    print(f"Saved eval/results/code_eval_{stamp}.{{md,csv,json}}")


if __name__ == "__main__":
    main()
