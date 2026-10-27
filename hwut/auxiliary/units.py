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
    "genetic_distance": "cM",
    "inductance":    "H",
    "length":        "m",
    "luminosity":    "cd",
    "mass":          "kg",
    "power":         "W",
    "pressure":      "Pa",
    "resistance":    "ohm",
    "sequence_length": "bp",
    "speed":         "m/s",
    "temperature":   "K",
    #  ONE DIMENSION, TWO KINDS (ND12, E-191): a reading and a difference.
    "temperature_difference": "delta_degC",
    "time":          "s",
    "voltage":       "V",
    "volume":        "m**3",
}

#  THE PREFIXES SHOWN beside a type's reference unit by '--units': pint
#  reads every SI prefix on every unit; these are the ones a log carries.
SHOWN_PREFIX_TUPLE = ("n", "u", "m", "k", "M", "G")

#  A TYPE WHOSE LOGS CARRY OTHER PREFIXES (ND14, E-194): a sequence is
#  written in kbp, Mbp, Gbp -- never 'mbp'; 'cM' is prefixed already.
SHOWN_PREFIX_DB = {"data": ("k", "M", "G", "T"),       # no 'mbyte' (E-195)
                   "sequence_length": ("k", "M", "G"),
                   "genetic_distance": ()}

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
    #  PINT'S OWN ALGEBRA (ND12, services E-191): an absolute temperature
    #  in arithmetic is an error with a name -- 't * 2' over 20 degC --
    #  never silently kelvin. 't2 - t1' of two degC is a delta_degC, and
    #  'degC + delta_degC' a degC, as physics has it.
    return pint.UnitRegistry(_definition_file(),
                             autoconvert_offset_to_baseunit=False)


def _definition_file():
    """
    RETURN: str, the path of pint's own unit definitions -- derived from
            the INSTALLED pint at the first call, so they never fall out
            of step with it -- changed where pint reads otherwise than a
            log means:
            - information is a dimension of its own, 'bit = [information]'
              (ND10, services E-192). pint counts bits and bytes as
              dimensionless, so '3 MB' bound as an angle and '10 GHz' held
              'r >= 100 MB/s'.
            - GENOMICS (ND14, E-194): 'bp' is a base pair, a sequence
              length ('kbp', 'Mbp', 'Gbp' by prefix), not pint's big point
              ('1200 bp' bound 0.423 m); 'cM' a centimorgan, a genetic
              distance, not centimolar. 'big_point' and 'centimolar' keep
              their long names.
            - BITS (E-195): 'kb', 'Mb', 'Gb' are kilo-, mega-, gigabits, as
              a link speed writes them -- not kilobarn, megabarn, gilbert.
            - ADDED (RQ-7, E-198): 'ppb' (1e-9, beside pint's 'ppm') and
              'pood' (16.3804964 kg), symbols of one reading each.
            raises RuntimeError naming the line, where the installed pint
            spells a changed line otherwise.
    """
    import atexit
    import os
    import re
    import shutil
    import tempfile
    import pint
    source = os.path.dirname(pint.__file__)
    target = tempfile.mkdtemp(prefix="hwut_units_")
    atexit.register(shutil.rmtree, target, True)
    for name in os.listdir(source):          # 'default_en.txt' imports others
        if name.endswith(".txt"):
            shutil.copy(os.path.join(source, name), target)
    path = os.path.join(target, "default_en.txt")
    with open(path, encoding="utf-8") as fh: text = fh.read()
    for pattern, replacement, said in _DEFINITION_CHANGE_TUPLE:
        text, n = re.subn(pattern, replacement, text)
        if n != 1:
            #  A PINT THAT SPELLS IT OTHERWISE is said, not guessed around.
            raise RuntimeError("pint %s does not define %s as hwut expects; "
                               "hwut cannot read its units"
                               % (pint.__version__, said))
    text += _DEFINITION_ADDED
    with open(path, "w", encoding="utf-8") as fh: fh.write(text)
    return path


