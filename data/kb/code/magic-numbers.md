# Magic numbers
Applies to: cyclomatic_complexity, naming

Unexplained literals such as 100, 3 or 0.07 scattered through code are "magic numbers". The reader cannot tell why that value, and changing it means hunting every copy. Give them a named constant at module level: `MAX_ITEM_VALUE = 100`. Exceptions are obvious values like 0, 1 and -1 used in their ordinary sense.
