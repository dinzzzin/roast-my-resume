"""Expected: naming
Correct logic, unreadable names."""


def calc(a, b, q):
    tmp = 0
    for v in a:
        if v > b:
            tmp += v * q
    data = tmp / len(a) if a else 0
    zz = round(data, 2)
    return zz