#  WHERE HWUT'S REGISTRY DIFFERS FROM PINT'S: (pattern, replacement, what
#  the line is), each matching exactly once in 'default_en.txt'.
_DEFINITION_CHANGE_TUPLE = (
    (r"(?m)^(\s*)bit\s*=\s*\[\]", r"\1bit = [information]",
     "'bit = []'"),
    #  'bp' leaves the point's aliases; the point keeps 'big_point'.
    (r"(?m)^(\s*point\s*=.*?)\s*=\s*bp\s*$", r"\1",
     "the point with its alias 'bp'"),
    #  'Gb' leaves the gilbert, which keeps its name (E-195).
    (r"(?m)^(\s*gilbert\s*=.*?)\s*=\s*Gb\s*$", r"\1",
     "the gilbert with its symbol 'Gb'"),
)

#  WHAT HWUT ADDS (ND14, E-194; E-195). 'cM' defined whole is read before pint
#  splits it into 'c' + 'M' (molar).
_DEFINITION_ADDED = """

# hwut (ND14, services E-194): genomics
base_pair = [sequence_length] = bp
morgan = [genetic_distance]
centimorgan = 0.01 * morgan = cM

# hwut (services E-195): a link speed's bits -- '100 Mb/s', not megabarn
kilobit = 1e3 * bit = kb
megabit = 1e6 * bit = Mb
gigabit = 1e9 * bit = Gb

# hwut (RQ-7, services E-198): units the agent swarm met and pint lacks,
# each with ONE reading -- a part per billion as 'ppm' beside it; the
# Russian pood, 40 funt
ppb = 1e-9
pood = 16.3804964 * kilogram
"""


def difference_unit_f(unit):
    """
    RETURN: bool, True if 'unit' is a temperature DIFFERENCE --
            'delta_degC', 'delta_degF', ... -- as pint names them;
            False, else.
    """
    return str(unit).startswith("delta_")


def absolute_temperature_f(unit):
    """
    RETURN: bool, True if 'unit' is a temperature an ABSOLUTE reading
            is written in -- degC, degF, K, ... -- not a difference;
            False, else.
    """
    ureg = registry()
    return not difference_unit_f(unit) \
           and ureg.Unit(unit).dimensionality == ureg.Unit("K").dimensionality


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
    #  A BARE NUMBER IS NO QUANTITY: it spells no unit at all. NOT pint's
    #  'unitless', which is True for every dimensionless unit -- MEASURED
    #  (E-198): '2 ppm', '5 percent' never matched 'quantity(ppm)'.
    if not hasattr(quantity, "dimensionality") \
       or quantity.dimensionality != dimensionality_of(spec) \
       or quantity.units == ureg.dimensionless:
        raise NotThisQuantity(text)
    #  ABSOLUTE AND DIFFERENCE ARE NOT ONE KIND (ND12): 'quantity(temperature)',
    #  'quantity(degC)', 'quantity(K)' read readings; a difference is
    #  'quantity(delta_degC)'. One dimension, two meanings.
    if absolute_temperature_f(reference_of(spec)) \
       and difference_unit_f(quantity.units):
        raise NotThisQuantity(text)
    try:
        return float(quantity.to(reference_of(spec)).magnitude)
    except Exception:                                 # noqa: BLE001
        #  ONE DIMENSION, NO CONVERSION (ND9): an absolute temperature
        #  and a difference ('degC' and 'delta_degC') share
        #  '[temperature]', and pint refuses to convert between them --
        #  the text is no quantity of THIS kind: no match here.
        raise NotThisQuantity(text) from None


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


