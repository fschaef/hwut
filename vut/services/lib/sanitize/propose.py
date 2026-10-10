# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
hwut.sanitize.propose -- what a tree accumulates, as commands to read,
edit and hand back.

    hwut.sanitize.propose [-o <file>] [<aspect>...] [--target <name>]
                          [--directory=<path>] [<wish>]

IT ACTS ON NOTHING AND RUNS NOTHING. It walks the tree -- below
'--directory', the current one where none is given -- and writes what it
finds as COMMANDS (services E-125), to '<file>' with '-o', else to
standard output, so '> <file>' writes the same file:

    # SESSION WRECKAGE: a 'TMP/session/' outlived its run; nothing reads
    # it between runs, and the next run makes its own.
    # 'remove' deletes the directory.
    remove engine/display/TEST/TMP/session
    remove services/TEST/TMP/session

    # BOOK BEHIND: a nominal stands in GOOD/, and the book has no entry
    # for its test (E-41).
    # 'book' enters the standing nominal as accepted; nothing runs,
    # nothing in GOOD/ moves.
    book services/TEST/test-x.py basic

ONE LINE, ONE COMMAND: '<command> <concerned entity>', the entity
relative to the CURRENT directory. A line may end in '  # <note>',
which no reader of commands reads. Issues of one kind stand in adjacent
lines; an empty line separates the kinds; a comment heads each block --
the problem, and what its command heals. Put '#' before a line, or
delete it, and it is not done; then

    hwut.sanitize.apply <file>

does what is left. Every line is also a command line of its own:
'hwut.sanitize <command> <concerned entity>' does just that one.

-------------------------------------------------------------------
WHAT IT LOOKS FOR -- each aspect by its own flag; NONE STATED MEANS ALL
OF THEM but '--transient', because a wish that states nothing wants
everything, and a bare call asks about rubbish, not about the
candidates.
-------------------------------------------------------------------
    --session   'TMP/session/' directories, the wreckage of a session
                that did not finish. Healed by 'remove'.
    --lock      'TMP/lock/' directories WHOSE HOLDER IS GONE, or which
                cannot name one. A LIVE LOCK IS NEVER PROPOSED: breaking
                it is how two runs come to write one store; where the
                platform cannot tell, the lock stays. Healed by 'remove'.
    --out       'OUT/' directories holding files: the application's
                scratch between runs. A directory a live run holds is
                not proposed, and said on stderr. Healed by 'remove'.
    --orphans   RECORDS THAT NAME NOTHING: nominals, candidates and book
                entries of a (test, choice) the configuration no longer
                offers. Healed by 'forget', through 'hwut.remove' -- or,
                where the application stands in ONE other directory with
                nothing recorded of it there, by 'move': its records are
                carried after it (E-131). Where it is recorded there
                already, or stands in several places, the 'forget' line
                says so in a note.
                AN APPLICATION THAT STANDS AND CANNOT BE EXPLORED is
                UNREACHABLE, not orphaned, and never proposed: the
                mending is in its configuration. A directory whose
                exploration faulted is not judged at all, and neither is
                one where the wish hides cases -- the hidden ones would
                look orphaned. Both are said on stderr.
    --books     THE TWO RECORDS OF ACCEPTANCE DISAGREE (E-41): a nominal
                whose test the book lacks; a book entry the book calls
                ASPIRANT while a nominal stands (B-14). Healed by 'book':
                the standing nominal is entered as accepted, nothing
                runs.
                A test in the book with no nominal is an ASPIRANT, not a
                disagreement.
    --constraints
                A NOMINAL THAT CONTRADICTS ITS OWN CONSTRAINTS (E-123).
                Healed by 'remark', which writes each finding into the
                nominal where it was made and stains the book
                'constraint'; nothing is removed. A finding already
                written is not proposed again.
    --relations 'parent' AND 'childs' AGAINST THE DIRECTORIES: every
                'hwut-composition.conf' and 'hwut-features.conf' gives
                itself an 'id', names its parent's and lists its
                childs'. A file without an id, a 'parent' that is not
                the id of the directory above, an id the directory
                above does not list: healed by 'relate', which adapts
                the statements. Where another component still lists
                the id and nothing below it carries it, the directory
                was MOVED: 'relate' carries the entry, noted 'moved
                from <dir>'. A listed id nothing carries is healed by
                'unrelate'. Two childs under one id, and a directory
                whose parent has no id, are said on stderr.
    (no option) A TREE WITHOUT A BOUNDARY (E-25): where no
                'hwut-root.conf' stands in or above the directory, the
                proposal is 'root <dir>' and nothing else -- nothing
                else can be judged without one. The repository's root
                stands uncommented, the current directory as a
                commented alternative. Healed by 'root', which writes
                the file; 'hwut.sanitize root' alone asks instead.
    --transient THE TWO TRANSIENT ROOTS WHOLE, 'OUT/' and 'TMP/' (E-24),
                candidates included. Asked for by name only; it takes
                '--session', '--lock' and '--out' with it. A directory
                a live run holds is not proposed, and said on stderr.
    --target <name>
                THE PROJECT'S OWN VERB (E-7), e.g. 'clean': one 'run'
                line for the tree. A target no directory binds is
                REFUSED BY NAME. Several may stand.

