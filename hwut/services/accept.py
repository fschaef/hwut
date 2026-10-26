"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.accept' COMMAND LINE -- PROMOTION. A candidate that
         a run recorded becomes the NOMINAL: the pole of goodness the
         framework judges every later run against.

         'Store.accept()' is the only way a nominal comes to exist;
         this face is the only thing that calls it.

    hwut.accept                 every candidate the wish selects
    <the wish>                  which cases are wanted; the keywords
                                stand in 'plan/wish.py'
    <file-glob> [choice-glob]...
                                the SHORT FORM -- sugar over the
                                wish's '--glob' target (R-34):

                                    hwut.accept "[tT]est-*.cpp"
                                    hwut.accept "test-*.py" one two

                                the first word names files, every
                                further word a choice; both carry
                                fnmatch's '*', '?' and '[ ]'
    --whole, --as-is, --force   overwrite a standing nominal with the
                                recording, without the merge. A first
                                acceptance blesses the recording whole
                                without them (E-188). One act, three
                                spellings (E-109)
    --directory=<path>          ONE directory; the whole tree else
    --help                      this text

WHAT ACCEPT DOES NOT DO: it never overwrites a standing nominal unless
'--force' says so out loud. Where a nominal stands, the candidate is
not a first blessing but a CHANGE, and a change is 'hwut.merge's
business -- accept names the key, refers to 'hwut.merge' and leaves the
pole alone. It asks nothing and opens no screen (E-167): the face has
one task, and undoing it is the configuration management's (git).

EXIT STATUS (E-1, services/_exit.py):
    0  everything the wish selected was accepted, or needed nothing
    1  a fault was met, a case was refused, or a key needed a merge
       and was left alone
    2  the command line cannot be read
    3  the command line reads, and asks for nothing
______________________________________________________________________________
"""
import argparse
import asyncio
import time
from .lib.face import write_refusal
from .lib import preferences
from dataclasses import replace, dataclass
import os
import sys

from   hwut.engine.orchestrator.exploration.tree_explorer \
                                                       import (RootConfMissing,
                                                               ascended_spec)
from ..engine.display.word import CInk
from ..engine.display.console import colour_decision
from ..engine.operations.result import E_TestRunResult
from ..engine.bookkeeper.api import carries_unaccepted_text_f
from ..engine.bookkeeper.api import Store, unstable_f
from ..engine.orchestrator.exploration.task_list import SelectionError
from ..engine.orchestrator.exploration import selection
from .lib.labels import view_at
from .lib.labels._file import LabelFileError
from ..engine.orchestrator.plan.wish import (HELP as WISH_HELP,
                                                               WishError,
                                                               parse_wish,
                                                               with_targets)
from ..engine.orchestrator.run.adapter import \
                                                       test_configuration_of
from   ._exit                                          import E_ExitCode
from   ._target                                        import entered
from .lib.cmdline import (face_parser, usage_of,
                                        parse_or_refuse)


#  THE STANDARD READER (E-84).
PARSER = face_parser("hwut.accept",
                     "PROMOTION: a candidate becomes the nominal.",
                     word_help="a test, a test and a choice, a file glob "
                               "and a choice glob",
                     word_metavar="[<file-glob> [choice-glob]...]")
#  GONE, AND REFUSED BY NAME: both stay readable so a script that still
#  says them is told, never silently obeyed; neither shows in the usage.
PARSER.add_argument("--dont-ask", action="store_true", help=argparse.SUPPRESS)
PARSER.add_argument("--digest", action="append", default=[], metavar="tag")
PARSER.add_argument("-f", "--force", action="store_true")
PARSER.add_argument("--whole", "--as-is", dest="force", action="store_true")
PARSER.add_argument("--force-run", action="store_true",
                    help=argparse.SUPPRESS)
PARSER.add_argument("--directory", default=None)
ARG_DB = {"--directory": True}
USAGE  = usage_of(PARSER, ARG_DB)

HELP = """hwut.accept -- PROMOTION: a candidate becomes the nominal

    hwut.accept         blesses every candidate the wish selects that
                        has no nominal yet -- the FIRST pole. Where a
                        nominal already stands, the key is named and
                        left alone: that is 'hwut.merge's business.

""" + WISH_HELP + """

THE SHORT FORM -- sugar over '--glob', not a second selection language
    <file-glob> [choice-glob]...
                        the first word names files, every further word
                        names a choice; both carry fnmatch's '*', '?'
                        and '[ ]'. These say the same thing:

                            hwut.accept "test-*.py" one two
                            hwut.accept --glob "test-*.py one" \\
                                        --glob "test-*.py two"

                        a file word alone means EVERY choice of it

PROMOTION
    ACCEPT ASKS NOTHING (E-167). It blesses what the words select, at
    once; undoing it is git's. Where a nominal stands it refers to
    'hwut.merge', which alone merges.
    --digest=<tag>      bless only the recording 'hwut.play' named with
                        this tag ('RECORDED: <file> (digest: <tag>)').
                        A different recording is refused. The words
                        must select exactly ONE case; a wishlist gives
                        each of its literal lines a tag of its own
    --whole, --as-is, --force
                        overwrite a standing nominal with the recording,
                        skipping the merge; a first acceptance blesses
                        the recording whole without them (E-188). ONE ACT: what it replaces is an earlier
                        accept, never the author's evidence -- a GOOD
                        file cannot exist without this face (E-109).
    A BARE 'hwut.accept' WALKS THE TREE, as 'hwut.run' does -- the
    failures a run reports do not sit in one directory.
    '--directory=<path>' names one directory and reads that alone.

    ACCEPT RUNS NOTHING (E-165). It blesses the RECORDING that
    'hwut.play' or 'hwut.run' left -- what was seen -- and says which
    face made it and when. A case with no recording is refused; a
    recording whose test source changed since is blessed, with a HINT.
    '--force-run' is gone: 'hwut.play' records afresh.

        hwut.play test-a.py one        run, show, record
        hwut.accept test-a.py one      bless what was recorded
    --directory=<path>  where to read; the current one else

STDERR IS NEVER SUBJECT TO TESTING
    stderr is for ERROR REPORTING; that is its whole job. It is never
    a nominal, never compared, never pype-d. Where error reporting is
    itself the thing under test, the application flushes it to a FILE
    and names that file in the 'output' parameter. Accordingly there
    is no 'accept stderr as nominal' here, and never will be.

THE CLOSING TOKEN
    A candidate whose stdout does not end in the line '<hwut-end>' is
    REFUSED: the stream never testified its completeness -- it was
    cut short, aborted, or the application does not follow R-70. No
    flag bypasses this; '--force' overrides a standing pole, never
    stream integrity.

WHAT IS SHOWN BEFORE A BLESSING
    The CANDIDATE, which is the canonicalised record -- what the
    framework actually compares. The pre-canonicalisation stream is
    kept beside it as '.raw' evidence and is named, not printed.

EXIT STATUS
    0   everything selected was accepted, or needed nothing
    1   a fault was met, a case was refused, or a key needed a merge
        and was left alone
    2   the command line cannot be read
    3   the command line reads, and asks for nothing

