"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE OTHER MEASUREMENTS -- branch, condition, MC/DC -- and the
         registration that admits one more without touching the format.

DESCRIPTION
       LINE COVERAGE IS ONE MEASUREMENT AMONG SEVERAL, and the record
       holds it in 'EX'/'CV' (RATIONALE D-5). Every other measurement a
       tool reports answers a DIFFERENT question about the same source,
       and none of them is a flag on a line:

           branch      of the arms leaving this decision, how many were
                       taken
           condition   of the terms in this decision, how many took both
                       values
           mcdc        of the conditions in this decision, for how many
                       was INDEPENDENCE demonstrated -- that each one
                       alone can flip the outcome

       A MEASURE IS REGISTERED, NOT BUILT IN. It owns its record TAG, its
       encoding, and the answer to whether it can be merged. Admitting a
       fourth is one 'register' call and no change to 'record.py' -- the
       record dispatches on the tag and asks the measure.

           EX:3+3,1        line, executable      record.py's own
           CV:3+3          line, covered         record.py's own
           BR:2*1/2        branch                this module
           MC:4*2/3,0*3/3  mc/dc                 this module

       THE POINT SHAPE. Both built-in measures are lists of
       (line, covered, total) -- a DECISION POINT and how much of it was
       exercised. Delta coded on the line, exactly as the ranges are:

           '<line delta>*<covered>/<total>'

       A delta of ZERO means ANOTHER DECISION ON THE SAME LINE, which
       'a && b || c' in one 'if' produces and which a line-keyed record
       could not otherwise express. The FIRST delta must still advance
       from zero: there is no line zero.

       WHY THESE CANNOT BE MERGED, and why that is refused rather than
       fudged. A count of arms taken does not carry WHICH arms. Run A
       takes arm 0, run B takes arm 1: together the decision is fully
       covered, but the two counts are 1 and 1, and no function of 1 and
       1 yields 2. The same holds for MC/DC -- two runs may demonstrate
       independence of DIFFERENT conditions.

           max(1, 1) = 1     a LOWER BOUND, reported as a measurement
                             -- a false RED, and worse, one that becomes
                             a false GREEN the moment somebody 'fixes'
                             it by summing instead

       So a measure DECLARES 'mergeable', both of these declare False,
       and 'record.merge' refuses by name. A future encoding that carried
       the SET of arms taken rather than their number would be mergeable,
       and could then declare so; that is the shape to reach for if an
       aggregate over branch data is ever wanted (DISCUSSIONS todo-8).

       A MEASURE WITHOUT LINES CANNOT LIVE HERE -- AND FEWER LACK ONE
       THAN disc-9 BELIEVED. The witnessed artifacts (TEST/REAL_
       PARSING_INPUT/PROVENANCE.txt) seat toggle points at the signal's DECLARATION
       line and cover points at their statement, so both live here as
       NAMED points. What truly has no line -- a covergroup BIN behind
       UCIS -- still cannot, and the registration below is deliberately
       no help with it: pretending otherwise is how a design gets
       reported '92% covered' while the coverage somebody came for is
       discarded.
