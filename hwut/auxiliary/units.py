"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: QUANTITIES WITH UNITS (the book's RQ-7) -- one reading for every
         face that binds a number with its unit: pype's '<t = quantity(X)>'
         and the comparison's bindings '((t: 2.5 ms))' and constraint
         literals 't < 50 ms'.

    quantity(time)      X names a UNIT TYPE: every unit of that dimension
    quantity(s)         X names a UNIT: every unit of ITS dimension --
    quantity(ms)        's', 'h', 'ms', 'us', 'ns' all for each of these

THE BACKBONE IS pint (BSD-3-Clause), a requirement of hwut: it parses
'2.5ms' and '2.5 ms' alike, converts, and refuses a wrong dimension. The
UNIT TYPES are hwut's own names for dimensions -- pint names dimensions
('[length] / [time]'), not 'velocity' -- each held by a reference unit.
No unit is defined by the user, for now: the base is pint's registry.

THE VALUE BOUND is the number in the unit X names; for a unit type, in
the type's reference unit ('quantity(time)' binds seconds). See
'bound_value'.
______________________________________________________________________________
"""
import functools

#  THE UNIT TYPES: name -> reference unit (SI where SI has one). The name
#  is what 'quantity(<type>)' and 'hwut.pype --units <type>' take.
UNIT_TYPE_DB = {
    "acceleration":  "m/s**2",
    "amount":        "mol",
    "angle":         "radian",
    "area":          "m**2",
    "capacitance":   "F",
    "charge":        "C",
    "current":       "A",
    "data":          "byte",
    "density":       "kg/m**3",
    "energy":        "J",
    "force":         "N",
    "frequency":     "Hz",
    "inductance":    "H",
    "length":        "m",
    "luminosity":    "cd",
    "mass":          "kg",
    "power":         "W",
    "pressure":      "Pa",
    "resistance":    "ohm",
    "speed":         "m/s",
    "temperature":   "K",
    "time":          "s",
    "voltage":       "V",
    "volume":        "m**3",
}

#  THE PREFIXES SHOWN beside a type's reference unit by '--units': pint
#  reads every SI prefix on every unit; these are the ones a log carries.
SHOWN_PREFIX_TUPLE = ("n", "u", "m", "k", "M", "G")

#  A UNIT AS A LINE SPELLS IT: a word, optionally divided or multiplied
#  by further words, powers allowed -- 'ms', 'kN', 'm/s', 'm/s**2',
#  'kg*m', 'degC'.
UNIT_WORD_SRC = (r"(?:[A-Za-zµΩ°%][A-Za-z0-9µΩ°%_]*"
                 r"(?:\*\*-?\d+|\^-?\d+)?"
                 r"(?:[/*][A-Za-zµΩ°%][A-Za-z0-9µΩ°%_]*"
                 r"(?:\*\*-?\d+|\^-?\d+)?)*)")


class UnitSpecError(ValueError):
    """'quantity(X)' where X is neither a unit type nor a unit pint
    knows -- refused where the pattern is read, naming X."""


class NotThisQuantity(Exception):
    """The text at hand is a number and a word, but not a quantity of
    the dimension asked for -- the pattern does not match HERE."""


@functools.lru_cache(maxsize=1)
def registry():
    """
    RETURN: pint.UnitRegistry, the one registry of hwut, if success;
            raises ModuleNotFoundError naming pint, else -- 'hwut.help'
            names how to install it.
    """
    import pint
    return pint.UnitRegistry(autoconvert_offset_to_baseunit=True)


@functools.lru_cache(maxsize=None)
def reference_of(spec):
    """
    RETURN: str, the unit a binding of 'quantity(<spec>)' is expressed
            in -- 'spec' itself where it names a unit, the type's
            reference unit where it names a unit type -- if success;
            raises UnitSpecError naming 'spec', else.
    """
    spec = spec.strip()
    if spec in UNIT_TYPE_DB: return UNIT_TYPE_DB[spec]
    try:
        registry().Unit(spec)
    except Exception:                                 # noqa: BLE001
        raise UnitSpecError(
            "'quantity(%s)': '%s' is neither a unit type ('hwut.pype "
            "--unit-types') nor a unit ('hwut.pype --units')"
            % (spec, spec)) from None
    return spec


@functools.lru_cache(maxsize=None)
def dimensionality_of(spec):
    """
    RETURN: the pint dimensionality 'quantity(<spec>)' admits -- the one
            of its reference unit; raises UnitSpecError, else.
    """
    return registry().Unit(reference_of(spec)).dimensionality


def bound_value(text, spec):
    """
    RETURN: float, the quantity 'text' ('2.5ms', '2.5 s', '+30.0 N')
            expressed in the reference unit of 'spec' -- '2.5 s' under
            'quantity(ms)' is 2500.0 -- if success;
            raises NotThisQuantity, else: the word is no unit, or a unit
            of another dimension ('3 kg' under 'quantity(N)').
    """
    ureg = registry()
    try:
        quantity = ureg.Quantity(text.replace(" ", ""))
    except Exception:                                 # noqa: BLE001
        try:
            quantity = ureg.Quantity(text)
        except Exception:                             # noqa: BLE001
            raise NotThisQuantity(text) from None
    if not hasattr(quantity, "dimensionality") \
       or quantity.dimensionality != dimensionality_of(spec) \
       or quantity.unitless:
        raise NotThisQuantity(text)
    return float(quantity.to(reference_of(spec)).magnitude)


def quantity_of(text):
    """
    RETURN: pint.Quantity, the quantity 'text' spells -- '50 ms', '2.5kN',
            '+30 N' -- if success;
            raises NotThisQuantity naming 'text' where it spells none (a
            word pint does not know), ModuleNotFoundError where pint is
            absent.
    """
    ureg = registry()
    for candidate in (text.strip(), text.replace(" ", "")):
        try:
            quantity = ureg.Quantity(candidate)
        except ModuleNotFoundError:
            raise
        except Exception:                             # noqa: BLE001
            continue
        if hasattr(quantity, "dimensionality"):
            return quantity
    raise NotThisQuantity(text)


def shown(value):
    """
    RETURN: str, 'value' as a test page says it: a quantity in pint's
            short form ('2.5 ms'), anything else as 'str' does.
    """
    if hasattr(value, "units") and hasattr(value, "magnitude"):
        return format(value, "~")
    return str(value)


def unit_type_tuple():
    """
    RETURN: tuple[(str, str)], every unit type with its reference unit,
            by name -- what 'hwut.pype --unit-types' lists.
    """
    return tuple(sorted(UNIT_TYPE_DB.items()))


def unit_tuple(spec=None):
    """
    RETURN: tuple[(str, str)], '(unit, unit type)' for every unit of the
            registry, of 'spec's dimension only where 'spec' is given --
            each type's reference unit also with the prefixes of
            SHOWN_PREFIX_TUPLE -- sorted by type, then unit;
            raises UnitSpecError where 'spec' names nothing known.
    """
    ureg = registry()
    wanted = None if spec is None else dimensionality_of(spec)
    type_of = {}
    for name, reference in UNIT_TYPE_DB.items():
        type_of.setdefault(ureg.Unit(reference).dimensionality, name)
    found = set()
    for name in list(ureg._units):                    # noqa: SLF001 -- pint has no public list
        try:
            unit = ureg.Unit(name)
        except Exception:                             # noqa: BLE001
            continue
        dimension = unit.dimensionality
        if dimension not in type_of: continue
        if wanted is not None and dimension != wanted: continue
        found.add((type_of[dimension], format(unit, "~") or name))
    for type_name, reference in UNIT_TYPE_DB.items():
        dimension = ureg.Unit(reference).dimensionality
        if wanted is not None and dimension != wanted: continue
        if "*" in reference or "/" in reference: continue
        for prefix in SHOWN_PREFIX_TUPLE:
            #  SPELLED AS A LOG SPELLS IT: 'us', not pint's 'μs'.
            try:
                ureg.Unit(prefix + reference)
            except Exception:                         # noqa: BLE001
                continue
            found.add((type_of[dimension], prefix + reference))
    return tuple((unit, type_name) for type_name, unit in sorted(found))
