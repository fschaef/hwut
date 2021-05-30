from math import ceil, log10

def number_of_decimal_digits(n):
    return ceil(log10(n+1))
