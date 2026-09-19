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
from   vut.engine.orchestrator.plan.tree               import admit_of
from   vut.engine.orchestrator.plan.printer            import print_plan
from   vut.engine.orchestrator.plan.wish               import (HELP as WISH_HELP,
                                                               WishError,
                                                               parse_wish,
                                                               with_targets)
from   ._exit                                          import E_ExitCode
from   ._target                                        import entered
from   vut.services.lib.cmdline import (face_parser, usage_of,
                                        parse_or_refuse)
from   vut.services.lib.face    import Refused, Fault, answered
from   vut.engine.orchestrator.plan.wish import Wish
from   vut.engine.orchestrator.plan.form import E_LinkKind, E_Provenance
from   dataclasses import dataclass


#  THE STANDARD READER (E-84).
PARSER = face_parser("hwut.plan",
                     "Print the plan the wish determines, never run it.",
                     word_help="a test, a test and a choice, a file glob "
                               "and a choice glob",
                     word_metavar="[<file-glob> [choice-glob]...]")
PARSER.add_argument("--directory", default=None,
                    help="the directory to read; the current one else")
ARG_DB = {"--directory": True}
USAGE  = usage_of(PARSER, ARG_DB)

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

The configuration the framework READ is the service 'hwut.config.show'.

EXIT STATUS
    0    nothing refused, no fault met
    1    a fault was met
    2    the command line cannot be read, or the wish names what the
         directory does not offer
    3    the command line reads, and asks for nothing: the wish
         selects no test case"""


@dataclass(frozen=True)
class Node:
    """One node of the plan, as a page shows it (E-101)."""
    name:        str
    kind:        str
    misdep_f:    bool = False
    implied_by:  str | None = None


@dataclass(frozen=True)
class Link:
    """One link: its two ends and the arrow between them."""
    source: str
    arrow:  str
    target: str


@dataclass(frozen=True)
class Request:
    """WHAT WAS ASKED of 'hwut.plan': the wish, and where."""
    directory:     str = "."
    fail_f:        bool = False
    pass_f:        bool = False
    since_spec:    str | None = None
    until_spec:    str | None = None
    glob_tuple:    tuple = ()
    exclude_tuple: tuple = ()
    dir_tuple:     tuple = ()
    exclude_dir_tuple: tuple = ()
    wishlist_f:    bool = False
    label_spec:    str | None = None
    language_tuple:tuple = ()
    faster_than_ms:int | None = None
    unaccepted_f:  bool = False


@dataclass(frozen=True)
class Result:
    """WHAT HAPPENED: the wish as it reads, what was reported, what was
    refused, and the plan -- nodes, links, exclusion sets."""
    wish_text:      str = ""
    report_tuple:   tuple = ()
    refused_tuple:  tuple = ()      # (name, reason)
    fault_tuple:    tuple = ()      # the faults, as text
    node_tuple:     tuple = ()      # of Node
    link_tuple:     tuple = ()      # of Link
    exclusion_tuple:tuple = ()      # of tuple[str]
    fault_f:        bool = False


def request_of(wish, directory):
    """RETURN: Request, a Wish and a directory as plain fields."""
    return Request(
        directory     = directory,
        fail_f        = bool(wish.fail_f),
        pass_f        = bool(wish.pass_f),
        since_spec    = wish.since_spec,
        until_spec    = wish.until_spec,
        glob_tuple    = tuple(wish.glob_tuple),
        exclude_tuple = tuple(wish.exclude_tuple),
        dir_tuple     = tuple(wish.dir_tuple),
        exclude_dir_tuple = tuple(wish.exclude_dir_tuple),
        wishlist_f    = bool(wish.wishlist_f),
        label_spec    = wish.label_spec,
        language_tuple= tuple(wish.language_tuple),
        faster_than_ms= wish.faster_than_ms,
        unaccepted_f  = bool(wish.unaccepted_f))


def wish_of(request):
    """RETURN: Wish, the engine's, as 'request' states it."""
    return Wish(fail_f=request.fail_f, pass_f=request.pass_f,
                since_spec=request.since_spec, until_spec=request.until_spec,
                glob_tuple=tuple(request.glob_tuple),
                exclude_tuple=tuple(request.exclude_tuple),
                dir_tuple=request.dir_tuple,
                exclude_dir_tuple=request.exclude_dir_tuple,
                wishlist_f=request.wishlist_f,
                label_spec=request.label_spec,
                language_tuple=request.language_tuple,
                faster_than_ms=request.faster_than_ms,
                unaccepted_f=request.unaccepted_f)


