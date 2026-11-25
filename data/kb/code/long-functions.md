# Long functions
Applies to: function_length

A function should do one thing. Once a function grows past roughly 40 lines it usually mixes several jobs, such as parsing, validating, transforming and saving. Split it into small, well-named helpers so each piece can be read, tested and reused on its own. A good sign you need to split: you want to write a comment above a block to explain what it does; that comment is the name of the missing function.
