"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
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
             format        the formats that wrote its records, ','-
                           joined, as the coverage file names them
             reportable    the measures those formats can report
                           (coverage D-49, D-50); None where a format
                           is one this build does not know by name

       A RUN NAME is 'directory/test choice' ('directory/test' without
       a choice), from the output's run table.

       RATIOS ARE DERIVED HERE AND STORED NOWHERE ('percent'): a source
       with nothing to cover has NO ratio, and the text says 'n/a'
       rather than a green 100%.
______________________________________________________________________________
"""
from   dataclasses import dataclass

from ....engine.coverage.api import (Output, format_named, id_text,
                                       measure_db_of, measure_of, root_of,
                                       subtract, union)


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
    format:       str          = ""
    reportable:   tuple | None = None


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
                            tuple(by_reference), gathered.format,
                            reportable_of(gathered.format))


def reportable_of(format_text):
    """
    RETURN: tuple[str], sorted, the measures the formats named in
            'format_text' (','-joined) can report between them, beside
            the lines (coverage D-49)
            None, where any of them is unknown to this build by name, or
            none is named -- no information (coverage D-50).
    """
    name_list = [name for name in (format_text or "").split(",") if name]
    if not name_list: return None
    reportable = set()
    for name in name_list:
        fmt = format_named(name)
        if fmt is None: return None
        reportable.update(fmt.measure_tuple)
    return tuple(sorted(reportable))


def unreportable_of(summary, name_list):
    """
    RETURN: tuple[str], the measures of 'name_list' -- the page's columns
            -- that the source's formats cannot report: its MARKERS
            (coverage D-50); empty where it has none or where nothing is
            known of its formats.
    """
    if summary.reportable is None: return ()
    return tuple(name for name in name_list
                 if name not in summary.reportable)


def legend_of(summary_list, name_list):
    """
    RETURN: tuple of (str, str, str), per marker that occurs among
            'summary_list' against the page's columns 'name_list': the
            measure's tag, its name, and the formats that cannot report
            it, ','-joined -- in the columns' order (coverage D-50).
    """
    format_db = {}
    for summary in summary_list:
        for name in unreportable_of(summary, name_list):
            format_db.setdefault(name, set()).update(
                f for f in summary.format.split(",") if f)
    return tuple((measure_of(name).tag, name,
                  ",".join(sorted(format_db[name])))
                 for name in name_list if name in format_db)


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
