# Descriptive names
Applies to: naming

A name should say what a value means, not what type it is. Single letters are fine for short loop counters (i, j) and math, but names like d, r, t, data, tmp, obj or stuff tell the reader nothing. Prefer names that explain intent: `orders` instead of `d`, `matching_ids` instead of `r`, `target_type` instead of `t`. The cost of a longer name is tiny compared to the cost of a reader guessing wrong.
