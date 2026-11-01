"""srt_divider.py -- MODEL of the Pentium's radix-4 SRT divider, bit level.

The divider produces two quotient bits per step: a digit q in {-2..+2},
chosen by a TABLE LOOKUP from the top bits of the partial remainder p and
of the divisor d, followed by p := 4 (p - q d). The model follows the
account of K. Shirriff ('Intel's $475 million error: the silicon behind
the Pentium division bug', 2024) and Coe & Tang ('It Takes Six Ones to
Reach a Flaw', 1995):

  * d is normalised to [1, 2); its 4 bits after the point pick one of 16
    table COLUMNS (1.dddd).
  * p is kept in CARRY-SAVE form, two words s and c with p = s + c; the
    subtraction of q d is a carry-save add of the one's complement of q d
    with a carry-in of 1 (for q > 0), or of |q| d (for q < 0).
  * the table ROW is a 7-bit estimate of p, 'pppp.ppp' (two's complement,
    steps of 1/8): the top bits of s and of c, each truncated, added. The
    estimate lies up to 2/8 below p.
  * the table: each cell holds the digit of LARGEST magnitude that keeps
    -8/3 d <= 4 (p - q d) <= 8/3 d for every p and d the cell can stand
    for; cells no remainder can reach hold 0.

THE FLAW: five cells at the top of the +2 region -- one in each of the
divisor columns 1.0001, 1.0100, 1.0111, 1.1010, 1.1101 -- hold 0 instead of
+2 (Intel: a script left them out when the table was loaded into the PLA).
A remainder that reaches one of them is not reduced, leaves the range, and
the quotient is wrong from about the 14th bit on. With this model,
4195835 / 3145727 gives 1.3337390689020376 -- Tim Coe's famous wrong
value (Nov 1994) -- and 5505001 / 294911 gives 18.666000929..., as the
chip did.
"""
from fractions import Fraction as Fr

F = 66                       # fraction bits of the remainder words
W = 4 + F                    # plus 4 integer bits, two's complement
MASK = (1 << W) - 1
FLAWED_COLUMNS = (1, 4, 7, 10, 13)


def _valid_digits(k, m):
    """RETURN: the digits valid for every (p, d) of cell (column k, row m),
               or None if no remainder can reach the cell."""
    d0, d1 = Fr(16 + k, 16), Fr(17 + k, 16)
    p0, p1 = Fr(m, 8), Fr(m + 2, 8)          # the estimate is up to 2/8 low
    if p0 >= Fr(8, 3) * d1 or p1 <= -Fr(8, 3) * d1:
        return None
    result = []
    for q in (-2, -1, 0, 1, 2):
        ok = True
        for d in (d0, d1):
            lo, hi = max(p0, -Fr(8, 3) * d), min(p1, Fr(8, 3) * d)
            if lo <= hi and not ((q - Fr(2, 3)) * d <= lo and hi <= (q + Fr(2, 3)) * d):
                ok = False
        if ok:
            result.append(q)
    return result


def table(flawed):
    """RETURN: {(column, row): digit}; rows m = -64 .. 63 (p = m / 8)."""
    t = {}
    for k in range(16):
        for m in range(-64, 64):
            v = _valid_digits(k, m)
            t[(k, m)] = 0 if v is None else (max(v) if m >= 0 else min(v))
    if flawed:
        for k in FLAWED_COLUMNS:
            t[(k, max(m for m in range(-64, 64) if t[(k, m)] == 2))] = 0
    return t


def missing_cells():
    good, bad = table(False), table(True)
    return sorted(key for key in good if good[key] != bad[key])


def _signed(v, bits):
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v


def divide(x, y, tab, digits=30):
    """RETURN: x / y as the divider computes it (a Fraction), x and y
               Fractions in [1, 2); 'digits' radix-4 digits."""
    s, c = int(x * (1 << F)) & MASK, 0
    dfix = int(y * (1 << F)) & MASK
    k = int((y - 1) * 16)
    quotient = 0
    for _ in range(digits):
        m = _signed(_signed(s >> (F - 3), 7) + _signed(c >> (F - 3), 7), 7)
        q = tab[(k, m)]
        quotient = quotient * 4 + q
        if q > 0:
            add, carry_in = (~(q * dfix)) & MASK, 1
        else:
            add, carry_in = ((-q) * dfix) & MASK, 0
        s2 = s ^ c ^ add
        c2 = (((s & c) | (s & add) | (c & add)) << 1) | carry_in
        s, c = (s2 << 2) & MASK, (c2 << 2) & MASK
    return Fr(quotient, 4 ** (digits - 1))


def fdiv(a, b, tab):
    """RETURN: a / b for positive integers, through the divider (a Fraction)."""
    ea, eb = a.bit_length() - 1, b.bit_length() - 1
    return divide(Fr(a, 2 ** ea), Fr(b, 2 ** eb), tab) * Fr(2) ** (ea - eb)
