"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READER FOR LUACOV -- and the one artifact of the two it
         writes that can be read honestly.

DESCRIPTION
       LUACOV WRITES TWO FILES, AND ONLY ONE OF THEM IS ENOUGH.

       'luacov.stats.out', the raw counters, is a count per line:

           14:app.lua
           1 0 1 1 1 0 0 1 0 1 0 1 0 1

       Line 2 is BLANK and counts 0. Line 7 is 'return 0' -- executable,
       never run -- and counts 0. NOTHING IN THIS FILE TELLS THEM APART.
       A reader over it could report CV correctly and would have to
       INVENT EX: take EX = CV and every file is 100% covered, which is a
       false green of the plainest kind; take EX = every line and every
       blank line and every 'end' is reported uncovered, which is a false
       red that makes the measurement useless.

       'luacov.report.out', which the 'luacov' command writes FROM those
       counters, knows the difference -- it has the source beside them:

            1 local M = {}
                                 <- blank: not executable
            1 function M.used(n)
                  end            <- 'end': not executable, no count
           *0     return 0       <- EXECUTABLE, NEVER RUN
            1 return M

       So this reader reads the REPORT. The stats file is deliberately
       not read at all: a reader that produced a plausible number from
       insufficient data would be worse than none.

       THE COUNT FIELD IS RIGHT-ALIGNED IN A WIDTH THE FILE CHOOSES --
       wide enough for its largest count, and a missed line is a '0'
       padded with '*' ('*0', '****0'). The width is therefore not a
       constant and is DERIVED per section: it is the smallest W such
       that every non-blank line of the section has a blank at W and
       nothing but ' ', '*' and digits before it. One space separates the
       field from the source.

       LINE NUMBERS ARE IMPLICIT: the Nth line after a section's header
       is source line N, blank ones included. That is what makes the
       report readable at all, and it is also why a truncated report
       would misattribute every line after the truncation -- so a section
       is read whole or not at all.

       NO SECOND CALL IS NAMED. Producing the report is 'luacov' run over
       the stats, which is a process -- but it needs the LUA_PATH the
       test ran under, and this component does not know it. The author
       runs 'luacov' as part of the test, as they already run 'lua'.
______________________________________________________________________________
"""
import io
import os

from ..reader import (CCoverageFramework, CCoverageFormat,
                      register, artifact_directory_of,
                      relative_path, wanted, record_of)


REPORT_NAME   = "luacov.report.out"
SECTION_RULE  = "=" * 10          # the report's separator, at least this
_FIELD_SET    = set(" *0123456789")


class LuacovFormat(CCoverageFormat):
    """luacov, through the report its own command writes."""
    name = "luacov-report"

    def read(self, work_dir, source_root, config=None):
        """
        RETURN: CoverageRecord, of the luacov report.
                None, where none stands -- ABSENT.
        """
        path = os.path.join(artifact_directory_of(work_dir), REPORT_NAME)
        if not os.path.isfile(path): return None
        with io.open(path, "r", encoding="utf-8",
                     errors="replace") as handle:
            section_db = read_report(handle.read())
        if not section_db: return None

        counts_f = bool(config is not None and config.counts)
        return record_of(self, "lua",
                         entry_iterable(section_db, source_root, config,
                                        counts_f),
                         counts_f)


class LuacovFramework(CCoverageFramework):
    """luacov: invocation; reads LuacovFormat."""
    name   = "luacov"
    format = LuacovFormat()

    def wrap(self, argv, config, work_dir):
        """
        RETURN: list[str], 'argv' unchanged. luacov is switched on from
        INSIDE the application ('require("luacov")'), not from outside
        it: there is nothing here to wrap.
        """
        return list(argv)

    def report_argv(self, config, work_dir):
        """RETURN: None. See the module header: producing the report
        needs the LUA_PATH the test ran under, which this component does
        not know."""
        return None


def read_report(text):
    """
    RETURN: dict, source path -> {line number: count}; the count is None
            where the line is EXECUTABLE AND NEVER RUN, and the line is
            absent altogether where it is not executable.

    The trailing 'Summary' section is not a file and is skipped: it names
    no source, and its own table would otherwise read as one.
    """
    result   = {}
    line_list = text.splitlines()
    i, n      = 0, len(line_list)
    while i < n:
        if not line_list[i].startswith(SECTION_RULE):
            i += 1
            continue
        #  A section is: rule, NAME, rule, then the annotated source.
        if i + 2 >= n: break
        name = line_list[i + 1].strip()
        if not line_list[i + 2].startswith(SECTION_RULE):
            i += 1
            continue
        i += 3
        body = []
        while i < n and not line_list[i].startswith(SECTION_RULE):
            body.append(line_list[i])
            i += 1
        if name and name != "Summary":
            result[name] = _line_db_of(body)
    return result


def _line_db_of(body_list):
    """
    RETURN: dict, line number -> count, or None where executable and
            never run. A line that is not executable does not appear.

    The last line of a section's body is the blank one the reporter puts
    before the next rule; it is dropped so that it does not become a
    source line that does not exist.
    """
    while body_list and not body_list[-1].strip():
        body_list = body_list[:-1]

    width = _field_width_of(body_list)
    if width is None: return {}

    result = {}
    for i, raw in enumerate(body_list, start=1):
        if len(raw) <= width: continue          # blank: not executable
        field = raw[:width].strip()
        if not field: continue                  # spaces: not executable
        if field.strip("*") == "0":
            result[i] = None                    # '*0': never executed
            continue
        try:    result[i] = int(field)
        except ValueError: continue
    return result


def _field_width_of(body_list):
    """
    RETURN: int, the width of the count field in this section -- the
            SMALLEST W such that every non-blank line carries a blank at
            W and nothing but ' ', '*' and digits before it.
            None, where no such W stands: the section is then not read,
            rather than read at a guessed width.

    The width is the file's own, wide enough for its largest count, so it
    cannot be a constant: ' 1 ' in one file and '  1501 ' in another.
    """
    candidate_list = [raw for raw in body_list if raw.strip()]
    if not candidate_list: return None

    longest = max(len(raw) for raw in candidate_list)
    for width in range(1, longest):
        if all(len(raw) > width
               and raw[width] == " "
               and not (set(raw[:width]) - _FIELD_SET)
               for raw in candidate_list):
            return width
    return None


def entry_iterable(section_db, source_root, config, counts_f):
    """
    YIELD: (path, executable_lines, covered_lines, count_list) per source
           file inside the gather set.

    EX is every line the report gave a field to -- counted or '*0'. CV is
    those whose count is not None and above zero.
    """
    from ..record import ranges_of
    for raw_path in sorted(section_db):
        path = relative_path(raw_path, source_root)
        if not wanted(path, config): continue
        line_db    = section_db[raw_path]
        executable = sorted(line_db)
        covered    = [n for n in executable
                      if line_db[n] is not None and line_db[n] > 0]
        count_list = None
        if counts_f:
            count_list = [max(line_db[n] for n in range(begin, end)
                              if line_db.get(n) is not None)
                          for begin, end in ranges_of(covered)]
        yield path, executable, covered, count_list


register(LuacovFramework())
