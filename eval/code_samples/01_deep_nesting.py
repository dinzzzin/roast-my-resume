"""Expected: nesting_depth
Order validation with every check nested inside the last."""


def validate_orders(orders, min_total):
    valid = []
    for order in orders:
        if order is not None:
            if "items" in order:
                if len(order["items"]) > 0:
                    if order.get("total", 0) >= min_total:
                        if order.get("status") != "cancelled":
                            valid.append(order["id"])
    return valid
