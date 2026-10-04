"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE FOLD over an output directory for the converters
         (coverage RATIONALE D-44): per source file, what a reader of
         any target format asks -- the lines, the measures over EVERY
         run, and WHO executed each range.

DESCRIPTION
       Every 'hwut.cov.conv.to_<format>' reads a 'SourceSummary' and
       writes its format; none of them reads the coverage files
       itself. So the fold from references to runs, the union over the
       references and the OR of the masks are written ONCE, and a
       target that wants less (lcov) simply leaves fields unread.

           SourceSummary
             source        path from the run's root
             executable    tuple of (begin, end)
             covered       tuple of (begin, end), the UNION over every
                           reference
             uncovered     executable minus covered
             measure_db    measure name -> entry in the measure's own
                           shape (measure.py), every point of the
                           universe, mask the OR over every reference
             by_reference  tuple of (tuple of run names, spans): per
                           reference with lines, WHO it stands for --
                           the run names sorted -- and the ranges it
                           executed; in reference order

       A RUN NAME is 'directory/test choice' ('directory/test' without
       a choice), from the output's run table.

       RATIOS ARE DERIVED HERE AND STORED NOWHERE ('percent'): a source
       with nothing to cover has NO ratio, and the text says 'n/a'
       rather than a green 100%.
______________________________________________________________________________
"""
from   dataclasses import dataclass

from   vut.engine.coverage.api import (Output, id_text, measure_db_of,
                                       measure_of, root_of, subtract, union)


@dataclass(frozen=True)
class SourceSummary:
    """One source file of the output, folded for a reader (module
    header)."""
    source:       str
    executable:   tuple
    covered:      tuple
    uncovered:    tuple
    measure_db:   dict
    by_reference: tuple


def run_name(output, run_id):
    """RETURN: str, 'directory/test choice' of a test run id of
    'output'; 'directory/test' where the test has no choice."""
    directory, test, choice = output.name_db[run_id]
    head = "%s/%s" % (directory, test) if directory not in ("", ".") \
           else test
    return "%s %s" % (head, choice) if choice else head


def summarise(output):
    """
    YIELD: SourceSummary, one per coverage file of 'output', in path
           order.

    'output' is an 'Output' (coverage/output.py).

    Raises OutputRefused where a coverage file cannot be read or a
    reference stands in neither table.
    """
    for gathered in output.gathered_iterable():
        reference_set = {reference for reference, _, _
                         in gathered.reference_list}
        covered, by_reference = (), []
        for reference, span_tuple, _ in gathered.reference_list:
            if not span_tuple: continue
            covered = union(covered, span_tuple)
            run_set = output.run_set_of(id_text(reference, gathered.id_width))
            by_reference.append((tuple(sorted(run_name(output, run_id)
                                              for run_id in run_set)),
                                 span_tuple))
        yield SourceSummary(gathered.source, gathered.executable, covered,
                            subtract(gathered.executable, covered),
                            measure_db_of(gathered, reference_set),
                            tuple(by_reference))


def measure_summary(name, entry):
    """RETURN: (covered, total), what the measure 'name' says of its
    entry (measure.py 'summary')."""
    return measure_of(name).summary(entry)


def percent(covered, total):
    """
    RETURN: str, 'covered' of 'total' as a percentage to one decimal.
            'n/a', where there is nothing to cover -- 100% would be a
            lie told in the green direction.
    """
    return "n/a" if total == 0 else "%.1f%%" % (100.0 * covered / total)


def line_count(range_tuple):
    """RETURN: int, the lines the ranges hold."""
    return sum(end - begin for begin, end in range_tuple)


def summaries_of(directory):
    """
    RETURN: [0] str, the root the run walked (None where the marker
                names none)
            [1] list of SourceSummary, in path order

    Raises OutputRefused where the directory cannot be read.
    """
    output = Output(directory)
    return root_of(directory), list(summarise(output))
