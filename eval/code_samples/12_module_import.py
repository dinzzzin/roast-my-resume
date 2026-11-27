"""Expected: nesting_depth
Trap: relies on a module-level import, so the snippet can't run on its own and the
equivalence check should report "not testable"."""
import math


def nearest_points(points, origin, radius):
    found = []
    for p in points:
        if p is not None:
            if len(p) == 2:
                d = math.hypot(p[0] - origin[0], p[1] - origin[1])
                if d <= radius:
                    if p not in found:
                        found.append(p)
    return found
