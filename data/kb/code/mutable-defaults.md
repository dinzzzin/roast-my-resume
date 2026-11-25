# Mutable default arguments
Applies to: naming

Default argument values are created once, when the function is defined, not on each call. A mutable default like `def add(item, items=[])` therefore shares the same list across every call, a classic bug. Use `None` as the default and create the object inside the function: `if items is None: items = []`.
