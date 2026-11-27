"""Expected: nesting_depth
Builds a CSV by hand with nested loops and manual escaping."""


def to_csv(rows, columns):
    text = ""
    text += ",".join(columns) + "\n"
    for row in rows:
        values = []
        for col in columns:
            if col in row:
                value = row[col]
                if value is None:
                    values.append("")
                else:
                    if isinstance(value, str):
                        if "," in value:
                            values.append('"' + value + '"')
                        else:
                            values.append(value)
                    else:
                        values.append(str(value))
            else:
                values.append("")
        text += ",".join(values) + "\n"
    return text
