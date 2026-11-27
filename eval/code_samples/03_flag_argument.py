"""Expected: cyclomatic_complexity
A boolean-and-mode switchboard that does three different jobs."""


def export(records, compact, mode):
    out = []
    for rec in records:
        if mode == "csv":
            if compact:
                out.append(",".join(str(v) for v in rec.values()))
            else:
                out.append(", ".join(f"{k}={v}" for k, v in rec.items()))
        elif mode == "json":
            if compact:
                out.append(str(rec).replace(" ", ""))
            else:
                out.append(str(rec))
        elif mode == "keys":
            if compact and rec:
                out.append(list(rec)[0])
            elif rec:
                out.append("|".join(rec))
            else:
                out.append("")
        else:
            raise ValueError("unknown mode")
    return out
