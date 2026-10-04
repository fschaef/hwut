"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.cov.conv.to_lcov' -- the output directory of a coverage
         run as ONE lcov tracefile (coverage RATIONALE D-6, D-43), for
         'genhtml' and every other tool that reads lcov.

    hwut.cov.conv.to_lcov [DIRECTORY] [-o FILE]
                                DIRECTORY is the '-o' of 'hwut.cov.run'
                                ('./hwut.coverage' where none is
                                named); the tracefile goes to FILE, or
                                to stdout.
    hwut.cov.conv.to_lcov --help
                                this text

THE MAPPING IS LOSSY BY CONSTRUCTION, as D-43 states, and in exactly
these ways:

    SF    the source's path from the run's root, made absolute with the
          root the marker names
    DA    every executable line, count 1 where ANY test run executed it
          and 0 where none did -- hwut carries no hit counts
    FN    every function point, at its line; FNDA 1 or 0
    BRDA  every arm of every decision: the BLOCK is the decision's place
          among the decisions of its line, the BRANCH the arm's index;
          taken is 1 or 0, and '-' where the decision's line was never
          executed, as lcov spells a block never entered
    TG CP dropped: lcov has no toggle and no cover point
    MC    dropped, OWED: lcov 2.2 spells MC/DC, but no reader produces
          the measure yet and no tracefile carrying it was witnessed;
          writing the line from memory would be the invention every
          reader of this component refuses

WHO EXECUTED WHAT -- the test runs and the groups behind each range --
is what lcov cannot say and this component's own files do. The
tracefile is a presentation for the tools that want lcov; the output
directory stays the one place the data is kept.

The exit status (E-1): OK with the tracefile written, FAULT where the
directory cannot be read, REFUSED where the command line cannot be.
______________________________________________________________________________
"""
import os
import sys

from   vut.engine.coverage.api   import OutputRefused, root_of
from   vut.engine.coverage.api   import DEFAULT_DIRECTORY_NAME
from   vut.services._exit        import E_ExitCode
from   vut.services.lib.cov.summary import summaries_of

NAME  = "hwut.cov.conv.to_lcov"
USAGE = "usage: %s [DIRECTORY] [-o FILE] | --help" % NAME
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip()


def lcov_lines(root, summary_list):
    """
    YIELD: str, one line of the lcov tracefile, without its newline:
           per source file 'TN:', 'SF:', the functions, the branches,
           the lines, 'end_of_record'; the sources in path order.

    'root' is the run's root (None where unknown), 'summary_list' the
    'SourceSummary' list of 'cov/summary.py'.
    """
    for summary in summary_list:
        covered_set = {line for begin, end in summary.covered
                       for line in range(begin, end)}
        yield "TN:"
        yield "SF:%s" % (os.path.join(root, *summary.source.split("/"))
                         if root is not None else summary.source)

        function_tuple = summary.measure_db.get("function", ())
        for line, name, _, _ in function_tuple:
            yield "FN:%i,%s" % (line, name)
        for _, name, entered, _ in function_tuple:
            yield "FNDA:%i,%s" % (entered, name)
        if function_tuple:
            yield "FNF:%i" % len(function_tuple)
            yield "FNH:%i" % sum(entered for _, _, entered, _
                                 in function_tuple)

        branch_tuple = summary.measure_db.get("branch", ())
        found_n = taken_n = 0
        block_db = {}
        for line, mask, total in branch_tuple:
            block = block_db.get(line, 0)
            block_db[line] = block + 1
            for arm in range(total):
                taken = (mask >> arm) & 1
                yield "BRDA:%i,%i,%i,%s" % (
                    line, block, arm,
                    "-" if line not in covered_set else str(taken))
                found_n += 1
                taken_n += taken
        if branch_tuple:
            yield "BRF:%i" % found_n
            yield "BRH:%i" % taken_n

        line_n = hit_n = 0
        for begin, end in summary.executable:
            for line in range(begin, end):
                hit = 1 if line in covered_set else 0
                yield "DA:%i,%i" % (line, hit)
                line_n += 1
                hit_n  += hit
        yield "LF:%i" % line_n
        yield "LH:%i" % hit_n
        yield "end_of_record"


def main(argv=None, write=None, write_bytes=None):
    """
    RETURN: E_ExitCode (E-1): OK with the tracefile written, FAULT
            where the output directory cannot be read, REFUSED where
            the command line cannot be read.

    'write' takes one line of text; 'write_bytes' takes the tracefile
    whole where no '-o' names a file -- stdout's buffer where none is
    given, so a test may capture the face without a process.
    """
    if write is None:       write = print
    if write_bytes is None: write_bytes = sys.stdout.buffer.write
    if argv is None:        argv = sys.argv[1:]

    if "--help" in argv or "-h" in argv:
        write(HELP)
        return E_ExitCode.OK

    directory_list, target = [], None
    i = 0
    while i < len(argv):
        word = argv[i]
        if word in ("-o", "--output"):
            if i + 1 >= len(argv) or target is not None:
                write("REFUSED: '%s' takes one FILE, once" % word)
                write(USAGE)
                return E_ExitCode.REFUSED
            target = argv[i + 1]; i += 2
        elif word.startswith("-"):
            write("REFUSED: unknown option '%s'" % word); write(USAGE)
            return E_ExitCode.REFUSED
        else:
            directory_list.append(word); i += 1
    if len(directory_list) > 1:
        write("REFUSED: %s takes at most one DIRECTORY" % NAME)
        write(USAGE)
        return E_ExitCode.REFUSED
    directory = directory_list[0] if directory_list \
                else os.path.join(os.getcwd(), DEFAULT_DIRECTORY_NAME)
    if not os.path.isdir(directory):
        write("FAULT: '%s' is no directory" % directory)
        return E_ExitCode.FAULT
    if root_of(directory) is None:
        write("FAULT: '%s' carries no marker of a coverage run; name "
              "the '-o' directory of 'hwut.cov.run'" % directory)
        return E_ExitCode.FAULT

    try:
        root, summary_list = summaries_of(directory)
        text = "\n".join(lcov_lines(root, summary_list))
    except OutputRefused as refusal:
        write("FAULT: %s" % refusal)
        return E_ExitCode.FAULT
    data = (text + "\n" if text else "").encode("utf-8")
    if target is None:
        write_bytes(data)
    else:
        try:
            with open(target, "wb") as handle: handle.write(data)
        except OSError as fault:
            write("FAULT: %s" % fault)
            return E_ExitCode.FAULT
    return E_ExitCode.OK


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from vut.services._exit import guarded
    sys.exit(guarded(NAME, main, sys.argv[1:]))
