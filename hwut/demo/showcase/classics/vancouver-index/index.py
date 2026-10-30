"""
______________________________________________________________________________
A STOCK INDEX, updated on every trade -- the unit 'TEST/test-vse.py' tests.

The index is kept in thousandths (an integer: 1000.000 is 1000000). Each
trade changes it by a relative step of 'k' parts per million:

    exact       the index carried with nine more decimals, the true value
    rounded     new = index x (1 + k/10^6), ROUNDED to the thousandth
    truncated   new = index x (1 + k/10^6), TRUNCATED to the thousandth
                -- as the Vancouver Stock Exchange did, 1982-1983

All arithmetic is in integers: no floating point decides a digit.
______________________________________________________________________________
"""
EXTRA = 10**9          # the exact track's additional decimals


def step_exact(index_e, k):
    """RETURN: int, the exact track (thousandths x EXTRA) after a trade of
    'k' ppm, rounded at its own last of twelve decimals."""
    return (index_e * (10**6 + k) + 5 * 10**5) // 10**6


def step_rounded(index, k):
    """RETURN: int, the index in thousandths after a trade of 'k' ppm,
    rounded half up to the thousandth."""
    return (index * (10**6 + k) + 5 * 10**5) // 10**6


def step_truncated(index, k):
    """RETURN: int, the index in thousandths after a trade of 'k' ppm,
    truncated to the thousandth: every trade drops what follows the third
    decimal."""
    return (index * (10**6 + k)) // 10**6