def written(unit, type_name):
    """
    RETURN: str, the spelling of 'unit' a LINE can write and the reader
            reads back as that very unit under 'quantity(<type_name>)' --
            pint's symbol where it is one ('ms', 'degC'), else the first
            alias or the name that is ('um' for 'μm', 'angstrom' for
            'Å', 'delta_degC' for 'Δ°C') -- if success;
            None, else: no spelling of it is read back (a constant such
            as 'pi', or a symbol another unit owns: 'mcd' reads as a
            microday).

    THE LISTING IS MEASURED THROUGH THE READER (D-65, services E-183):
    a spelling is offered only where 'UNIT_WORD_SRC' takes it whole and
    'bound_value' binds it, under its type, to this unit.
    """
    import re
    ureg   = registry()
    symbol = format(unit, "~")
    name   = str(unit)
    #  THE SYMBOL FIRST, then its ASCII forms ('μm' -> 'um', 'Δ°C' ->
    #  'delta_degC'), then pint's aliases and the name.
    candidate_list = [symbol, symbol.replace("μ", "u").replace("µ", "u"),
                      symbol.replace("Δ°", "delta_deg")]
    definition = getattr(ureg, "_units", {}).get(name)
    candidate_list += list(getattr(definition, "aliases", ()) or ())
    candidate_list.append(name)
    for candidate in candidate_list:
        if not candidate \
           or re.fullmatch(UNIT_WORD_SRC, candidate) is None:   continue
        try:
            if ureg.Unit(candidate) != unit:                    continue
            bound_value("1 %s" % candidate, type_name)
        except Exception:                             # noqa: BLE001
            continue
        return candidate
    return None


def unit_tuple(spec=None):
    """
    RETURN: tuple[(str, str)], '(unit, unit type)' for every unit of the
            registry a line can write ('written'), of 'spec's dimension
            only where 'spec' is given -- each type's reference unit also
            with the prefixes of SHOWN_PREFIX_TUPLE, or of SHOWN_PREFIX_DB
            where the type names its own -- sorted by type,
            then unit; empty where no unit of that dimension is written;
            raises UnitSpecError where 'spec' names nothing known.
    """
    ureg = registry()
    wanted = None if spec is None else dimensionality_of(spec)
    #  THE KIND, where a temperature is asked for: a reading or a difference.
    wanted_difference = None if spec is None \
                        else difference_unit_f(reference_of(spec))
    type_of = {}
    for name, reference in UNIT_TYPE_DB.items():
        type_of.setdefault(ureg.Unit(reference).dimensionality, name)

    def type_name_of(unit, dimension):
        """RETURN: str, the unit type 'unit' belongs to -- its dimension's,
                   a temperature difference apart from a reading."""
        if difference_unit_f(unit): return "temperature_difference"
        return type_of[dimension]
    found = set()
    for name in list(ureg._units):                    # noqa: SLF001 -- pint has no public list
        try:
            unit = ureg.Unit(name)
        except Exception:                             # noqa: BLE001
            continue
        dimension = unit.dimensionality
        if dimension not in type_of: continue
        if wanted is not None and dimension != wanted: continue
        if wanted is not None and type_of[dimension] == "temperature" \
           and difference_unit_f(unit) != wanted_difference:   continue
        spelling = written(unit, type_name_of(unit, dimension))
        if spelling is None: continue
        found.add((type_name_of(unit, dimension), spelling))
    for type_name, reference in UNIT_TYPE_DB.items():
        dimension = ureg.Unit(reference).dimensionality
        if wanted is not None and dimension != wanted: continue
        if "*" in reference or "/" in reference: continue
        if difference_unit_f(reference): continue      # no 'kdelta_degC'
        if wanted is not None and wanted_difference: continue
        for prefix in SHOWN_PREFIX_DB.get(type_name, SHOWN_PREFIX_TUPLE):
            #  SPELLED AS A LOG SPELLS IT: 'us', not pint's 'μs'.
            try:
                ureg.Unit(prefix + reference)
                bound_value("1 %s%s" % (prefix, reference), type_name)
            except Exception:                         # noqa: BLE001
                continue
            found.add((type_of[dimension], prefix + reference))
    return tuple((unit, type_name) for type_name, unit in sorted(found))
