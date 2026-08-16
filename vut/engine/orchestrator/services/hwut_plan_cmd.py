"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.plan' COMMAND LINE -- what the framework INTENDS. It
         explores the directory, selects what the wish states, and
         prints the TEST PLAN: the nodes, links and exclusion sets the
         scheduler will obey (P-2, P-4, P-16).

    hwut.plan                   the plan of everything the directory
                                offers
    --fail                      the last recorded run failed
    --pass                      the last recorded run stood
    --since=<point>             the last run lies at or after the point
    --until=<point>             the last run lies before the point --
                                the never-run counted
    --glob <target>             'test-*.py quick-[0-2]'; several times,
                                OR'ed among themselves
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

from ..exploration.explorer        import explore
from ..exploration.task_list       import SelectionError
from ..exploration.task_list_query import CTestTaskListQuery
from ..plan.determine              import determine
from ..plan.printer                import print_plan
from ..plan.wish                   import WishError, parse_wish
from ..bookkeeper.bookkeeper       import Bookkeeper


USAGE = "usage: hwut.plan [--fail] [--pass] [--since=<point>] " \
        "[--until=<point>]\n" \
        "                 [--glob <target>]... [--directory=<path>]"

HELP = """hwut.plan -- the TEST PLAN the framework intends

    hwut.plan           the plan of everything the directory offers:
                        the nodes (TEST, BUILD, SESSION), the links
                        ('x -> y' ordering, 'w ==> t' supports), and
                        the exclusion sets

SELECTION -- the wish; an absent keyword asks nothing
    --fail              the last recorded run's verdict was negative
    --pass              the last recorded run's verdict was positive
    --since=<point>     the last recorded run lies AT or AFTER the
                        point; a case never run is not wanted
    --until=<point>     the last recorded run lies BEFORE the point,
                        and a case NEVER RUN is wanted too -- the
                        stale wish
    --glob <target>     a target: a file name, or a file name and a
                        choice name with one blank between, either
                        carrying fnmatch's '*', '?' and '[ ]':
                            --glob "test-*.py quick-[0-2]"
                        may stand several times; the globs are OR'ed
                        among themselves

    Keywords of different kinds are AND'ed. '--fail' beside '--pass'
    is refused. A wish matching nothing yields an empty plan and a
    report, not a refusal.

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
         directory does not offer"""


def main(argv, write=None):
    """
    RETURN: int, the exit status: 0 where nothing was refused and no
            fault was met, 1 where a fault was met, 2 where the
            command line cannot be read or the wish is refused.

    'write' takes one line at a time; 'print' where none is given, so
    a test may capture the face without a process.
    """
    if write is None: write = print

    if "--help" in argv:
        write(HELP)
        return 0

    try:
        wish, rest_list = parse_wish(argv)
    except WishError as error:
        write("REFUSED: %s" % error)
        write(USAGE)
        return 2

    directory = "."
    unknown   = []
    for argument in rest_list:
        if argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        else:
            unknown.append(argument)
    if unknown:
        write("REFUSED: 'hwut.plan' does not take: %s"
              % ", ".join(sorted(unknown)))
        write(USAGE)
        return 2

    result = explore(directory)
    for fault in result.fault_list:
        write(str(fault))

    bookkeeper = Bookkeeper(directory) if wish.asks_base_f() else None
    task_list  = CTestTaskListQuery(wish, bookkeeper)
    try:
        plan, report_list = determine(result.app_set, task_list)
    except SelectionError as error:
        write("REFUSED: %s" % error)
        return 2

    write("WISH: %s" % wish)
    for report in report_list:
        write("REPORT: %s" % report)
    print_plan(plan, write)
    return 1 if result.fault_list else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
