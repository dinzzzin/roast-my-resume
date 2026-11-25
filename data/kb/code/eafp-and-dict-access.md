# Dictionary access and KeyError
Applies to: nesting_depth, cyclomatic_complexity

Use `dict.get(key, default)` when a missing key is normal and has a sensible default. Use `dict[key]` when the key must exist, so a missing key fails loudly instead of being silently skipped. Changing one into the other changes behavior: code that used to raise KeyError will now continue quietly. Make that choice on purpose, and say so when refactoring.
