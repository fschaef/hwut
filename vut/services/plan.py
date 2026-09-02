"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.plan' COMMAND LINE -- what the framework INTENDS. It
         explores the directory, selects what the wish states, and
         prints the TEST PLAN: the nodes, links and exclusion sets the
         scheduler will obey (P-2, P-4, P-16).

    hwut.plan                   the plan of everything the directory
                                offers
    <the wish>                  which cases are wanted; the keywords
                                and their meaning stand in
                                'plan/wish.py', spliced into --help
    --directory=<path>          where to read; the current one else
    --help                      this text

A <point> is a span ('90s', '2h', '7d') or an anchor ('today',
'yesterday', 'last-week', 'last-month', a weekday, a month), reckoned
in UTC. Keywords of different kinds are AND'ed.

Faults print first; the plan of what stands follows all the same, since
a directory with one broken header still has a plan for the rest. The
Bookkeeper is made here and handed down, and only where the wish asks
the base.
______________________________________________________________________________
"""
import sys

from   vut.engine.orchestrator.exploration.task_list   import SelectionError
from   vut.engine.orchestrator.exploration            import selection
from   vut.services.lib.labels                             import view_at
from   vut.services.lib.labels._file                       import LabelFileError
from   vut.engine.orchestrator.exploration.tree_explorer \
                                                    import (RootConfMissing,
                                                            ascended_spec)
from   vut.engine.orchestrator.plan.determine          import determine
from   vut.engine.orchestrator.plan.printer            import print_plan
from   vut.engine.orchestrator.plan.wish               import (HELP as WISH_HELP,
                                                               WishError,
                                                               parse_wish,
                                                               with_targets)
from   vut.engine.orchestrator.plan.wish               import USAGE_TOKEN_TUPLE \
                                                               as WISH_TOKEN_TUPLE
from   ._core                                          import usage_line
from   ._exit                                          import E_ExitCode


USAGE = usage_line("usage: hwut.plan",
                    WISH_TOKEN_TUPLE
                    + ("[<file-glob> [choice-glob]...]",
                       "[--directory=<path>]"))

HELP = """hwut.plan -- the TEST PLAN the framework intends

    hwut.plan           the plan of everything the directory offers:
                        the nodes (TEST, BUILD, SESSION), the links
                        ('x -> y' ordering, 'w ==> t' supports), and
                        the exclusion sets

""" + WISH_HELP + """

    Keywords of different kinds are AND'ed. '--fail' beside '--pass'
    is refused. A wish matching nothing yields an empty plan and a
    report; the exit status is 3.

A <point> is a SPAN back from now -- a number and one of 's', 'm',
'h', 'd', as in '90s', '2h', '7d' -- or an ANCHOR, reckoned in UTC:
    today, yesterday            that day, 00:00
    last-week                   Monday of the week before, 00:00
    last-month                  the 1st of the month before, 00:00
    monday .. sunday            the most recent such day, 00:00
    january .. december         the 1st of the most recent such month

OTHER
    --directory=<path>  the directory to read; the current one else
    --help              this text

The plan is printed, never read back: to replay is to re-determine,
and determination is deterministic. Cases required by a selected case
enter by implication, marked '<= required by <target>'. A case whose
dependencies cannot be met carries '[MISDEP]': it is selected,
reported as failure, and does not run.

The configuration the framework READ is the service 'hwut.show'.

EXIT STATUS
    0    nothing refused, no fault met
    1    a fault was met
    2    the command line cannot be read, or the wish names what the
         directory does not offer
    3    the command line reads, and asks for nothing: the wish
         selects no test case"""


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (E-1): OK where nothing was
            refused and no fault was met, FAULT where one was met,
            REFUSED where the command line cannot be read or the wish
            is refused, EMPTY where the wish selects no test case.

    'write' takes one line at a time; 'print' where none is given, so
    a test may capture the face without a process.
    """
    if write is None: write = print

    if argv is None: argv = sys.argv[1:]
    if "--help" in argv:
        write(HELP)
        return E_ExitCode.OK

    try:
        wish, rest_list = parse_wish(argv)
    except WishError as error:
        write("REFUSED: %s" % error)
        write(USAGE)
        return E_ExitCode.REFUSED

    directory = "."
    unknown   = []
    word_list = []
    for argument in rest_list:
        if argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        else:
            if argument.startswith("-"): unknown.append(argument)
            else:                        word_list.append(argument)
    if unknown:
        write("REFUSED: 'hwut.plan' does not take: %s"
              % ", ".join(sorted(unknown)))
        write(USAGE)
        return E_ExitCode.REFUSED

    #  THE CLIMB APPLIES HERE TOO: a single-directory face standing
    #  in a test directory owes the same effective configuration as a
    #  walk that reached it from the project root.
    try:
        inherited, ascent_fault_list = ascended_spec(directory)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    for fault in ascent_fault_list:
        write(str(fault))

    wish = with_targets(wish, word_list)
    try:
        label_view = view_at(directory)
    except LabelFileError as error:
        write("FAULT: %s" % error)
        return E_ExitCode.FAULT
    #  ONE ACTION, ONE PLACE ('exploration/selection.py'): the
    #  explore, the Bookkeeper and the query. THIS FACE NEEDS THE
    #  QUERY ITSELF, because 'determine' takes a task list rather than
    #  a list of cases.
    found  = selection.of_directory(directory, wish, label_view,
                                    inherited=inherited)
    result = found.result_db["."]
    for fault in found.fault_tuple:
        write(str(fault))
    task_list = found.query_db["."]
    try:
        plan, report_list = determine(result.app_set, task_list)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    except SelectionError as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED

    write("WISH: %s" % wish)
    for report in report_list:
        write("REPORT: %s" % report)
    print_plan(plan, write)
    if result.fault_list:   return E_ExitCode.FAULT
    if not plan.node_tuple: return E_ExitCode.EMPTY
    return E_ExitCode.OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