THE WISH NARROWS THE WALK, so '--glob "engine/*"' asks about part of a
tree: a directory is asked about where the wish selects anything in it.

WHAT GOES WHERE. The proposal goes to the file or to stdout and holds
only commands and comments; what CANNOT be proposed -- a directory
refused, a case not judged -- goes to STDERR as 'NOTE:', so a pipe
stays a proposal.

EXIT: OK where something was proposed, EMPTY where nothing is insane,
REFUSED where the command line cannot be read or names a target no
directory binds.
"""
import os
import sys

from vut.services                             import sanitize
from vut.services._exit                       import E_ExitCode
from vut.services.lib.cmdline                 import (face_parser, usage_of,
                                                      parse_or_refuse)
from vut.engine.bookkeeper.api                import Bookkeeper
from vut.engine.orchestrator.exploration.task_list import SelectionError
from vut.engine.orchestrator.exploration.task_list_query \
                                              import CTestTaskListQuery
from vut.engine.orchestrator.exploration.tree_explorer \
                                              import (explore_tree,
                                                      RootConfMissing)
from vut.engine.orchestrator.plan.wish        import (HELP as WISH_HELP,
                                                      WishError, parse_wish)

#  THE STANDARD READER (E-84).
PARSER = face_parser("hwut.sanitize.propose",
                     "Write -- and never do -- the commands that would "
                     "sanitize a tree.")
PARSER.add_argument("-o", "--output", default=None, metavar="file")
PARSER.add_argument("--target", action="append", default=[], metavar="name")
for _aspect in sanitize.ASPECT_TUPLE + sanitize.EXPLICIT_ASPECT_TUPLE:
    PARSER.add_argument("--" + _aspect, action="store_true")
PARSER.add_argument("--directory", default=None)
ARG_DB = {"--directory": True, "--output": True}
USAGE  = usage_of(PARSER, ARG_DB)

HELP = __doc__.strip() + "\n\n" + WISH_HELP + "\n" + USAGE


def proposal_text(issue_list, base, head_list):
    """
    RETURN: str, the proposal: the head, then one BLOCK per kind of
            issue found, in the order of 'sanitize.ISSUE_KIND_TUPLE' --
            its comment, then its commands, one per line -- the blocks
            separated by an empty line.

    'base' is where the entities are read from: the directory apply and
    the one-command face will be called in.
    """
    line_list = list(head_list)
    for kind in sanitize.ISSUE_KIND_TUPLE:
        of_kind = [issue for issue in issue_list if issue.kind == kind.name]
        if not of_kind: continue
        line_list.append("")
        line_list.extend("# %s" % text for text in kind.comment_list)
        line_list.extend(issue.line(base) for issue in of_kind)
    if not issue_list:
        line_list.append("")
        line_list.append("# nothing to sanitize")
    return "\n".join(line_list) + "\n"


def head_list_of(directory, aspect_set):
    """RETURN: list[str], the proposal's head: what was asked, and how
               the file is used."""
    return ["# hwut.sanitize.propose -- in '%s': %s"
            % (directory, ", ".join(a for a in sanitize.ASPECT_TUPLE
                                            + sanitize.EXPLICIT_ASPECT_TUPLE
                                            + ("target", "root")
                                    if a in aspect_set)),
            "#",
            "# One command per line, '<command> <concerned entity>', the entity",
            "# relative to the directory this was written in. Put '#' before a",
            "# line, or delete it, to leave it undone; then",
            "#",
            "#     hwut.sanitize.apply <this file>",
            "#",
            "# Every command judges again before it acts."]


def _stderr_line(line):
    """RETURN: None. 'line' written to stderr, terminated."""
    print(line, file=sys.stderr)


def main(argv=None, write=None, err=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    if argv is None:  argv  = sys.argv[1:]
    if write is None: write = sys.stdout.write
    if err is None:   err   = _stderr_line
    if "--help" in argv:
        from vut.services._core import man_page
        print(man_page("hwut.sanitize.propose", HELP))
        return E_ExitCode.OK

    try:
        wish, rest_list = parse_wish(argv)
    except WishError as error:
        err("REFUSED: %s" % error)
        err(USAGE)
        return E_ExitCode.REFUSED
    if rest_list and rest_list[-1] in ("--target", "-o", "--output"):
        err("REFUSED: '%s' stands without a name" % rest_list[-1])
        err(USAGE)
        return E_ExitCode.REFUSED
    arguments, completion_f = parse_or_refuse(PARSER, rest_list, err, ARG_DB)
    if completion_f:      return E_ExitCode.OK
    if arguments is None:
        err(USAGE)
        return E_ExitCode.REFUSED
    directory  = arguments.directory or "."
    aspect_set = {aspect for aspect in sanitize.ASPECT_TUPLE
                                       + sanitize.EXPLICIT_ASPECT_TUPLE
                  if getattr(arguments, aspect)}
    if not os.path.isdir(directory):
        err("REFUSED: the directory '%s' does not exist" % directory)
        err(USAGE)
        return E_ExitCode.REFUSED
    if not aspect_set: aspect_set = set(sanitize.ASPECT_TUPLE)
    if "transient" in aspect_set:
        aspect_set -= {"session", "lock", "out"}

    root = os.path.abspath(directory)
    try:
        exploration = explore_tree(root)
    except RootConfMissing:
        #  THE ONE STATE THIS FACE MUST ENTER (E-25, amended 2026-10-08):
        #  a tree without a boundary. It proposes the boundary and
        #  nothing else -- nothing else can be judged without one.
        text = proposal_text(sanitize.root_issue_list(root), os.getcwd(),
                             head_list_of(directory, {"root"}))
        return _delivered(text, arguments.output, write, err, E_ExitCode.OK)

    issue_list, note_list = [], []
    bound_set = set()
    exploration = list(exploration)
    #  WHERE ELSE AN APPLICATION OF THAT NAME STANDS (E-130): asked of
    #  an orphan whose application is gone -- it may have MOVED.
    home_db = {}
    for where, result in exploration:
        for name in result.app_set.app_db:
            home_db.setdefault(name, []).append(
                os.path.normpath(os.path.join(root, where)))
    for where, result in exploration:
        whole = os.path.normpath(os.path.join(root, where))
        bound_set.update(result.app_set.directory_spec.target_db or {})
        try:
            query = CTestTaskListQuery(wish, Bookkeeper(whole),
                                       directory=where, root=root)
            wanted_f = bool(query.get_test_cases(result.app_set))
        except SelectionError as error:
            #  A WISH THAT NAMES WHAT THE TREE DOES NOT HOLD IS REFUSED
            #  BY NAME (E-19, R-75), here as at every face: read as
            #  'not wanted' it would propose over a selection nobody
            #  could have meant.
            err("REFUSED: %s" % error)
            return E_ExitCode.REFUSED
        found, noted = sanitize.directory_issue_list(root, whole, result,
                                                     aspect_set, wanted_f)
        for issue in found:
            if issue.kind == "orphan-test":
                #  A MOVE IS AN ADD PLUS A REMOVE (E-131): what is
                #  proposed depends on what the other side holds.
                issue = sanitize.moved_issue_of(
                            issue,
                            sorted(d for d in home_db.get(issue.word_tuple[0], ())
                                   if d != whole),
                            root)
            issue_list.append(issue)
        note_list.extend(noted)

    if "relations" in aspect_set:
        from vut.engine.orchestrator.exploration.feature_relation \
                                              import relation_of_exploration
        found, noted = sanitize.relation_issue_list(
            root, relation_of_exploration(root, exploration))
        issue_list.extend(found)
        note_list.extend(noted)

    unbound_list = [name for name in arguments.target if name not in bound_set]
    for name in unbound_list:
        err("REFUSED: no directory binds a target '%s'" % name)
    if unbound_list: return E_ExitCode.REFUSED
    issue_list.extend(sanitize.CIssue("target", root, (name,))
                      for name in dict.fromkeys(arguments.target))
    if arguments.target: aspect_set.add("target")

    for note in note_list: err("NOTE: %s" % note)

    text = proposal_text(issue_list, os.getcwd(),
                         head_list_of(directory, aspect_set))
    return _delivered(text, arguments.output, write, err,
                      E_ExitCode.OK if issue_list else E_ExitCode.EMPTY)


def _delivered(text, output, write, err, status):
    """
    RETURN: E_ExitCode, 'status' where the proposal reached its sink --
                        stdout, or the file '-o' names
            E_ExitCode.REFUSED, where that file cannot be written
    """
    if output is None:
        write(text)
        return status
    try:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as error:
        err("REFUSED: cannot write '%s': %s" % (output, error))
        return E_ExitCode.REFUSED
    return status


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded("hwut.sanitize.propose", main))
