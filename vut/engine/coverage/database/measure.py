"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE OTHER MEASUREMENTS -- branch, MC/DC, toggle, cover, function -- and the
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
       (line, mask, total) -- a DECISION POINT, how many ITEMS it has
       (its arms, its conditions) and WHICH of them were taken: bit i
       of the mask is set where item i was (RATIONALE D-43). Delta coded
       on the line, exactly as the ranges are:

           '<line delta>*<mask in hexadecimal>/<total>'

           BR:2*1/2        line 2, arm 0 of two taken
           BR:2*3/2        line 2, both arms taken

       A delta of ZERO means ANOTHER DECISION ON THE SAME LINE, which
       'a && b || c' in one 'if' produces and which a line-keyed record
       could not otherwise express. The FIRST delta must still advance
       from zero: there is no line zero.

       ITEMS ARE IDENTIFIED BY POSITION: the order the tool reports
       them. That is what makes the measures MERGEABLE: run A takes arm
       0, run B takes arm 1, and the union is the OR of the masks,
       3 -- where a COUNT of arms taken (1 and 1) had no answer, and
       'max(1, 1) = 1' was a lower bound reported as a measurement. A
       tool that cannot name its arms (a count of taken and missing)
       contributes no such measure at all.

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
    records holding it can be unioned: a measure whose entry cannot name
    the items it counted says False, and 'record.merge' refuses it by
    name.
    """
    name      = None
    tag       = None
    mergeable = False
    named_f   = False

    def encode(self, entry):
        """RETURN: str, the entry as it is stored."""
        raise NotImplementedError

    def point_list(self, entry):
        """
        RETURN: list of (line, name, total, mask), the entry as POINTS OF
                ITEMS, in the entry's order: bit i of 'mask' is set where
                item i of the point was taken. 'name' is '' for a
                decision point, which has none.

        THIS IS THE SHAPE THE OUTPUT FILES GATHER (RATIONALE D-43): the
        same for every measure, so a gatherer needs to know none of
        them.

        Raises MeasureFault where the entry holds a point whose items
        cannot be named -- a count of items taken is no mask.
        """
        raise NotImplementedError

    def entry_of(self, point_list):
        """RETURN: the entry that 'point_list' spells; the inverse of
        'point_list'."""
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
    """A measure recorded PER DECISION POINT: (line, mask, total).

    'total' is the number of items the decision has, 'mask' which of
    them were taken, bit i for item i. 'same_line_f' admits a delta of
    zero -- a second decision on one line. Branch data is reported per
    line and does not need it; MC/DC is reported per DECISION, and
    'if (a && b || c)' is one line with one decision while 'if (a) if
    (b)' is one line with two.
    """

    def __init__(self, name, tag, same_line_f=False):
        """RETURN: PointMeasure, ready to register. Mergeable: the masks
        carry which items were taken."""
        self.name        = name
        self.tag         = tag
        self.same_line_f = same_line_f
        self.mergeable   = True

    def encode(self, entry):
        """
        RETURN: str, '<line delta>*<mask in hexadecimal>/<total>' per
                point, in line order. Empty string where there is no
                point.
        """
        piece_list = []
        previous   = 0
        for line, mask, total in entry:
            piece_list.append("%i*%x/%i" % (line - previous, mask, total))
            previous = line
        return ",".join(piece_list)

    def decode(self, text):
        """
        RETURN: tuple of (line, mask, total), in line order.

        Raises MeasureFault on a piece that spells no point, on a first
        delta that does not advance from zero, on a zero delta where this
        measure admits none, on a decision with nothing to take, and on
        a mask that names an item the decision does not have -- which is
        not a measurement but an arithmetic mistake.
        """
        text = text.strip()
        if not text: return ()

        result   = []
        previous = 0
        for i, piece in enumerate(text.split(",")):
            head, _, ratio = piece.partition("*")
            mask_text, _, total_text = ratio.partition("/")
            try:
                delta = int(head)
                mask  = int(mask_text, 16)
                total = int(total_text)
            except ValueError:
                raise MeasureFault("'%s' spells no '<delta>*<mask>/"
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
            if mask < 0 or mask >> total:
                raise MeasureFault(
                    "'%s' names an item of a decision that has %i -- an "
                    "arithmetic mistake, not a measurement"
                    % (piece, total))
            line = previous + delta
            result.append((line, mask, total))
            previous = line
        return tuple(result)

    def summary(self, entry):
        """RETURN: [0] int, items taken. [1] int, items there were."""
        return (sum(bin(mask).count("1") for _, mask, _ in entry),
                sum(total for _, _, total in entry))

    def point_list(self, entry):
        """RETURN: list of (line, '', total, mask) -- the entry's own
        points, no name."""
        return [(line, "", total, mask) for line, mask, total in entry]

    def entry_of(self, point_list):
        """RETURN: tuple of (line, mask, total) over the points."""
        return tuple((line, mask, total)
                     for line, _, total, mask in point_list)

    def merge(self, entry_a, entry_b):
        """
        RETURN: tuple of (line, mask, total), the UNION: an item taken in
                either record is taken. A point is identified by its line
                and its place among the points of that line.

        Raises MeasureFault where one point carries two different totals
        -- the two records do not describe one decision, and
        adjudicating them would be an invention.
        """
        point_db = {}
        for entry in (entry_a, entry_b):
            seen_db = {}
            for line, mask, total in entry:
                place = seen_db.get(line, 0)
                seen_db[line] = place + 1
                standing = point_db.get((line, place))
                if standing is None:
                    point_db[(line, place)] = (mask, total)
                    continue
                if standing[1] != total:
                    raise MeasureFault(
                        "the decision at line %i has %i items in one "
                        "record and %i in the other: these are not one "
                        "decision" % (line, standing[1], total))
                point_db[(line, place)] = (standing[0] | mask, total)
        return tuple((line, mask, total)
                     for (line, _), (mask, total)
                     in sorted(point_db.items()))


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

    named_f = True

    def __init__(self, name, tag):
        """RETURN: NamedPointMeasure, ready to register. Mergeable by
        construction -- see the class header."""
        self.name      = name
        self.tag       = tag
        self.mergeable = True

    def point_list(self, entry):
        """
        RETURN: list of (line, name, 1, mask), the entry's points in
                (line, name) order: mask 1 where the point was covered.

        Raises MeasureFault on a point with a total above one: 'covered
        3 of 5' says HOW MANY items were taken and not WHICH, and two
        such counts cannot be told apart from the same three items.
        """
        result = []
        for line, name, covered, total in sorted(entry):
            if total != 1:
                raise MeasureFault(
                    "point '%s' at line %i has %i items and a COUNT of "
                    "%i taken: a count names no item, and only a point "
                    "of one item can be carried" % (name, line, total,
                                                    covered))
            result.append((line, name, 1, covered))
        return result

    def entry_of(self, point_list):
        """RETURN: tuple of (line, name, covered, total) over the
        points, each of one item."""
        return tuple((line, name, mask, total)
                     for line, name, total, mask in point_list)

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

#  THE FUNCTION: a point of ONE item, entered or not, named by the
#  function and seated at the line it is declared on. Registered with
#  the output files (D-43); a reader that produces it is owed
#  (DISCUSSIONS todo-8): gcov, JaCoCo, cobertura and lcov 'FN' all name
#  their functions.
FUNCTION = register(NamedPointMeasure("function", "FN"))
