"""Expected: none
Control: clean code. The analyzer should report no findings."""


def average_score(scores):
    """Return the mean of the scores, or 0.0 for an empty list."""
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def passing_students(results, threshold=60):
    """Return names whose score meets the threshold, sorted alphabetically."""
    return sorted(name for name, score in results.items() if score >= threshold)
