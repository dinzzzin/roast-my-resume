"""Expected: cyclomatic_complexity
Shipping cost as an if/elif ladder of unexplained numbers."""


def shipping_cost(weight, zone, express):
    if weight <= 0:
        return 0
    if zone == 1:
        cost = 4.99 if weight < 2 else 7.5
    elif zone == 2:
        cost = 6.99 if weight < 2 else 10.25
    elif zone == 3:
        cost = 9.5 if weight < 2 else 14.0
    elif zone == 4:
        cost = 12.0 if weight < 2 else 18.75
    else:
        cost = 25.0
    if weight > 20:
        cost += 15
    elif weight > 10:
        cost += 7
    if express and zone in (1, 2):
        cost *= 1.5
    elif express:
        cost *= 2
    return round(cost, 2)
