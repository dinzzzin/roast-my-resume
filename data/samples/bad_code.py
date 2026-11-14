def process(d, t, flag):
    r = []
    for x in d:
        if x is not None:
            if flag:
                if x["type"] == t:
                    for k in x["items"]:
                        if k > 0 and k < 100 or k == -1:
                            r.append(k)
                        elif k >= 100:
                            if k % 2 == 0:
                                r.append(k // 2)
                            else:
                                r.append(k * 3 + 1)
                        else:
                            pass
            else:
                try:
                    tmp = x["items"]
                    r.extend(tmp)
                except KeyError:
                    pass
    return r


def ok_function(values):
    return sum(values) / len(values)
