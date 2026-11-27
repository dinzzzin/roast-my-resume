"""Expected: function_length
One function that parses, cleans, aggregates and formats a sales report."""


def sales_report(rows):
    cleaned = []
    for row in rows:
        name = row.get("name", "").strip()
        region = row.get("region", "").strip().upper()
        amount = row.get("amount", 0)
        if not name:
            continue
        if amount is None:
            amount = 0
        cleaned.append((name, region, amount))
    totals = {}
    for name, region, amount in cleaned:
        totals[region] = totals.get(region, 0) + amount
    best_region = None
    best_total = -1
    for region, total in totals.items():
        if total > best_total:
            best_region = region
            best_total = total
    people = {}
    for name, region, amount in cleaned:
        people[name] = people.get(name, 0) + amount
    top_people = sorted(people.items(), key=lambda p: p[1], reverse=True)
    top_people = top_people[:3]
    lines = []
    lines.append("SALES REPORT")
    lines.append("=" * 20)
    for region in sorted(totals):
        lines.append(f"{region}: {totals[region]}")
    lines.append("-" * 20)
    lines.append(f"Best region: {best_region} ({best_total})")
    lines.append("Top sellers:")
    for name, amount in top_people:
        lines.append(f"  {name}: {amount}")
    grand_total = sum(totals.values())
    lines.append(f"Grand total: {grand_total}")
    if cleaned:
        average = grand_total / len(cleaned)
    else:
        average = 0
    lines.append(f"Average sale: {round(average, 2)}")
    return "\n".join(lines)
