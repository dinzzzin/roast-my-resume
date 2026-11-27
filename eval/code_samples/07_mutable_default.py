"""Expected: nesting_depth
Trap: the mutable default list is a real bug (state leaks between calls). A correct
fix CHANGES behavior, so the equivalence check should report a mismatch. Shows that
"equivalent" is not the same as "correct"."""


def collect_tags(posts, seen=[]):
    for post in posts:
        if post:
            for tag in post.get("tags", []):
                if tag:
                    if tag.lower() not in seen:
                        seen.append(tag.lower())
    return seen
