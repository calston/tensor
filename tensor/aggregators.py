def Counter32(a, b, delta):
    """32bit counter aggregator with wrapping
    """
    if b < a:
        c = 4294967295 - a
        return (c + b) / float(delta)

    return (b - a) / float(delta)

def Counter64(a, b, delta):
    """64bit counter aggregator with wrapping
    """
    if b < a:
        c = 18446744073709551615 - a
        return (c + b) / float(delta)

    return (b - a) / float(delta)

def Counter(a, b, delta):
    """Counter derivative
    """
    if b < a:
        return None 

    return (b - a) / float(delta)
