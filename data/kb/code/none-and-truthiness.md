# Comparisons to None and truthiness
Applies to: naming, cyclomatic_complexity

PEP 8: compare to singletons like None with `is` or `is not`, never `==`. Write `if x is not None`, not `if not x is None`. For sequences, use truthiness: `if items:` rather than `if len(items) > 0:`. But be careful: `if value:` is also false for 0 and empty strings, so use `is not None` when those are valid values.
