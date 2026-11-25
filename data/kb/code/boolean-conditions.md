# Complex boolean conditions
Applies to: cyclomatic_complexity

`and` binds tighter than `or`, so `a and b or c` means `(a and b) or c`. Mixing them without parentheses hides the logic and invites bugs. Add explicit parentheses, use Python's chained comparisons (`0 < k < 100` instead of `k > 0 and k < 100`), or move a complex condition into a well-named helper or variable such as `is_valid = ...`.
