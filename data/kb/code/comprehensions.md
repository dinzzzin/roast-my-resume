# Comprehensions instead of append loops
Applies to: function_length, nesting_depth

A loop whose only job is to build a list with `.append()` is clearer as a list comprehension, which removes a level of nesting and an accumulator variable. Keep comprehensions simple: one loop and one condition. If it needs nested loops or several conditions, a regular loop or a helper function reads better.

Bad:
```python
result = []
for x in values:
    if x > 0:
        result.append(x * 2)
```

Good: `result = [x * 2 for x in values if x > 0]`