______________________________________________________________________________
"""


class MeasureFault(ValueError):
    """A measure line that cannot be read, or a tag no measure claims.
    Named where it is met: a coverage record half-read is a coverage
    report that lies."""
    pass


class I_Measure:
    """ONE MEASUREMENT beside line coverage.

    'name' is how a configuration and a report speak of it; 'tag' is the
    two letters that carry it in a record. 'mergeable' says whether two
    records holding it can be unioned -- see the module header for why
    both built-in measures say False.
    """
    name      = None
    tag       = None
    mergeable = False

    def encode(self, entry):
        """RETURN: str, the entry as it is stored."""
        raise NotImplementedError

    def decode(self, text):
        """RETURN: the entry the text spells. Raises MeasureFault."""
        raise NotImplementedError

    def summary(self, entry):
        """
        RETURN: [0] int, how much of this measure was covered.
                [1] int, how much there was to cover.

        A ratio is DERIVED from these by whoever renders; the record
        stores neither.
        """
        raise NotImplementedError


class PointMeasure(I_Measure):
    """A measure recorded PER DECISION POINT: (line, covered, total).

    'same_line_f' admits a delta of zero -- a second decision on one
    line. Branch data is reported per line and does not need it; MC/DC
    is reported per DECISION, and 'if (a && b || c)' is one line with
    one decision while 'if (a) if (b)' is one line with two.
    """

    def __init__(self, name, tag, same_line_f=False, mergeable=False):
        """RETURN: PointMeasure, ready to register."""
        self.name        = name
        self.tag         = tag
        self.same_line_f = same_line_f
        self.mergeable   = mergeable

    def encode(self, entry):
        """
        RETURN: str, '<line delta>*<covered>/<total>' per point, in line
                order. Empty string where there is no point.
        """
        piece_list = []
        previous   = 0
        for line, covered, total in entry:
            piece_list.append("%i*%i/%i" % (line - previous, covered, total))
            previous = line
        return ",".join(piece_list)

    def decode(self, text):
        """
        RETURN: tuple of (line, covered, total), in line order.

        Raises MeasureFault on a piece that spells no point, on a first
        delta that does not advance from zero, on a zero delta where this
        measure admits none, and on a covered count above the total --
        which is not a measurement but an arithmetic mistake.
        """
        text = text.strip()
        if not text: return ()

        result   = []
        previous = 0
        for i, piece in enumerate(text.split(",")):
            head, _, ratio = piece.partition("*")
            covered_text, _, total_text = ratio.partition("/")
            try:
                delta   = int(head)
                covered = int(covered_text)
                total   = int(total_text)
            except ValueError:
                raise MeasureFault("'%s' spells no '<delta>*<covered>/"
                                   "<total>' point" % piece) from None
            if delta < 0 or (delta == 0 and (i == 0 or not self.same_line_f)):
                raise MeasureFault(
                    "delta %i in '%s' does not advance%s"
                    % (delta, piece,
                       "" if not self.same_line_f
                       else " (zero is admitted only for a SECOND "
                            "decision on one line)"))
            if total < 1:
                raise MeasureFault("'%s' has nothing to cover" % piece)
            if covered > total:
                raise MeasureFault(
                    "'%s' covers %i of %i -- an arithmetic mistake, not a "
                    "measurement" % (piece, covered, total))
            line = previous + delta
            result.append((line, covered, total))
            previous = line
        return tuple(result)

    def summary(self, entry):
        """RETURN: [0] int, points covered. [1] int, points there were."""
        return (sum(covered for _, covered, _ in entry),
                sum(total   for _, _, total   in entry))


class NamedPointMeasure(I_Measure):
    """A measure recorded PER NAMED POINT: (line, name, covered, total).

    The point of the NAME (TEST/REAL_PARSING_INPUT/PROVENANCE.txt, finding 4): the
    artifact names every bit and every cover point, so two runs can be
    UNIONED -- point identity is carried, which is exactly what the
    anonymous (covered, total) digest of 'branch' threw away and why
    that one refuses merge. 'covered' is bounded by 'total'; for the
    one-bit points both built-ins produce, it is 0 or 1 and merge is OR.

    The LINE is the point's DECLARED position -- a signal's declaration,
    a 'cover property' statement -- so several points share one line as
    a matter of course: a delta of zero is admitted from the second
    point on. Points sort by line, then by name, so the bytes are
    stable.
    """

    def __init__(self, name, tag):
        """RETURN: NamedPointMeasure, ready to register. Mergeable by
        construction -- see the class header."""
        self.name      = name
        self.tag       = tag
        self.mergeable = True

    def encode(self, entry):
        """
        RETURN: str, '<line delta>*<name>*<covered>/<total>' per point,
                in (line, name) order. Empty string where there is none.

        Raises MeasureFault on a name carrying '*' or ',' -- the
        encoding's own separators; no witnessed identifier does, and an
        escape scheme would trade a refusal for a corruption.
        """
        piece_list = []
        previous   = 0
        for line, name, covered, total in sorted(entry):
            if "*" in name or "," in name:
                raise MeasureFault(
                    "point name '%s' carries a separator of the "
                    "encoding itself" % name)
            piece_list.append("%i*%s*%i/%i"
                              % (line - previous, name, covered, total))
            previous = line
        return ",".join(piece_list)

    def decode(self, text):
        """
        RETURN: tuple of (line, name, covered, total), in (line, name)
                order.

        Raises MeasureFault on a piece that spells no point, a first
        delta that does not advance from zero, a negative delta, an
        empty name, nothing to cover, or a covered count above the
        total.
        """
        text = text.strip()
        if not text: return ()

        result   = []
        previous = 0
        for i, piece in enumerate(text.split(",")):
            part_list = piece.split("*")
            if len(part_list) != 3:
                raise MeasureFault("'%s' spells no '<delta>*<name>*"
                                   "<covered>/<total>' point" % piece)
            head, name, ratio = part_list
            covered_text, _, total_text = ratio.partition("/")
            try:
                delta   = int(head)
                covered = int(covered_text)
                total   = int(total_text)
            except ValueError:
                raise MeasureFault("'%s' spells no '<delta>*<name>*"
                                   "<covered>/<total>' point" % piece) from None
            if not name:
                raise MeasureFault("'%s' names no point" % piece)
            if delta < 0 or (delta == 0 and i == 0):
                raise MeasureFault("delta %i in '%s' does not advance "
                                   "(zero is admitted only for a second "
                                   "point on one line)" % (delta, piece))
            if total < 1:
                raise MeasureFault("'%s' has nothing to cover" % piece)
            if covered > total:
                raise MeasureFault(
                    "'%s' covers %i of %i -- an arithmetic mistake, not "
                    "a measurement" % (piece, covered, total))
            line = previous + delta
            result.append((line, name, covered, total))
            previous = line
        return tuple(result)

    def summary(self, entry):
        """RETURN: [0] int, points covered. [1] int, points there were."""
        return (sum(covered for _, _, covered, _ in entry),
                sum(total   for _, _, _, total   in entry))

    def merge(self, entry_a, entry_b):
        """
        RETURN: tuple of (line, name, covered, total), the UNION: a point
                covered in either run is covered.

        Raises MeasureFault where one (line, name) point carries two
        different totals -- the two records do not describe one point,
        and adjudicating them would be an invention.
        """
        point_db = {(line, name): (covered, total)
                    for line, name, covered, total in entry_a}
        for line, name, covered, total in entry_b:
            standing = point_db.get((line, name))
            if standing is None:
                point_db[(line, name)] = (covered, total)
                continue
            if standing[1] != total:
                raise MeasureFault(
                    "point '%s' at line %i totals %i in one record and "
                    "%i in the other: these are not one point"
                    % (name, line, standing[1], total))
            point_db[(line, name)] = (max(standing[0], covered), total)
        return tuple(sorted((line, name, covered, total)
                            for (line, name), (covered, total)
                            in point_db.items()))


#  ------------------------------------------------------------ registry

_MEASURE_DB = {}
_TAG_DB     = {}


def register(measure):
    """
    RETURN: I_Measure, now standing for its name and its tag.

    Raises MeasureFault where either is already taken: two measures
    behind one tag is two truths, and the second would win by import
    order.
    """
    if measure.name in _MEASURE_DB:
        raise MeasureFault("measure '%s' is already registered"
                           % measure.name)
    if measure.tag in _TAG_DB:
        raise MeasureFault("tag '%s' is already taken, by '%s'"
                           % (measure.tag, _TAG_DB[measure.tag].name))
    _MEASURE_DB[measure.name] = measure
    _TAG_DB[measure.tag]      = measure
    return measure


def measure_of(name):
    """
    RETURN: I_Measure of that name.
            None, where none is registered -- the caller decides whether
            that is a fault; a record's reader does, a report may not.
    """
    return _MEASURE_DB.get(name)


def measure_of_tag(tag):
    """
    RETURN: I_Measure carrying that record tag.
            None, where no measure claims it.
    """
    return _TAG_DB.get(tag)


def name_tuple():
    """RETURN: tuple of str, every registered measure, sorted -- the
    order a record writes them in, so the bytes are stable."""
    return tuple(sorted(_MEASURE_DB))


def tag_tuple():
    """RETURN: tuple of str, every claimed tag, sorted."""
    return tuple(sorted(_TAG_DB))


#  ------------------------------------------------------- the built-ins

BRANCH = register(PointMeasure("branch", "BR", same_line_f=False))

#  MC/DC IS REGISTERED; NO READER PRODUCES IT YET. GCC 14 gained
#  '-fcondition-coverage' and 'gcov --conditions'; the machine this was
#  written on carries gcc 13, so the artifact could not be seen. The
#  ENCODING here is this component's own and is tested; the READING of
#  somebody else's is owed and must be written against a real artifact
#  (DISCUSSIONS todo-8).
MCDC = register(PointMeasure("mcdc", "MC", same_line_f=True))

#  THE NAMED-POINT MEASURES, witnessed before they were written
#  (TEST/REAL_PARSING_INPUT/PROVENANCE.txt): verilator's native '.dat' names every
#  toggle point PER BIT at the signal's declaration line, and every
#  'cover property' at its statement; GHDL's psl-report names every
#  'cover' directive at its line. Both are read ('readers/verilator.py',
#  'readers/ghdl_psl.py'); both merge, because the artifact carries
#  point identity -- which is what the paragraph above says to reach
#  for.
TOGGLE = register(NamedPointMeasure("toggle", "TG"))
COVER  = register(NamedPointMeasure("cover",  "CP"))
