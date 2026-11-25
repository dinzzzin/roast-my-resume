# Exception handling
Applies to: cyclomatic_complexity, function_length

Catch the most specific exception you expect, never a bare `except:`, which also swallows KeyboardInterrupt and real bugs. Keep the `try` block as small as possible so you know exactly which line can fail. `except SomeError: pass` silently hides failures; at minimum log what happened, or handle it deliberately with a comment explaining why ignoring it is safe.
