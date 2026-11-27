"""Expected: cyclomatic_complexity
The same block pasted three times with small edits. Known analyzer gap: the
duplication itself is not measured, only the complexity it causes."""


def grade_summary(math, science, english):
    out = {}
    if math:
        avg = sum(math) / len(math)
        if avg >= 90:
            out["math"] = "A"
        elif avg >= 80:
            out["math"] = "B"
        elif avg >= 70:
            out["math"] = "C"
        else:
            out["math"] = "F"
    if science:
        avg = sum(science) / len(science)
        if avg >= 90:
            out["science"] = "A"
        elif avg >= 80:
            out["science"] = "B"
        elif avg >= 70:
            out["science"] = "C"
        else:
            out["science"] = "F"
    if english:
        avg = sum(english) / len(english)
        if avg >= 90:
            out["english"] = "A"
        elif avg >= 80:
            out["english"] = "B"
        elif avg >= 70:
            out["english"] = "C"
        else:
            out["english"] = "F"
    return out
