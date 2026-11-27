"""Expected: none
Control: clean code with early returns. The analyzer should report no findings."""


def parse_price(text):
    """Convert a price string like "$1,299.50" to a float, or None if invalid."""
    if not text:
        return None
    cleaned = text.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None
