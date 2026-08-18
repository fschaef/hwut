"""
UNITS -- the physical unit machinery (R-50).

One unit is a RATIONAL EXPONENT VECTOR over the seven SI base units.
The surface (what an author writes -- any product/quotient spelling)
folds into the vector; the vector is the CANONICAL form (product =
add, quotient = subtract, power = scale, equality = plain equality);
DISPLAY is the quotient of nominator to denominator (positive powers
left of the bar, negative right, sorted) -- two spellings of one unit
always print identically.

Derived unit names (N, J, W, ...) expand through the glossary below;
the human-readable twin is language/UNITS.txt.
"""

from fractions import Fraction

# the seven SI base units, in display order
BASES = ("kg", "m", "s", "A", "K", "mol", "cd")

_ZERO = (Fraction(0),) * 7

# name -> exponent vector; the glossary (UNITS.txt is the prose twin)
GLOSSARY = {}


def _base(name):
    """RETURN: tuple, the unit vector of one SI base -- a single 1 in the
              base's slot.
    """
    return tuple(Fraction(1) if b == name else Fraction(0) for b in BASES)


def mul(u, v):
    """RETURN: tuple, the vector of the PRODUCT of two units -- exponent
              addition.
    """
    return tuple(a + b for a, b in zip(u, v))


def div(u, v):
    """RETURN: tuple, the vector of the QUOTIENT of two units -- exponent
              subtraction.
    """
    return tuple(a - b for a, b in zip(u, v))


def power(u, p):
    """RETURN: tuple, the vector of a unit raised to rational 'p' --
              exponent scaling.
    """
    p = Fraction(p)
    return tuple(a * p for a in u)


def dimensionless(u):
    """RETURN: bool, True exactly when 'u' is the zero vector -- a bare
              number's unit (R-50: the dimensionless case).
    """
    return all(a == 0 for a in u)


for _b in BASES:
    GLOSSARY[_b] = _base(_b)

# gram: the glossary speaks 'g' so 'kg' stays the coherent base
GLOSSARY["g"] = power(_base("kg"), 1)   # magnitude prefixes are NOT
                                        # modelled (R-50 scopes DIMENSION,
                                        # not scale); 'g' aliases kg's
                                        # dimension

# derived units (dimension only -- scale factors are out of R-50's scope)
GLOSSARY.update({
    "Hz":  div(_ZERO, _base("s")),                        # 1/s
    "N":   div(mul(_base("kg"), _base("m")),
               power(_base("s"), 2)),                     # kg*m/s^2
    "Pa":  div(_base("kg"), mul(_base("m"),
               power(_base("s"), 2))),                    # kg/(m*s^2)
    "J":   div(mul(_base("kg"), power(_base("m"), 2)),
               power(_base("s"), 2)),                     # kg*m^2/s^2
    "W":   div(mul(_base("kg"), power(_base("m"), 2)),
               power(_base("s"), 3)),                     # kg*m^2/s^3
    "C":   mul(_base("A"), _base("s")),                   # A*s
    "V":   div(mul(_base("kg"), power(_base("m"), 2)),
               mul(power(_base("s"), 3), _base("A"))),    # kg*m^2/(s^3*A)
    "Ohm": div(mul(_base("kg"), power(_base("m"), 2)),
               mul(power(_base("s"), 3),
                   power(_base("A"), 2))),                # kg*m^2/(s^3*A^2)
    "F":   div(mul(power(_base("s"), 4),
                   power(_base("A"), 2)),
               mul(_base("kg"), power(_base("m"), 2))),   # s^4*A^2/(kg*m^2)
    "T":   div(_base("kg"),
               mul(power(_base("s"), 2), _base("A"))),    # kg/(s^2*A)
    "Wb":  div(mul(_base("kg"), power(_base("m"), 2)),
               mul(power(_base("s"), 2), _base("A"))),    # kg*m^2/(s^2*A)
    "lm":  _base("cd"),                                   # cd (sr is 1)
    "lx":  div(_base("cd"), power(_base("m"), 2)),        # cd/m^2
})

_SUPER = {"\u2070": "0", "\u00b9": "1", "\u00b2": "2", "\u00b3": "3",
          "\u2074": "4", "\u2075": "5", "\u2076": "6", "\u2077": "7",
          "\u2078": "8", "\u2079": "9", "\u207b": "-", "\u207a": "+"}


def super_int(text):
    """RETURN: int, the signed integer a Unicode superscript run spells
              (R-50: m^2 and m-superscript-2 are one thing).

    Raises ValueError on an ill-formed run (sign not leading, empty).
    """
    return int("".join(_SUPER[c] for c in text))


def lookup(name):
    """RETURN: tuple, the exponent vector of a unit name -- an SI base or
              a GLOSSARY derived name.
              None, else (the semantic layer rejects; UNITS.txt lists the
              admitted names).
    """
    return GLOSSARY.get(name)


def display(u):
    """RETURN: str, the canonical print of a unit vector -- the QUOTIENT of
              nominator to denominator (FR's representation, R-50):
              positive powers left of the bar in BASES order, negative
              right; '1' the dimensionless nominator; exponents as
              '^p' or '^(p/q)'.
    """
    def _fmt(base, exp):
        e = abs(exp)
        if e == 1:
            return base
        if e.denominator == 1:
            return "%s^%d" % (base, e.numerator)
        return "%s^(%d/%d)" % (base, e.numerator, e.denominator)

    num = [_fmt(b, e) for b, e in zip(BASES, u) if e > 0]
    den = [_fmt(b, e) for b, e in zip(BASES, u) if e < 0]
    head = "*".join(num) if num else "1"
    if not den:
        return head
    tail = "*".join(den)
    if len(den) > 1:
        tail = "(%s)" % tail
    return "%s/%s" % (head, tail)
