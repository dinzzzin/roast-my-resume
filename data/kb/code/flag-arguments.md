# Boolean flag arguments
Applies to: naming, cyclomatic_complexity, function_length

A boolean parameter that switches a function between two different behaviors (`process(data, flag)`) usually means the function does two jobs. Callers write `process(x, True)`, which is unreadable at the call site. Split it into two functions with clear names, or at least make the flag a keyword-only argument with a descriptive name.

Bad: `def export(data, flag): ...`

Good: `def export_csv(data): ...` and `def export_json(data): ...`