OTHER
    --help              this text"""


#  Sidecars live beside a candidate under the same stem; they are not
#  subjects and are never promoted.

#  STDERR IS NEVER SUBJECT TO TESTING: it is for error reporting, and
#  that is its whole job. It is never a nominal, never compared, never
#  pype-d. Where error reporting is itself under test, the application
#  flushes it to a FILE and names that file in 'output'.
#
#  So stderr is never PROMOTED. The one thing acceptance decides about
#  it is the NOTE, and only where it spoke -- see 'stderr_decision'.
STDERR_SUBJECT = "stderr"


def subject_tuple_of(store, test, choice):
    """
    RETURN: tuple, the subjects recorded for that key, sorted -- the
            names under the candidate's stem with the sidecars
            ('.raw', '.times', '.when') left out; empty where the run
            recorded nothing.
    """
    from ..engine.bookkeeper.api import (SUBJECT_BY_SUFFIX_DB,
                                           SIDECAR_SUFFIX_TUPLE)
    probe     = store.bookkeeper.candidate_path(test, choice, "s")
    directory = probe.parent
    stem      = probe.name[:-len("s")]        # 'test--choice.'
    if not directory.is_dir(): return ()
    name_list = []
    for path in directory.iterdir():
        name = path.name
        if not name.startswith(stem):                       continue
        if name.endswith(SIDECAR_SUFFIX_TUPLE):             continue
        suffix = name[len(stem):]
        #  THE ERROR WITNESS IS NOT A SUBJECT (E-5): 'OUT/<key>.err'
        #  stands beside the candidates and is NEVER promoted. Refused
        #  here by name, so that it can never be read as one.
        if suffix == "err":                                 continue
        #  THE FILE WEARS A SUFFIX; THE SUBJECT HAS A NAME: '.txt' is
        #  the stdout subject. The bookkeeper holds the table.
        name_list.append(SUBJECT_BY_SUFFIX_DB.get(suffix, suffix))
    return tuple(sorted(name_list))


def read_text(path):
    """
    RETURN: str, the file's content; None where it cannot be read.
    """
    try:
        with open(path, encoding="utf-8", newline="") as file_handle:
            return file_handle.read()
    except OSError:
        return None


class CKey:
    """One promotable thing: a test, a choice, a subject -- and what
    stands for it in the store."""
    __slots__ = ("test", "source_file", "choice", "subject",
                 "candidate_path", "nominal_path", "shared_f")

    def __init__(self, test, source_file, choice, subject,
                 candidate_path, nominal_path, shared_f):
        """RETURN: CKey, one (test, choice, subject) with its paths.

        'test' is the STEM, which is what recording used as the test's
        identity ('operations/session.py': configuration.stem);
        'source_file' is what the eye reads."""
        self.test           = source_file and test
        self.source_file    = source_file
        self.choice         = choice
        self.subject        = subject
        self.candidate_path = candidate_path
        self.nominal_path   = nominal_path
        self.shared_f       = shared_f

    @property
    def name(self):
        """RETURN: str, the key as the eye reads it."""
        if self.choice is None:
            return "%s .%s" % (self.source_file, self.subject)
        return "%s %s .%s" % (self.source_file, self.choice,
                              self.subject)

    @property
    def nominal_stands_f(self):
        """RETURN: bool, True where a nominal already stands."""
        return self.nominal_path.exists()


def key_list_of(store, case_sequence):
    """
    RETURN: list[CKey], every promotable key of the selected cases, in
            walk order -- one per (test, choice, subject) that a run
            actually recorded.

    'shared_f' marks a key whose nominal is shared by every choice of
    the test ('same', B-30): blessing one choice there rewrites
    the pole the others are judged by.
    """
    key_list = []
    for case in case_sequence:
        #  RECORDING keys by the STEM, so acceptance must too, or it
        #  looks where nothing was ever written.
        test   = case.source_file
        choice = case.choice
        #  A STAINED CHOICE IS NEVER PROMOTED. Acceptance declares the
        #  POLE of the good cluster; a choice that switches results has
        #  no cluster to be the centre of, and blessing one of its runs
        #  would write the false testimony into the nominal itself.
        if unstable_f(store.bookkeeper.stain(test, choice)): continue
        for subject in subject_tuple_of(store, test, choice):
            if subject == STDERR_SUBJECT: continue      # never promoted
            key_list.append(CKey(
                test, case.source_file, choice, subject,
                store.bookkeeper.candidate_path(test, choice, subject),
                store.bookkeeper.nominal_path(test, choice, subject),
                store.bookkeeper.naming.shared_f(test)))
    return key_list


def shared_conflict_db(key_list):
    """
    RETURN: dict, nominal path -> the keys sharing it, for every shared
            nominal whose candidates DISAGREE.

    Under 'same_nominal_f' the author declared that every choice
    produces the same behaviour. Where the candidates differ, that
    premise is broken: there is no principled way to pick a winner, so
    accept names it instead of blessing one arbitrarily.
    """
    group_db = {}
    for key in key_list:
        if not key.shared_f: continue
        group_db.setdefault(str(key.nominal_path), []).append(key)
    conflict_db = {}
    for path_text, group in group_db.items():
        if len(group) < 2: continue
        text_set = set(read_text(key.candidate_path) for key in group)
        if len(text_set) > 1: conflict_db[path_text] = group
    return conflict_db


def proposal_targets(file_name):
    """
    RETURN: list of (directory, target) -- one per line the file names,
            in the order written. 'directory' is the path part, '' for
            a bare name; 'target' is the test application and, where
            one stands, its choice.

    Raises OSError where the file cannot be read.

    THE COMMENT IS THE VETO. Every line whose first non-blank character
    is '#' is skipped, and so is every blank one -- which is the whole
    of the format: 'hwut.accept.propose' writes the difference above
    each target as '# TEST RUN:', '# OUT:' and '# => GOOD:' lines, so a
    reader deletes a target or puts a '#' before it, and what is left
    is what he blesses -- 'hwut.accept.apply' being the face that
    does it.

    THE DIRECTORY IS SEPARATED FROM THE NAME. A proposal spans the
    whole tree, so a line reads 'engine/display/TEST/test-run.sh green'
    -- the path is where the case stands, the rest is the case. They
    are split here, once, so that every target is applied in ITS OWN
    directory and a name is never matched against a directory it does
    not live in.
    """
    found = []
    with open(file_name, encoding="utf-8") as fh:
        for line in fh:
            text = line.strip()
            if not text or text.startswith("#"): continue
            head, _, tail = text.partition(" ")
            directory, _, name = head.rpartition("/")
            found.append((directory,
                          name + ((" " + tail.strip()) if tail.strip()
                                  else "")))
    return found


def key_setup_of(key, config_db):
    """RETURN: compare's Configuration for the key's choice, from a
    'config_db' as 'propose' and 'accept_one' build it; None where
    the test carries none."""
    return compare_setup_of(config_db.get(key.test), key.choice)


def compare_setup_of(configuration, choice):
    """
    RETURN: compare's Configuration for this CHOICE -- the tolerances
            it declared; None where the test carries none, or where
            the choice is not among its scenarios.

    ONE SCENARIO, ONE TOLERANCE: the compare setup rides on
    'TestChoiceConfiguration', never on the test, so a choice that
    tolerates a numeric drift does not lend that to its siblings.
    """
    if configuration is None: return None
    try:
        return configuration.choice_configuration(choice).compare
    except (KeyError, AttributeError):
        return None


#  THE ASSOCIATION IS AN A* OVER EDIT SEQUENCES and its cost grows with
#  the SQUARE of the differing text: 100 lines align in half a second,
#  400 in ten, a thousand in minutes. It is the right tool for showing
#  a handful of lines and the wrong one for a wholly rewritten file --
#  and a proposal that never returns is worse than no proposal. So it
#  is reached only where it is CHEAP, and it is bounded even then.
#  THE TRACE. 'VUT_PROPOSE_TRACE=1' makes the reading say, on stderr,
#  what each subject cost. It goes to STDERR because stdout is the
#  proposal itself and must stay a file one can hand back.
def _trace(text):
    """RETURN: None. One trace line on stderr, where the trace is on."""
    if os.environ.get("VUT_PROPOSE_TRACE"):
        sys.stderr.write("[propose] %s\n" % text)
        sys.stderr.flush()


def ignored_line_set(line_list):
    """
    RETURN: set[int], the numbers (from 1) of the lines of 'line_list'
            that stand INSIDE a '##! ignore' region -- between its
            opening line and its closing '####', both excluded;
            empty where the text holds no such region.
    """
    found  = set()
    inside = False
    for number, line in enumerate(line_list, 1):
        stripped = line.strip()
        if inside:
            if stripped == "####": inside = False
            else:                  found.add(number)
        elif stripped.startswith("##!") \
             and stripped[3:].split()[:1] == ["ignore"]:
            inside = True
    return found


def difference_pair_list(compare_config, out_path, good_path, line_n):
    """
    RETURN: [0] list of (position, out text, good text) -- ONE PER
                POSITION where the two files disagree, in order.
                'position' is the line number, counted from 1 and the
                same on both sides since the walk is positional. Either
                text is None where that file has no line there. Empty
                where the two agree throughout.
            [1] None where the whole difference was seen; a reason
                where it was not -- more than 'line_n' positions, or a
                file that will not read.

    LINE BY LINE, AND THAT IS ALL. Line i of the candidate faces line i
    of the nominal; where they differ, the candidate's line is recorded
    as the REPLACEMENT of the nominal's, which is exactly what
    accepting will do. Past 'line_n' replacements the answer is already
    'more than n' and the walk stops.

    THE ENGINE JUDGES EACH POSITION, so a tolerance holds here as it
    holds in the run: a line differing only in trailing space, or by a
    number inside its ratio, is NOT a difference. It is asked only
    where the BYTES already disagree -- an identical line cannot differ
    under any tolerance, and skipping those is what makes the walk cost
    nothing.

    NO ALIGNMENT IS ATTEMPTED, and none is wanted. Pairing two streams
    properly is an A* over edit sequences whose cost grows with the
    square of the text; it was tried here and did not return on a
    rewritten file. A proposal does not need it: a shifted file simply
    shows many replacements, exceeds the bound, and is named in one
    line for 'hwut.report.details' to explain. THE COST IS LINEAR IN THE LINES
    READ, and bounded by 'line_n' besides.
    """
    from ..engine.compare.api import is_equivalent, Configuration, \
                                       RegionSyntaxError
    import io
    options = compare_config if compare_config is not None \
              else Configuration()
    out_line_list  = _lines_of(out_path)  or []
    good_line_list = _lines_of(good_path) or []
    started        = time.time()

    async def walk():
        """RETURN: (pair list, aborted flag), position by position."""
        found = []
        asked = 0
        for index in range(max(len(out_line_list), len(good_line_list))):
            out_text  = out_line_list[index]  \
                        if index < len(out_line_list)  else None
            good_text = good_line_list[index] \
                        if index < len(good_line_list) else None
            if out_text is not None and out_text == good_text:
                continue                      # the bytes agree: no engine
            if out_text is None or good_text is None:
                found.append((index + 1, out_text, index + 1, good_text,
                              None))
            else:
                asked += 1
                if not await is_equivalent(options,
                                           io.StringIO(out_text + "\n"),
                                           io.StringIO(good_text + "\n")):
                    found.append((index + 1, out_text, index + 1,
                                  good_text, None))
            if len(found) > line_n:
                _trace("%s: %d line(s), ABORTED past %d   (%.3fs, %d asked)"
                       % (os.path.basename(str(out_path)),
                          len(out_line_list), line_n,
                          time.time() - started, asked))
                return found, True
        _trace("%s: %d line(s), %d replacement(s)   (%.3fs, %d asked)"
               % (os.path.basename(str(out_path)), len(out_line_list),
                  len(found), time.time() - started, asked))
        return found, False

    async def aligned():
        """RETURN: (entry list, done flag) -- the difference as an
                   ALIGNMENT capped at the bound (D-42b), done False
                   where the bytes differ in more than the cap allows."""
        hunk_list = capped_hunk_list(out_line_list, good_line_list,
                                     2 * line_n + 2)
        if hunk_list is None: return [], False
        found = []
        for block, (out_begin, out_end, good_begin, good_end) \
                in enumerate(hunk_list):
            out_part  = out_line_list[out_begin:out_end]
            good_part = good_line_list[good_begin:good_end]
            for k in range(max(len(out_part), len(good_part))):
                out_text  = out_part[k]  if k < len(out_part)  else None
                good_text = good_part[k] if k < len(good_part) else None
                if out_text is not None and good_text is not None \
                   and await is_equivalent(options,
                                           io.StringIO(out_text + "\n"),
                                           io.StringIO(good_text + "\n")):
                    continue
                found.append((out_begin + k + 1
                              if out_text is not None else None,
                              out_text,
                              good_begin + k + 1
                              if good_text is not None else None,
                              good_text, block))
            if len(found) > line_n: return found, True
        return found, True

    #  A LINE IS JUDGED ALONE, OUTSIDE ITS REGION (ND5): a line inside
    #  '##! ignore' would differ, though the run ignores it. What both
    #  sides hold inside such a region is no difference to propose.
    out_ignored  = ignored_line_set(out_line_list)
    good_ignored = ignored_line_set(good_line_list)
    def kept(entry_list):
        """RETURN: list, 'entry_list' without the entries that lie inside
                   '##! ignore' on every side that has a line."""
        return [entry for entry in entry_list
                if not ((entry[0] is None or entry[0] in out_ignored)
                        and (entry[2] is None or entry[2] in good_ignored))]

    try:
        #  ALIGNED FIRST (D-42b): one inserted line is one entry, not a
        #  shift of every line after it. Where the bytes differ beyond
        #  the cap -- a file whose every line carries a tolerated clock
        #  -- the positional walk judges each position, as before.
        found, done_f = asyncio.run(aligned())
        if done_f:
            found = kept(found)
            if len(found) > line_n: return [], "> %d lines" % line_n
            return found, None
        found, aborted_f = asyncio.run(walk())
        found = kept(found)
    except RegionSyntaxError as error:
        return [], "the region framing does not read: %s" % error
    except OSError as error:
        return [], str(error)
    if aborted_f: return [], "> %d lines" % line_n
    return found, None


#  THE ONLY REASON THAT MAY BE PROPOSED. A proposal says 'these lines
#  become the nominal' -- an act that makes sense ONLY where the run
#  completed and the judgement went against the recording. Every other
#  verdict names a run that BROKE: a source not found, an application
#  contained by a cap, a stream that never testified, a witness
#  convicted of instability. Their candidates are wreckage, and
#  wreckage is not a pole.
DIVERGENCE_TOKEN_SET = frozenset((
    E_TestRunResult.NOT_EQUIVALENT_WITH_NOMINAL.value,
    E_TestRunResult.NOT_EQUIVALENT_GREW.value,
    E_TestRunResult.NOT_EQUIVALENT_SHRANK.value,
    E_TestRunResult.NOT_EQUIVALENT_DIVERGED.value))


def divergence_f(bookkeeper, test, choice):
    """
    RETURN: True where the book's last word on this case is a
            DIVERGENCE FROM THE NOMINAL -- the run completed and the
            judgement went against the recording.
            False where it is anything else: a verdict that passed, or
            a run that broke before it could be judged, or a case the
            book has never seen.

    THE BOOK IS ASKED FOR THE REASON, not for the difference. Whether
    the two texts differ is measured (the line walk); WHY they differ
    is remembered, and only the run that produced the candidate knows
    whether it produced it whole.
    """
    entry = bookkeeper.result(test, choice)
    if entry is None:            return False
    verdict = entry.get("verdict")
    if verdict is not None and verdict.passed_f: return False   # it passed
    return entry.get("report") in DIVERGENCE_TOKEN_SET


BRIEF_WIDTH = 78
DONE_TEXT   = "[DONE]"
ERROR_TEXT  = "[ERROR]"
VERDICT_W   = max(len(DONE_TEXT), len(ERROR_TEXT))


def _brief_label(directory, key):
    """
    RETURN: (directory, test-app, choice), the case as the proposal
            spelt it, split so a report can GROUP by directory and
            ELIDE a test application repeated under it. 'choice' is ''
            where the test has none.
    """
    name = key.name.replace(" .", " ").rsplit(" ", 1)[0] \
           if key.name.endswith((".stdout", ".stderr")) \
           or " ." in key.name else key.name
    test, _, choice = name.partition(" ")
    return (os.path.relpath(directory, os.getcwd()), test, choice.strip())


def _grouped(entry_list):
    """
    RETURN: list of (directory, list of entries), the entries gathered
            under the directory they stand in, directories in order and
            entries within one in order.
    """
    order, group_db = [], {}
    for entry in entry_list:
        where = entry[0][0]
        if where not in group_db: order.append(where); group_db[where] = []
        group_db[where].append(entry)
    return [(where, group_db[where]) for where in order]


def _elided(entry_group):
    """
    RETURN: list of (test text, choice), where a TEST APPLICATION
            REPEATED under its directory is replaced by whitespace --
            written once, and the eye reads the choices below it as
            belonging to it.
    """
    found, last = [], None
    for (_, test, choice), _verdict, _reason in entry_group:
        found.append((" " * len(test) if test == last else test, choice))
        last = test
    return found


def root_named(where):
    """
    RETURN: str, the directory 'where' (relative to the call directory)
                 named from the tree's root, as 'DIR' and HINTS name it
                 ('game/TEST' where the call stands in it, not '.'; the
                 book's D-28)
            'where' itself, where no 'hwut-root.conf' bounds it
    """
    from ..engine.orchestrator.exploration.tree_explorer \
        import root_conf_directory, RootConfMissing
    try:
        top = root_conf_directory(os.path.abspath(where))
    except RootConfMissing:
        return where
    return os.path.relpath(os.path.abspath(where), top).replace(os.sep, "/")


def write_brief(entry_list, write, ink, verb="Accepted"):
    """
    RETURN: None. A file's whole report, in the two sections a run's
            report wears -- rule, heading, rule, content:

        =====...
        EXECUTION:
        -----...
         engine/display/TEST
            test-plain.py allgreen ................. [DONE]
                          words .................... [DONE]
            test-run.sh   empty .................... [DONE]
        =====...
        REPORT:
        -----...
         services/TEST
            test-sanitize.sh  lock        missing terminating <hwut-end>
            :                 unreachable missing terminating <hwut-end>
        =====...
        Accepted 1/2

    'entry_list' is ((directory, test, choice), verdict, reason);
    'reason' is None where the target succeeded. 'verb' heads the
    closing count -- 'Accepted' here, 'Forgotten' for
    'hwut.remove.apply', which wears the same report.

    GROUPED AS A RUN GROUPS: the directory once, its cases under it,
    and a test application written once however many of its choices
    stand below. REPORT: appears only where something failed, and
    wears the shape of a run's HINTS.

    ONLY THE VERDICT IS PAINTED -- not the name, not the dots. A green
    field the width of the line would say 'this line is good' where
    what is good is the OUTCOME, and the eye would have nowhere to
    rest.
    """
    rule_hard = "=" * BRIEF_WIDTH
    rule_soft = "-" * BRIEF_WIDTH
    write(rule_hard)
    write("EXECUTION:")
    write(rule_soft)
    for where, group in _grouped(entry_list):
        write(" %s" % root_named(where))
        pair_list = _elided(group)
        test_w = max(len(test) for test, _ in pair_list)
        for (test, choice), (_key, verdict, _reason) in zip(pair_list, group):
            #  A TEST WITHOUT CHOICES LEAVES NO GAP: the choice column
            #  is only held open where some choice stands in it.
            head = ("    %-*s %s" % (test_w, test, choice)).rstrip() \
                   if not choice else "    %-*s %s" % (test_w, test, choice)
            #  THE DOTS CARRY THE EYE to the one column the verdicts
            #  end in, with ONE SPACE at either border.
            #  THE VERDICTS END IN ONE COLUMN and the dots run up to
            #  each: a shorter verdict gets one more dot, never a
            #  space, and ONLY THE VERDICT IS PAINTED.
            room  = BRIEF_WIDTH - len(head) - len(verdict) - 2
            paint = ink.tag_fail if verdict is ERROR_TEXT else ink.tag_ok
            write("%s %s %s" % (head, "." * max(room, 3), paint(verdict)))

    failed_list = [entry for entry in entry_list if entry[2] is not None]
    if failed_list:
        write(rule_hard)
        write("REPORT:")
        write(rule_soft)
        for where, group in _grouped(failed_list):
            write(" %s" % root_named(where))
            pair_list = _elided(group)
            test_w   = max(len(test) for test, _ in pair_list)
            choice_w = max(len(choice) for _, choice in pair_list)
            for (test, choice), (_key, _verdict, reason) in zip(pair_list,
                                                                group):
                head = ("    %-*s %-*s" % (test_w, test, choice_w, choice))
                write("%s %s" % (head.rstrip() if not choice_w else head,
                                 reason))
    write(rule_hard)
    write("%s %d/%d" % (verb, len(entry_list) - len(failed_list),
                        len(entry_list)))


def capped_hunk_list(out_list, good_list, d_max):
    """
    RETURN: list of (out begin, out end, good begin, good end), the
            stretches where the two line lists differ, in order and
            0-based, end exclusive -- a shortest edit script's hunks --
            if the lists differ by at most 'd_max' inserted or deleted
            lines;
            None, else.

    MYERS' DIFFERENCE, CAPPED AT THE BOUND (D-42b): O((N+M)*D) time and
    O(D*D) memory, with D at most 'd_max', so for a fixed bound it is
    linear in the file. It stops where the answer is already 'more
    than the bound' -- the rule the positional walk always followed.
    Lines are equal by their BYTES; the engine judges each pair inside
    a hunk afterwards.
    """
    n, m = len(out_list), len(good_list)
    #  The common head and tail cost nothing and shrink the search.
    head = 0
    while head < n and head < m and out_list[head] == good_list[head]:
        head += 1
    tail = 0
    while tail < n - head and tail < m - head \
          and out_list[n - 1 - tail] == good_list[m - 1 - tail]:
        tail += 1
    a = out_list[head:n - tail]
    b = good_list[head:m - tail]
    n_a, n_b = len(a), len(b)
    if n_a == 0 and n_b == 0: return []
    offset = d_max + 1
    v = [0] * (2 * d_max + 3)
    trace_list = []
    end_d = None
    for d in range(d_max + 1):
        trace_list.append(list(v))
        for k in range(-d, d + 1, 2):
            if k == -d or (k != d and v[offset + k - 1] < v[offset + k + 1]):
                x = v[offset + k + 1]                       # down: insert
            else:
                x = v[offset + k - 1] + 1                   # right: delete
            y = x - k
            while x < n_a and y < n_b and a[x] == b[y]:
                x += 1; y += 1
            v[offset + k] = x
            if x >= n_a and y >= n_b:
                end_d = d
                break
        if end_d is not None: break
    if end_d is None: return None
    #  BACKTRACK: the edit path, as (x, y) points from the end.
    x, y = n_a, n_b
    edit_list = []                       # (kind, x, y): 'del' a[x], 'ins' b[y]
    for d in range(end_d, 0, -1):
        v_d = trace_list[d]
        k = x - y
        if k == -d or (k != d and v_d[offset + k - 1] < v_d[offset + k + 1]):
            k_prev = k + 1
        else:
            k_prev = k - 1
        x_prev = v_d[offset + k_prev]
        y_prev = x_prev - k_prev
        while x > x_prev and y > y_prev:
            x -= 1; y -= 1
        if x == x_prev: edit_list.append(("ins", x, y - 1))
        else:           edit_list.append(("del", x - 1, y))
        x, y = x_prev, y_prev
    edit_list.reverse()
    #  HUNKS: neighbouring edits together, as stretches of both sides.
    hunk_list = []
    for kind, ex, ey in edit_list:
        if kind == "del": span = (ex, ex + 1, ey, ey)
        else:             span = (ex, ex, ey, ey + 1)
        if hunk_list and span[0] <= hunk_list[-1][1] \
           and span[2] <= hunk_list[-1][3]:
            last = hunk_list[-1]
            hunk_list[-1] = (last[0], max(last[1], span[1]),
                             last[2], max(last[3], span[3]))
        else:
            hunk_list.append(span)
    return [(h[0] + head, h[1] + head, h[2] + head, h[3] + head)
            for h in hunk_list]


def replacement_block_list(pair_list):
    """
    RETURN: list of blocks, each a list of entries (out number, out,
            good number, good, block) taken from 'pair_list' -- ONE
            BLOCK PER HUNK of the alignment, or, where the walk was
            positional (block None), ADJACENT POSITIONS TOGETHER. A run
            of neighbouring differences is one replacement of several
            lines by several, and reads as one.
    """
    block_list = []
    for entry in pair_list:
        if block_list:
            last = block_list[-1][-1]
            if entry[4] is not None and entry[4] == last[4]:
                block_list[-1].append(entry); continue
            if entry[4] is None and last[4] is None \
               and entry[0] == last[0] + 1:
                block_list[-1].append(entry); continue
        block_list.append([entry])
    return block_list


def write_replacement_block(block, put, width):
    """
    RETURN: None. One block, the OUT lines then the GOOD lines they
            replace, each carrying ITS OWN LINE NUMBER:

                # -- [4711] OUT:  "..."
                #    [4712] OUT:  "..."
                # => [4721] GOOD: "..."
                #    [4722] GOOD: "..."

            '--' opens what the run produced, '=>' what it replaces,
            and a bare indent continues either. 'width' is the column
            the numbers are padded to -- ONE PER CASE, not per block,
            so every block of a test lines up with every other and the
            quotes start at one column throughout.
    """
    out_list  = [(entry[0], entry[1]) for entry in block
                 if entry[1] is not None]
    good_list = [(entry[2], entry[3]) for entry in block
                 if entry[3] is not None]

    def line(mark, number, kind, text):
        """RETURN: str, one rendered line of the block."""
        return '# %s [%*d] %-5s "%s"' % (mark, width, number, kind, text)

    for index, (number, text) in enumerate(out_list):
        put(line("--" if index == 0 else "  ", number, "OUT:", text))
    for index, (number, text) in enumerate(good_list):
        put(line("=>" if index == 0 else "  ", number, "GOOD:", text))


def propose(store, case_sequence, directory, line_n, write,
            result=None, language_setup=None, put=None):
    """
    RETURN: E_ExitCode.OK where something was proposed, EMPTY where
            nothing was -- proposing blesses nothing and runs nothing.

    Writes, for every selected case whose candidate DIFFERS from its
    nominal, the DIFFERING LINES as comments and then the target on
    its own line:

        # PROPOSE(<dir>/<test-app> <choice>):
        # OUT:     "<what the run produced>"
        # => GOOD: "<what stands as the nominal today>"
        <dir>/<test-app> <choice>

    A case over the bound gets ONE line and no target, and a run of
    them stands unbroken as the list it is:

        # DIFF(<dir>/<test-app> <choice>) > <n> lines

    WHAT A PAIR SAYS: ACCEPT THIS AND THE 'OUT' LINE BECOMES THE
    NOMINAL, in place of the quoted line below it. The '=> GOOD' line
    is the OLD value -- what is about to be replaced -- and nothing else in the
    nominal moves. A reader who agrees with every arrow leaves the
    target standing; a reader who disagrees with one deletes the
    target or puts a '#' before it.

    TWO CASES ARE PASSED OVER IN SILENCE.

      NO CANDIDATE -- nothing was run, so there is NOTHING TO JUDGE.
      A proposal over an absent subject would be a proposal to bless
      a file that does not exist.

      NO NOMINAL -- a FIRST blessing is a deliberate act, focussed on
      the one subject it declares the pole for (E-41: the pole is
      declared, never fallen into). It is never one line among fifty
      in a file somebody skimmed.

    THE VERDICT IS THE COMPARE ENGINE'S ('equivalent_f'): a case whose
    candidate the run holds EQUIVALENT to its nominal is never
    proposed, however many bytes differ. The difference SHOWN is
    line-wise, because a reader reads lines.

    ONLY THE DIFFERING LINES ARE PRINTED, and never more than
    'line_n' of either side: 'hwut.accept.propose 5' shows at most five OUT
    lines and five GOOD lines. A case with more differing lines than
    that on either side is named as a COMMENT alone, never as a
    target -- a difference nobody read is not one to bless in bulk.
    """
    #  TWO SINKS, TWO AUDIENCES. 'put' takes the FILE -- what can be
    #  blessed, and nothing else, so the file is handed back without
    #  editing out anything but the targets refused. 'write' takes
    #  STDOUT -- what cannot: the cases a reader must open himself.
    #  A proposal one has to strip before use is not a proposal.
    said_n, unproposed_n = 0, 0
    where = os.path.relpath(directory, os.getcwd())
    #  ONE CONFIGURATION PER TEST, built as the run builds it, so the
    #  tolerances a proposal honours are the ones the run honoured.
    #  THE COMPARE SETUP IS THE CHOICE'S, not the test's: one scenario,
    #  one tolerance ('TestChoiceConfiguration').
    config_db = {}
    if result is not None:
        for name, app in result.app_set.app_db.items():
            try:
                config_db[name] = test_configuration_of(
                                      app, directory,
                                      language_setup=language_setup)
            except Exception:
                config_db[name] = None
    for case in case_sequence:
        choice = case.choice
        for subject in subject_tuple_of(store, case.source_file, choice):
            out_path  = store.bookkeeper.candidate_path(case.source_file,
                                                        choice, subject)
            good_path = store.bookkeeper.nominal_path(case.source_file,
                                                      choice, subject)
            out  = _lines_of(out_path)          # stands at all?
            good = _lines_of(good_path)
            if out is None:  continue          # nothing ran: nothing to judge
            if good is None: continue          # no pole: a first blessing
            #  AND THE REASON MUST BE A DIVERGENCE. A candidate left by
            #  a run that broke is wreckage, whatever it happens to
            #  contain.
            if not divergence_f(store.bookkeeper, case.source_file,
                                choice):
                continue
            #  THE COMPARE ENGINE DECIDES what differs and which line
            #  faces which -- not a byte comparison. A difference the
            #  run tolerates is not a difference to propose.
            setup = compare_setup_of(config_db.get(case.source_file),
                                     choice)
            pair_list, refusal = difference_pair_list(setup, out_path,
                                                      good_path, line_n)
            if refusal is None and not pair_list: continue
            #  THE TARGET CARRIES ITS DIRECTORY, so ONE proposal file
            #  spans the whole tree and the script resolves each line
            #  where it belongs. A path-bearing glob is the wish's own
            #  form (E-15), relative to the run's root.
            label = "%s%s" % (os.path.join(where, case.source_file),
                              "" if choice is None else " " + choice)
            #  TOO BIG, OR UNREADABLE: ONE LINE AND NO TARGET. The
            #  reader is told which case and that it exceeds the
            #  bound; 'hwut.report.details' is the tool for the rest and needs
            #  no repeating here.
            #  TOO BIG, OR UNREADABLE: ONE LINE AND NO TARGET, and no
            #  blank after it -- a run of them is a LIST, and a list
            #  reads better unbroken. 'hwut.report.details' shows one whole.
            if refusal is not None:
                write("DIFF(%s) %s" % (label, refusal))
                unproposed_n += 1
                continue
            if len(pair_list) > line_n:
                write("DIFF(%s) > %d lines" % (label, line_n))
                unproposed_n += 1
                continue
            #  A PROPOSAL IS SPOKEN, not merely labelled: the head says
            #  what the block below proposes, and for which case.
            put("# TEST RUN: %s" % label)
            #  ADJACENT DIFFERENCES ARE ONE BLOCK: several lines
            #  replaced by several reads as one replacement, not as a
            #  column of pairs. WHAT A BLOCK SAYS: these OUT lines
            #  BECOME the nominal, in place of the GOOD lines under
            #  them. Accepting the target below performs exactly these
            #  replacements and nothing else.
            width = max([len(str(number)) for entry in pair_list
                         for number in (entry[0], entry[2])
                         if number is not None] or [1])
            for block in replacement_block_list(pair_list):
                write_replacement_block(block, put, width)
            put(label)
            put("")
            said_n += 1
    #  A CASE THAT DIFFERS AND COULD NOT BE PROPOSED IS NO AGREEMENT
    #  (D-42): the file must not close with 'every selected case agrees',
    #  and the exit status says that something was left to the reader.
    if unproposed_n:
        if not said_n:
            put("#  nothing proposed: %d case(s) differ beyond what a "
                "proposal shows --" % unproposed_n)
            put("#  named on stdout as 'DIFF(...)'; open them with "
                "'hwut.report.details'")
        return E_ExitCode.FAULT
    return E_ExitCode.OK if said_n else E_ExitCode.EMPTY


def _lines_of(path):
    """
    RETURN: list of str, the file's lines without their endings.
            None where the file does not stand or cannot be read.
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    except OSError:
        return None


def stderr_spoke_db(store, case_sequence):
    """
    RETURN: dict, (test, choice) -> the recorded stderr's size, for
            every selected case whose run left a NON-EMPTY stderr
            candidate behind.

    STDERR IS NEVER SUBJECT TO TESTING; the one thing acceptance
    decides about it is the NOTE, and only where it spoke.
    """
    spoke_db = {}
    for case in case_sequence:
        test   = case.source_file
        choice = case.choice
        #  THE ERROR WITNESS 'OUT/<key>.err': written only where
        #  stderr spoke, so its size says it all.
        path   = store.bookkeeper.error_witness_path(test, choice)
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        if size > 0: spoke_db[(test, choice)] = size
    return spoke_db


def stderr_decision(spoke_db, ignored_f_of):
    """
    RETURN: list, the (test, choice, size) triples REFUSED -- stderr
            spoke and the test does not declare it ignored. Empty where
            nothing stands in the way.

    'ignored_f_of(test, choice)' answers the test's OWN declaration,
    'tolerance { stderr_ignored = true }' (E-110, E-136). NOTHING HERE
    DECIDES: no switch of this face tolerates on a wish's say-so, and
    nothing is written. A choice whose stderr spoke undeclared is
    refused BY NAME, with both remedies.
    """
    return [(test, choice, size)
            for (test, choice), size in sorted(
                spoke_db.items(),
                key=lambda item: (item[0][0], item[0][1] or ""))
            if not ignored_f_of(test, choice)]


#  'token_terminated_f' and 'classify' live in '_accept_common.py' now:
#  they are what BOTH kinds of acceptance rely on, and a refusal rule
#  must not be able to apply to one kind and not the other.
from ._accept_common import (token_terminated_f, classify,  # noqa: E402
                                         STDERR_IGNORED_LINE)


def main(argv=None, write=None, read_line=None, propose_n=None,
         put=None, script_name=None, brief_f=False):
    """
    'put'        where a proposal's TARGETS go -- the file the reader
                 hands back. 'write' keeps what he must open himself.
    'brief_list'  not None: a list to APPEND (label, verdict, reason)
                 to instead of writing a report. 'hwut.accept.apply'
                 passes one, so that a file of fifty targets reads as
                 a column of verdicts and not as fifty paragraphs.
    'brief_f'    True: report a COLUMN of verdicts, one line per
                 target, and one sentence per failure -- what
                 'hwut.accept.apply' wants for a file of fifty.
    'script_name'  a file whose non-comment lines are the targets to
                 bless. NOT A COMMAND-LINE OPTION: applying a file of
                 blessings is a different act from blessing what a
                 wish selects, and it wears a different name --
                 'hwut.accept.apply' is the only caller that passes
                 this.
    'propose_n'  not None: BLESS NOTHING. Read what stands and write
                 the differing cases as a file to hand back, at most
                 that many lines a side. NOT A COMMAND-LINE OPTION:
                 proposing and blessing are different acts and wear
                 different names -- 'hwut.accept.propose' is the face,
                 and it is the only caller that passes this.

    RETURN: E_ExitCode, the exit status (E-1): OK where everything the
            wish selected was accepted or needed nothing, FAULT where
            a fault was met or a key needed a merge and was left
            alone, REFUSED where the command line cannot be read,
            EMPTY where it reads and asks for nothing.

    'write' takes one line at a time, 'print' where none is given.
    'read_line' answers the per-key question; where none is given the
    face reads stdin, so a suite drives it without a process.
    """
    if argv is None: argv = sys.argv[1:]
    if write is None: write = print
    if read_line is None: read_line = sys.stdin.readline

    #  ACCEPT NEVER MERGES AND NEVER ASKS (E-167, superseding E-59's
    #  terminal merge and E-57's prompt): 'hwut.merge' alone merges.
    if "--help" in argv:
        from ._core import man_page
        write(man_page("hwut.accept", HELP, usage=USAGE))
        return E_ExitCode.OK

    try:
        wish, rest_list = parse_wish(argv, digest_f=True)
    except WishError as error:
        write_refusal(write, "REFUSED: %s" % error, USAGE)
        return E_ExitCode.REFUSED

    if "--yes" in rest_list:
        #  E-68: the word names an ANSWER, and on the command line there
        #  is no question yet for it to answer.
        write("REFUSED: '--yes' is gone (E-68) -- '--dont-ask' is "
              "the one word for 'do not ask'")
        return E_ExitCode.REFUSED
    arguments, completion_f = parse_or_refuse(PARSER, rest_list, write,
                                              ARG_DB)
    if completion_f:      return E_ExitCode.OK
    if arguments is None:
        write(USAGE)
        return E_ExitCode.REFUSED
    directory_said_f = arguments.directory is not None
    directory    = arguments.directory or "."
    force_f      = arguments.force
    word_list    = arguments.word
    if arguments.dont_ask:
        #  E-167: there is no question left to skip. Refused BY NAME so
        #  a script that still says it is told.
        write("REFUSED: '--dont-ask' is gone (E-167) -- accept never "
              "asks; it blesses what the words select")
        return E_ExitCode.REFUSED
    if arguments.force_run:
        #  E-165: accept runs nothing. Refused BY NAME so a script that
        #  still says it is told, not silently given the recording.
        write("REFUSED: '--force-run' is gone (E-165) -- accept blesses "
              "the recording; 'hwut.play' records afresh")
        return E_ExitCode.REFUSED
    #  A TEST NAMED BY PATH IS ENTERED ('services/_target.py', E-47).
    found = entered(word_list, directory, write, USAGE)
    if found is None: return E_ExitCode.REFUSED
    directory, word_list = found
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist" % directory)
        write(USAGE)
        return E_ExitCode.REFUSED

    #  The short form is SUGAR ('wish.desugar_positional'), and the
    #  wish's own engine does the selecting. ONE SELECTION LANGUAGE:
    #  the sugar lives with the wish, so every face spells it alike.

    #  THE CLIMB APPLIES HERE TOO: a single-directory face standing
    #  in a test directory owes the same effective configuration as a
    #  walk that reached it from the project root.
    try:
        inherited, _ = ascended_spec(directory)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    #  THE CLIMB'S FAULTS ARE SAID ONCE, with the selection's ('FAULT:'
    #  below): the door reads them itself (ND7).

    entry_list = []
    if script_name is not None:
        try:
            entry_list = proposal_targets(script_name)
        except OSError as error:
            write("REFUSED: %s" % error)
            return E_ExitCode.REFUSED
        if not entry_list:
            write("NOTE: '%s' names no target -- every line is a "
                  "comment or blank" % script_name)
            return E_ExitCode.OK
        #  THE DIRECTORY AND THE NAME, REJOINED AS A GLOB. The path
        #  member is the glob's own form (E-15), so one file spans the
        #  whole tree and every target is matched in ITS directory.
        wish = replace(wish, glob_tuple=wish.glob_tuple
                             + tuple(os.path.join(where, target)
                                     if where else target
                                     for where, target in entry_list))
    wish = with_targets(wish, word_list)
    #  ONE COORDINATE SYSTEM: the Bookkeeper, the Store and the
    #  configuration of a case this face RUNS (E-40) must name the
    #  same directory, and the process's cwd is none of theirs.
    directory = os.path.abspath(directory)
    try:
        label_view = view_at(directory)
    except LabelFileError as error:
        write("FAULT: %s" % error)
        return E_ExitCode.FAULT

    #  ONE ACTION, ONE PLACE ('exploration/selection.py'). 'base_f=True'
    #  because this face reads candidates whatever the wish asked, and
    #  a bare wish asks no base. A FACE THAT NAMES A RUN AND BLESSES
    #  NOTHING MUST SAY WHY: the warnings speak (disc-8).
    #  ONE FACE, BOTH DOORS ('exploration/selection.py'). A BARE
    #  'hwut.accept' WALKS THE TREE, as 'hwut.run' does: the failures a
    #  run reports do not sit in one directory, and a face that blesses
    #  them should not ask the reader to visit seven. '--directory=<p>'
    #  names ONE directory and takes the other door, which is what a
    #  single-directory face has always done (E-15's cost note).
    tree_f = directory_said_f
    try:
        if tree_f:
            found = selection.of_directory(directory, wish, label_view,
                                           inherited=inherited,
                                           base_f=True)
        else:
            found = selection.of_tree(directory, wish, label_view,
                                      base_f=True)
        for fault in found.fault_tuple:
            write("FAULT: %s" % fault)
        for text in found.warning_tuple:
            write(text)
    except SelectionError as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    #  NOTHING IS BLESSED UNDER A CONFIGURATION THAT CANNOT BE READ (ND7,
    #  services E-190): its directories select nothing, and say so --
    #  the FAULT above names the file and the key.
    conf_refused_list = sorted(where for where, result
                               in (found.result_db or {}).items()
                               if result.conf_fault_tuple)
    for where in conf_refused_list:
        write("REFUSED: '%s' -- its configuration does not read (the "
              "FAULT above); nothing is accepted under it"
              % os.path.normpath(os.path.relpath(
                    os.path.join(directory, where), os.getcwd())))

    #  THE CASES, GROUPED BY THE DIRECTORY THEY WERE FOUND IN -- walk
    #  order, which is the order a reader met them in the run's report.
    where_list, case_db = [], {}
    for entry in found.case_list:
        where = entry.directory
        if where not in case_db: where_list.append(where); case_db[where] = []
        case_db[where].append(entry.case)

    #  WHAT WAS PLAYED IS WHAT IS BLESSED (E-168). On the command line a
    #  digest names ONE recording, so the words must select one case; a
    #  wishlist gives each literal line its own.
    digest_db = {}
    for target, tag in wish.digest_tuple:
        path, _, choice = target.partition(" ")
        digest_db.setdefault((os.path.abspath(path), choice.strip() or None),
                             set()).add(tag)
    if arguments.digest:
        selected_n = sum(len(case_list) for case_list in case_db.values())
        if selected_n != 1:
            write("REFUSED: '--digest' blesses one recording; the words "
                  "select %d case(s) -- name one case, or give each its "
                  "digest in a wishlist" % selected_n)
            return E_ExitCode.REFUSED
        where = where_list[0]
        case  = case_db[where][0]
        digest_db.setdefault(
            (os.path.abspath(os.path.join(directory, where,
                                          case.source_file)),
             case.choice or None), set()).update(arguments.digest)

    if propose_n is not None:
        put("#  proposal -- delete or '#' out what you do not want, "
            "then hand it back:")
        #  THE HAND-BACK ASKS NOTHING: 'hwut.accept.apply' implies
        #  both '--force' and '--yes', because editing this file WAS
        #  the answer to both. Said here, where the reader is.
        put("#      hwut.accept.apply <this file>")
        put("")
    brief_list = [] if brief_f else None
    worst   = E_ExitCode.OK
    empty_f = True
    for where in where_list:
        result     = found.result_db.get(where)
        bookkeeper = found.bookkeeper_db.get(where)
        if result is None or bookkeeper is None: continue
        whole = os.path.normpath(os.path.join(directory, where))
        if len(where_list) > 1 and propose_n is None and not brief_f:
            write("")
            write("== %s" % os.path.relpath(whole, os.getcwd()))
        code = accept_one(whole, result, bookkeeper, case_db[where],
                          force_f,
                          propose_n, write, read_line, put=put,
                          brief_list=brief_list,
                          digest_db=digest_db)
        if code is not E_ExitCode.EMPTY: empty_f = False
        if code not in (E_ExitCode.OK, E_ExitCode.EMPTY): worst = code
    if brief_list is not None:
        #  A TARGET THAT MATCHED NOTHING IS A FAILURE OF THE FILE, not
        #  a silence: the reader left the line standing and is owed an
        #  answer about it. Exploration never met it -- a name
        #  misspelt, a test since removed, a directory not under this
        #  root.
        seen_set = {key for key, _, _ in brief_list}
        for where, target in (entry_list if script_name else []):
            test, _, choice = target.partition(" ")
            key = (where or ".", test, choice.strip())
            if key not in seen_set:
                brief_list.append((key, ERROR_TEXT,
                                   "no such test, or not selected here"))
                worst = E_ExitCode.FAULT
        brief_list.sort()
        #  COLOUR AS EVERY OTHER FACE DECIDES IT: the environment and
        #  the terminal, through the one gate ('display/console.py').
        write_brief(brief_list, write,
                    CInk(colour_decision(os.environ, sys.stdout.isatty()),
                         color_of=preferences.load().color))
        return worst
    if conf_refused_list and worst in (E_ExitCode.OK, E_ExitCode.EMPTY):
        return E_ExitCode.FAULT
    if empty_f and worst is E_ExitCode.OK:
        (put if propose_n is not None else write)(
            "#  nothing to propose: every selected case agrees with "
            "its nominal" if propose_n is not None
            else "NOTE: nothing to accept -- the selection holds no "
                 "recorded candidate")
        return E_ExitCode.EMPTY
    return worst


def accept_one(directory, result, bookkeeper, case_sequence,
               force_f, propose_n,
               write, read_line, put=None, brief_list=None,
               digest_db=None):
    """
    RETURN: E_ExitCode for ONE test directory -- OK where every key it
            holds was blessed or nothing was owed, EMPTY where it held
            no recorded candidate, FAULT where a key was refused.

    THE WHOLE OF ACCEPT'S WORK, for one directory: propose or bless --
    the RECORDING, which this face never makes (E-165). 'main' selects -- over the tree or over one directory, as
    the wish says -- and calls this once per directory it met, so the
    two doors of 'exploration/selection.py' differ for accept only in
    HOW MANY TIMES this runs.
    """
    store = Store(bookkeeper)

    #  ACCEPT RUNS NOTHING (services E-165, ruled 2026-10-22): "the
    #  user accepts on recorded fixed output, not on content that might
    #  be produced in the background". The recording is 'hwut.play''s or
    #  'hwut.run''s; this face blesses it as it stands, says which face
    #  made it and when, and hints where the test's source changed since.
    #  It used to run ON NECESSITY (2026-09-05, E-40): a recording older
    #  than the source was run again -- and data, fixtures, the unit
    #  under test in another file were never seen (the book's D-34).
    language_setup = result.app_set.directory_spec.language_setup
    if propose_n is not None:
        return propose(store, case_sequence, directory, propose_n, write,
                       result, language_setup, put=put)

    #  STDERR FIRST: where it spoke and nothing tolerates it, the
    #  whole choice is refused before any pole is touched.
    def ignored_f_of(test, choice):
        """RETURN: bool, the test's own 'stderr_ignored' for the case."""
        app = result.app_set.app_db.get(test)
        parameters = None if app is None else app.choice_db.get(choice)
        tolerance  = getattr(parameters, "tolerance", None)
        return bool(tolerance is not None and tolerance.stderr_ignored)

    refused_list = stderr_decision(stderr_spoke_db(store, case_sequence),
                                   ignored_f_of)
    if refused_list:
        write("REFUSED: stderr SPOKE and nothing tolerates it --")
        for test, choice, size in refused_list:
            write("    %s%s   (%d bytes)"
                  % (test, "" if choice is None else " " + choice,
                     size))
        write("stderr is for ERROR REPORTING and is never subject to")
        write("testing. Either declare it in the test's own block,")
        write("'%s', or -- where the" % STDERR_IGNORED_LINE)
        write("reporting is itself under test -- flush it to a FILE and")
        write("name that file in 'output'.")
        return E_ExitCode.FAULT

    #  A STAINED CHOICE IS NEVER PROMOTED, and never silently: the
    #  refusal is spoken, by name, with the way out.
    stained_list = [(case.source_file, case.choice)
                    for case in case_sequence
                    if unstable_f(store.bookkeeper.stain(
                           case.source_file, case.choice))]
    for test, choice in stained_list:
        choice_str = "" if choice is None else " " + choice
        write("REFUSED stained: '%s%s' bears a STAIN -- unstable under "
              "hwut.run.stability repetitions" % (test, choice_str))
    if stained_list:
        write("    Apply 'hwut.run.stability --repeat=<n>' to proof stability, or")
        write("    'hwut.remove' it and 'hwut.accept' afresh.")

    #  A REFUSAL IS A FAULT OF THE CALL (D-44): what was asked for was
    #  not done, and a script must see it in the exit status. A key the
    #  person declined at the prompt is no refusal -- that was an answer.
    refused_f = bool(stained_list)

    #  NO RECORDING, NOTHING TO BLESS (E-165): a case that 'hwut.play'
    #  or 'hwut.run' never recorded is refused by name, with the remedy.
    from ._accept_common import NO_RECORDING_TEXT
    stained_set = set(stained_list)
    for case in case_sequence:
        if (case.source_file, case.choice) in stained_set: continue
        if any(subject != STDERR_SUBJECT for subject
               in subject_tuple_of(store, case.source_file, case.choice)):
            continue
        name = case.source_file if case.choice is None \
               else "%s %s" % (case.source_file, case.choice)
        if brief_list is not None:
            brief_list.append(((os.path.relpath(directory, os.getcwd()),
                                case.source_file, case.choice or ""),
                               ERROR_TEXT, NO_RECORDING_TEXT))
        else:
            write("REFUSED: '%s' -- %s" % (name, NO_RECORDING_TEXT))
        refused_f = True

    key_list = key_list_of(store, case_sequence)
    if not key_list:
        if refused_f: return E_ExitCode.FAULT    # the refusal said why
        write("NOTE: nothing to accept -- selection empty")
        return E_ExitCode.EMPTY

    #  A shared nominal whose choices DISAGREE cannot be blessed: the
    #  author's premise is broken, and picking a winner would hide it.
    conflict_db = shared_conflict_db(key_list)
    conflict_set = set()
    for path_text, group in sorted(conflict_db.items()):
        if brief_list is None:
            write("REFUSED to pick: the choices below share ONE nominal "
                  "('same') and DISAGREE --")
            write("    nominal: %s" % os.path.basename(path_text))
        for key in group:
            if brief_list is None: write("    %s" % key.name)
            conflict_set.add(id(key))
        if brief_list is None:
            write("    that is the test failing, not something to bless")

    #  THE CLOSING TOKEN (R-70): a stdout stream that does not end in
    #  '<hwut-end>' never COMPLETED -- cut short, aborted, or the
    #  application does not speak the law. An incomplete stream is
    #  never promotable, and NO FLAG bypasses this: '--force'
    #  overrides a standing pole, not stream integrity; the abort
    #  ruling already made such content irrelevant.
    tokenless_list = [key for key in key_list
                      if key.subject == "stdout"
                      and not token_terminated_f(
                              read_text(key.candidate_path))]
    if tokenless_list:
        if brief_list is not None:
            for key in tokenless_list:
                brief_list.append((_brief_label(directory, key), ERROR_TEXT,
                                   "missing terminating <hwut-end>"))
            return E_ExitCode.FAULT
        write("REFUSED: the closing token '<hwut-end>' does not "
              "appear --")
        for key in tokenless_list:
            write("    %s" % key.name)
        write("a stream without its terminal token never COMPLETED; "
              "nothing here is")
        write("promotable. Re-run the test. An application the "
              "framework does not run")
        write("prints the token itself, as its last line.")
        return E_ExitCode.FAULT

    #  ONE CONFIGURATION PER TEST, so the reading shown at the asking
    #  is read under the choice's own tolerances (E-57).
    config_db = {}
    for name, app in result.app_set.app_db.items():
        try:
            config_db[name] = test_configuration_of(
                                  app, directory,
                                  language_setup=language_setup)
        except Exception:
            config_db[name] = None

    #  WHAT IS BLESSED IS NAMED (E-165): the recording, which face made
    #  it and when; a HINT where the test's source changed since.
    if brief_list is None:
        from ._accept_common import (recording_text, source_changed_f,
                                     source_changed_hint)
        for key in key_list:
            if id(key) in conflict_set: continue
            freshness = store.freshness(key.test, key.choice, key.subject)
            write("RECORDING: %s -- %s" % (key.name,
                                           recording_text(freshness)))
            if source_changed_f(freshness,
                                os.path.join(directory, key.test)):
                write(source_changed_hint(key.name))

    #  A DIGEST ASKED FOR IS CHECKED PER CASE (E-168): over every
    #  recorded file of the case, as 'hwut.play' named it. A case whose
    #  recording carries another tag is refused whole.
    if digest_db:
        from ._accept_common import digest_tag, digest_refused_text
        case_key_db = {}
        for key in key_list:
            if id(key) in conflict_set: continue
            case_key_db.setdefault((key.test, key.choice), []).append(key)
        for (test, choice), case_key_list in case_key_db.items():
            tag_set = digest_db.get((os.path.abspath(
                                         os.path.join(directory, test)),
                                     choice or None))
            if not tag_set: continue
            standing = digest_tag([key.candidate_path
                                   for key in case_key_list])
            if standing in tag_set: continue
            write(digest_refused_text(
                      test if choice is None else "%s %s" % (test, choice),
                      " or ".join(sorted(tag_set)), standing))
            conflict_set.update(id(key) for key in case_key_list)
            refused_f = True

    blessed_list, merge_list, skipped_list = [], [], []
    undecided_list = []                 # first acceptances: the shape only
    for key in key_list:
        if id(key) in conflict_set:
            skipped_list.append(key)
            continue
        verdict = classify(key, force_f)
        if verdict == "merge":
            #  A nominal stands: this is a CHANGE, and a change is
            #  'hwut.merge's alone (E-167) -- named, left alone, and
            #  '--force' still overwrites.
            merge_list.append(key)
            continue
        text = read_text(key.candidate_path)
        if text is None:
            write("FAULT: the candidate of '%s' cannot be read"
                  % key.name)
            skipped_list.append(key)
            refused_f = True
            continue
        #  A SUBJECT THAT BREAKS ITS CONSTRAINTS IS NEVER ACCEPTED -- no
        #  '--force' reaches past this (E-124). Held against itself: what
        #  it would say, were it the GOOD.
        from .lib.accept.constraint import own_finding_text_list
        from .lib.accept.constraint import region_fault_text
        fault = region_fault_text(key_setup_of(key, config_db), text)
        if fault is not None:
            write("REFUSED region: '%s' -- the candidate's regions cannot "
                  "be read: %s" % (key.name, fault))
            skipped_list.append(key)
            refused_f = True
            continue
        own_list = own_finding_text_list(key_setup_of(key, config_db), text)
        if own_list:
            write("REFUSED constraint: '%s' -- the candidate breaks its "
                  "constraints:" % key.name)
            for own in own_list: write("    %s" % own)
            skipped_list.append(key)
            refused_f = True
            continue
        written = text
        store.accept(key.test, key.choice, key.subject, written)
        #  THE REGISTER: an id is born at first accept -- issued by
        #  'note_accept' in the acceptance's own act (B-9).
        #  THE BOOK: the acceptance's instant (E-36), so the three
        #  records of acceptance agree (E-41). Before this line the
        #  face itself accepted outside the book.
        #  THE STATE IS WHAT WAS WRITTEN, NOT WHAT WAS SHOWN. 'written'
        #  is the nominal that now stands -- the mirror on a first
        #  acceptance -- and its '##! unaccepted' regions are what make
        #  candidate the reader judged and is never filed.
        #  AN INCOMPLETE ACCEPTANCE IS BOOKED AS ONE (B-16). 'written'
        #  is the nominal that now stands; a '##! unaccepted' region in
        #  it makes the case an ASPIRANT, and the row must say so
        #  rather than 'true'. THE BOOKKEEPER'S OWN TEST (B-26): any
        #  other '##!' line opens a region that is not this.
        aspirant_f = carries_unaccepted_text_f(written)
        store.bookkeeper.note_accept(key.test, key.choice,
                                     aspirant_f=aspirant_f)
        blessed_list.append(key)

    uncommitted_list, short_list = [], []

    #  WHAT BECAME OF EACH KEY, as data (E-105): the five lists are one
    #  outcome per key, and the page -- brief column or report block --
    #  is made FROM it. A caller that is not a page (a server, a test,
    #  the screen that resolves a merge) reads the same record.
    outcome_tuple = outcome_tuple_of(directory, blessed_list, undecided_list,
                                     merge_list, uncommitted_list,
                                     skipped_list, short_list)
    if brief_list is not None:
        brief_list.extend(brief_row_of(outcome) for outcome in outcome_tuple)
    else:
        report_written(outcome_tuple, len(key_list), write)

    if result.fault_list or merge_list or uncommitted_list or conflict_db \
       or short_list or refused_f:
        return E_ExitCode.FAULT
    return E_ExitCode.OK


@dataclass(frozen=True)
class Outcome:
    """WHAT BECAME OF ONE KEY (E-105): plain fields, so a caller that is
    not a page can read what accept decided.

    'kind' is one of 'blessed', 'undecided', 'saved-short' (the screen
    saved a GOOD the output still differs from), 'needs-merge',
    'cancelled', 'left-alone'; 'name' is the key as a page names it, 'label' the
    same with its directory where the selection spans more than one."""
    name:   str
    label:  str
    kind:   str


#  THE WORD EACH OUTCOME WEARS, and the brief column's verdict beside it.
_OUTCOME_DB = {
    "blessed":     ("blessed       ", None),
    "undecided":   ("undecided     ", "recorded undecided: the shape stands, "
                                      "nothing is accepted yet"),
    "saved-short": ("saved [FAIL]  ", "GOOD is saved; OUT still differs "
                                      "from it"),
    "needs-merge": ("merge required", "a nominal stands: this is a change, "
                                      "not a first blessing"),
    "cancelled":   ("cancelled     ", "left alone -- the screen was cancelled"),
    "left-alone":  ("left alone    ", "left alone -- refused above, or not "
                                      "confirmed"),
}


def outcome_tuple_of(directory, blessed_list, undecided_list, merge_list,
                     uncommitted_list, skipped_list, short_list=()):
    """RETURN: tuple[Outcome], one per key, in the order a page says
               them."""
    return tuple(
        Outcome(key.name, _brief_label(directory, key), kind)
        for kind, key_list in (("blessed", blessed_list),
                               ("undecided", undecided_list),
                               ("saved-short", short_list),
                               ("needs-merge", merge_list),
                               ("cancelled", uncommitted_list),
                               ("left-alone", skipped_list))
        for key in key_list)


def brief_row_of(outcome):
    """RETURN: (label, verdict, note), one row of the brief column."""
    _, note = _OUTCOME_DB[outcome.kind]
    good_f  = outcome.kind in ("blessed", "undecided")
    return (outcome.label, DONE_TEXT if good_f else ERROR_TEXT,
            note if outcome.kind != "blessed" else None)


def report_written(outcome_tuple, key_n, write):
    """RETURN: None. The report block 'hwut.accept' has always written,
               made from the outcomes."""
    stood_n = sum(1 for o in outcome_tuple
                  if o.kind in ("blessed", "undecided"))
    write("")
    write("=" * 78)
    write("ACCEPTED  %d of %d" % (stood_n, key_n))
    write("-" * 78)
    for kind in ("blessed", "undecided", "saved-short", "needs-merge",
                 "cancelled", "left-alone"):
        for outcome in outcome_tuple:
            if outcome.kind == kind:
                write("    %s %s" % (_OUTCOME_DB[kind][0], outcome.name))
    if any(o.kind == "needs-merge" for o in outcome_tuple):
        write("")
        write("A nominal already stands for the keys above. That is a "
              "CHANGE, not a")
        write("first blessing => hwut.merge; or '--force' to overwrite "
              "the pole.")
    if any(o.kind == "cancelled" for o in outcome_tuple):
        write("")
        write("The screen was left without saving: nothing was written. "
              "'s' saves GOOD")
        write("as it stands and leaves.")
    write("=" * 78)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ._exit import guarded
    sys.exit(guarded("hwut.accept", main, sys.argv[1:]))