def do(request):
    """
    RETURN: Result, the plan the request determines -- its nodes, links
            and exclusion sets, the wish as it reads, what was reported
            and what was refused.

    RAISES: Refused, where no root conf stands above the directory or
            the wish names what the tree does not hold; Fault, where a
            label file cannot be read.

    IT NEVER PRINTS (E-101).
    """
    directory = request.directory or "."
    wish      = wish_of(request)
    try:
        inherited, ascent_fault_list = ascended_spec(directory)
    except RootConfMissing as error:
        raise Refused("REFUSED: %s" % error) from error
    try:
        label_view = view_at(directory)
    except LabelFileError as error:
        raise Fault("FAULT: %s" % error) from error
    found  = selection.of_directory(directory, wish, label_view,
                                    inherited=inherited)
    result = found.result_db["."]
    try:
        plan, report_list, refused_list = determine(
            result.app_set, found.query_db["."], admit=admit_of(directory))
    except (RootConfMissing, SelectionError) as error:
        raise Refused("REFUSED: %s" % error) from error
    fault_tuple = tuple(str(f) for f in ascent_fault_list) \
                  + tuple(str(f) for f in found.fault_tuple)
    return Result(
        wish_text      = str(wish),
        report_tuple   = tuple(str(r) for r in report_list),
        refused_tuple  = tuple((str(n), str(r)) for n, r in
                               tuple(result.refused_tuple) + tuple(refused_list)),
        fault_tuple    = fault_tuple,
        node_tuple     = tuple(Node(node.name(), node.kind.name,
                                    bool(node.misdep_f),
                                    node.implied_by
                                    if node.provenance is E_Provenance.IMPLIED
                                    else None)
                               for node in plan.node_tuple),
        link_tuple     = tuple(Link(str(l.source),
                                    "->" if l.kind is E_LinkKind.ORDERING else "==>",
                                    str(l.target)) for l in plan.link_tuple),
        exclusion_tuple= tuple(tuple(e.member_tuple) for e in plan.exclusion_tuple),
        fault_f        = bool(result.fault_list))


def printed(result, write):
    """RETURN: E_ExitCode. The page 'hwut.plan' has always written, out
               of the record: the faults, the wish, the reports, the
               refusals, then the plan."""
    for text in result.fault_tuple:  write(text)
    write("WISH: %s" % result.wish_text)
    for report in result.report_tuple: write("REPORT: %s" % report)
    for name, reason in result.refused_tuple:
        write("REFUSED: %s -- %s" % (name, reason))
    write("TEST PLAN: %d node(s), %d link(s), %d exclusion set(s)"
          % (len(result.node_tuple), len(result.link_tuple),
             len(result.exclusion_tuple)))
    write("NODES")
    if not result.node_tuple: write("    (none)")
    else:
        width = max(len(node.name) for node in result.node_tuple)
        for node in result.node_tuple:
            text = "%-*s  %-7s" % (width, node.name, node.kind)
            if node.misdep_f:             text += "  [MISDEP]"
            if node.implied_by is not None:
                text += "  <= required by %s" % node.implied_by
            write("    %s" % text.rstrip())
    write("LINKS")
    if not result.link_tuple: write("    (none)")
    else:
        for link in result.link_tuple:
            write("    %s %s %s" % (link.source, link.arrow, link.target))
    write("EXCLUSIONS")
    if not result.exclusion_tuple: write("    (none)")
    else:
        for member_tuple in result.exclusion_tuple:
            write("    { %s }" % ", ".join(member_tuple))
    if result.fault_f:        return E_ExitCode.FAULT
    if not result.node_tuple: return E_ExitCode.EMPTY
    return E_ExitCode.OK


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

    arguments, completion_f = parse_or_refuse(PARSER, rest_list, write,
                                              ARG_DB)
    if completion_f:      return E_ExitCode.OK
    if arguments is None:
        write(USAGE)
        return E_ExitCode.REFUSED
    directory = arguments.directory or "."
    word_list = arguments.word

    #  A TEST NAMED BY PATH IS ENTERED ('services/_target.py', E-47).
    found = entered(word_list, directory, write, USAGE)
    if found is None: return E_ExitCode.REFUSED
    directory, word_list = found
    return answered(do, request_of(with_targets(wish, word_list), directory),
                    write, printed)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ._exit import guarded
    sys.exit(guarded("hwut.plan", main, sys.argv[1:]))
