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


def _outcome(func, case_src: str) -> dict:
    args = ast.literal_eval(case_src)  # fresh copy per call: functions may mutate inputs
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
        original = _load(payload["original"], payload["original_name"])
        revised = _load(payload["revised"], payload["revised_name"])
        for case in payload["cases"]:
            result["cases"].append({"input": case, "original": _outcome(original, case),
                                    "revised": _outcome(revised, case)})
    except Exception as e:  # noqa: BLE001
        result["load_error"] = f"{type(e).__name__}: {e}"
    sys.stdout = real_stdout
    print(json.dumps(result))


if __name__ == "__main__":
    main()
