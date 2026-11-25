# Cyclomatic complexity
Applies to: cyclomatic_complexity

Cyclomatic complexity counts the independent paths through a function: every if, elif, loop, except and boolean operator adds one. Above about 10, a function becomes hard to test because each path needs its own test case. Reduce it by extracting branches into helpers, replacing long if/elif chains with a dictionary lookup, and using early returns.

Bad:
```python
if kind == "a": rate = 1
elif kind == "b": rate = 2
elif kind == "c": rate = 5
```

Good:
```python
RATES = {"a": 1, "b": 2, "c": 5}
rate = RATES[kind]
```
