# Deep nesting
Applies to: nesting_depth

Code nested more than three levels deep forces the reader to hold every enclosing condition in their head at once. Flatten it with guard clauses: check the failure case first and `continue` or `return` early, so the main logic stays at a shallow indent. Extracting the inner block into a helper function is the other main tool.

Bad:
```python
for item in items:
    if item is not None:
        if item.active:
            process(item)
```

Good:
```python
for item in items:
    if item is None or not item.active:
        continue
    process(item)
```
