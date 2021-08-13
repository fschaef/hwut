from math import ceil, log10

def number_of_decimal_digits(n):
    return ceil(log10(n+1))

def right_aligned(N, n=None, fill=" "):
    if n is None:
        return fill * N
    else:
        n_str = "%s" % n
        return fill * (N - len(n_str)) + n_str
