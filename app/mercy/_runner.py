"""Child process for the behavior-equivalence check. Standard library only.

Launched with `python -I` (isolated mode) by equivalence.py, in a temp working
directory, with CPU and memory limits. Reads a JSON payload on stdin, runs the
original and revised function on every case, prints one JSON result.

Not a security sandbox: it limits accidents (infinite loops, memory blow-ups,
stray files), not a determined attacker.
"""
import ast
import io
import json
import sys


def _limit_resources(cpu_seconds: int, memory_mb: int) -> None:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        limit = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (ImportError, ValueError, OSError):
        pass  # not available on every OS; the parent's timeout still applies


def _load(source: str, name: str):
    namespace: dict = {"__name__": "__mercy_check__"}
    exec(compile(source, "<submitted>", "exec"), namespace)  # noqa: S102
    return namespace[name]


def _outcome(func, case_src: str, keep: int | None = None) -> dict:
    args = ast.literal_eval(case_src)  # fresh copy per call: functions may mutate inputs
    if keep is not None:
        args = args[:keep]  # drop optional arguments so their defaults are used
    try:
        return {"ok": True, "value": repr(func(*args))}
    except Exception as e:  # noqa: BLE001 - recording the exception IS the result
        return {"ok": False, "error": type(e).__name__}


def main() -> None:
    payload = json.load(sys.stdin)
    _limit_resources(payload.get("cpu_seconds", 5), payload.get("memory_mb", 512))
    real_stdout = sys.stdout
    sys.stdout = io.StringIO()  # swallow anything the submitted code prints
    result: dict = {"cases": []}
    try:
        cases = payload["cases"]
        for n, case in enumerate(cases):
            # Fresh copies per input, so state can't leak from one case into the next.
            # Then a follow-up call with the NEXT input on the same copies: if the original
            # kept state from the first call (e.g. a mutable default), the results differ.
            follow_up = cases[(n + 1) % len(cases)]
            original = _load(payload["original"], payload["original_name"])
            revised = _load(payload["revised"], payload["revised_name"])
            result["cases"].append({
                "input": case, "follow_up": follow_up,
                "original": _outcome(original, case), "revised": _outcome(revised, case),
                "original_again": _outcome(original, follow_up),
                "revised_again": _outcome(revised, follow_up)})
            if payload.get("has_defaults"):
                # Same two-call probe, but relying on default arguments. Test inputs often
                # pass every argument explicitly, which hides a buggy mutable default.
                keep = payload["required"]
                original = _load(payload["original"], payload["original_name"])
                revised = _load(payload["revised"], payload["revised_name"])
                result["cases"][-1]["default_probe"] = {
                    "original": [_outcome(original, case, keep), _outcome(original, follow_up, keep)],
                    "revised": [_outcome(revised, case, keep), _outcome(revised, follow_up, keep)]}
    except Exception as e:  # noqa: BLE001
        result["load_error"] = f"{type(e).__name__}: {e}"
    sys.stdout = real_stdout
    print(json.dumps(result))


if __name__ == "__main__":
    main()
