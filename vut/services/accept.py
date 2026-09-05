"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
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
    --yes                       unattended: do not ask
    --force                     overwrite a STANDING nominal, where a
                                merge would otherwise be required
    --directory=<path>          where to read; the current one else
    --help                      this text

WHAT ACCEPT DOES NOT DO: it never overwrites a standing nominal unless
'--force' says so out loud. Where a nominal stands, the candidate is
not a first blessing but a CHANGE, and a change is 'hwut.merge's
business -- accept names the key and leaves the pole alone.

EXIT STATUS (E-1, services/_exit.py):
    0  everything the wish selected was accepted, or needed nothing
    1  a fault was met, or a key needed a merge and was left alone
    2  the command line cannot be read
    3  the command line reads, and asks for nothing
______________________________________________________________________________
"""
import asyncio
import os
import sys

from   vut.engine.orchestrator.exploration.tree_explorer \
                                                       import (RootConfMissing,
                                                               ascended_spec)
from   vut.engine.bookkeeper.api                import TestIdDb
from   vut.engine.bookkeeper.api             import E_StderrNote
from   vut.engine.bookkeeper.api              import Store
from   vut.engine.orchestrator.exploration.task_list   import SelectionError
from   vut.engine.orchestrator.exploration            import selection
from   vut.services.lib.labels                             import view_at
from   vut.services.lib.labels._file                       import LabelFileError
from   vut.engine.orchestrator.plan.wish               import (HELP as WISH_HELP,
                                                               WishError,
                                                               parse_wish,
                                                               with_targets)
from   vut.engine.orchestrator.plan.wish               import USAGE_TOKEN_TUPLE \
                                                               as WISH_TOKEN_TUPLE
from   vut.engine.operations                           import subject_provision
from   vut.engine.operations.session                   import (run_test,
                                                               Request)
from   vut.engine.orchestrator.run.adapter             import \
                                                       test_configuration_of
from   vut.auxiliary.directory_mutex                   import DirectoryBusy
from   ._core                                          import usage_line
from   ._exit                                          import E_ExitCode


USAGE = usage_line("usage: hwut.accept",
                    WISH_TOKEN_TUPLE
                    + ("[<file-glob> [choice-glob]...]",
                         "[--yes]", "[--force]",
                         "[--stderr-tol[erated]]",
                         "[--directory=<path>]"))

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
    --yes               unattended: do not ask, bless what needs
                        blessing. It asserts 'I have already looked'
    --force             overwrite a STANDING nominal, skipping the
                        merge. It asserts 'overwrite the thing I judge
                        against' -- the one operation here that
                        destroys evidence, so it is never implied
    --stderr-tol[erated]
                        note the choice's stderr IGNORED. Required
                        where stderr SPOKE: there is no default there,
                        because a default leaves the user clueless in
                        front of output that deviates
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
    1   a fault was met, or a key needed a merge and was left alone
    2   the command line cannot be read
    3   the command line reads, and asks for nothing

OTHER
    --help              this text"""


#  Sidecars live beside a candidate under the same stem; they are not
#  subjects and are never promoted.
SIDECAR_SUFFIX_TUPLE = (".raw", ".times", ".when")

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
    from vut.engine.bookkeeper.api import SUBJECT_BY_SUFFIX_DB
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
    the test ('same_nominal_f'): blessing one choice there rewrites
    the pole the others are judged by.
    """
    shared_f = bool(getattr(store.bookkeeper.naming, "same_nominal_f",
                            False))
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
        if store.bookkeeper.stain(test, choice) is not None: continue
        for subject in subject_tuple_of(store, test, choice):
            if subject == STDERR_SUBJECT: continue      # never promoted
            key_list.append(CKey(
                test, case.source_file, choice, subject,
                store.bookkeeper.candidate_path(test, choice, subject),
                store.bookkeeper.nominal_path(test, choice, subject),
                shared_f))
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


def stderr_decision(store, spoke_db, tolerate_f, write):
    """
    RETURN: list, the (test, choice, size) triples REFUSED -- stderr
            spoke, no note tolerates it, '--stderr-tol' not said.
            Empty where nothing stands in the way.

    THERE IS NO DEFAULT where stderr speaks: a default would leave the
    user clueless in front of output that deviates. With
    '--stderr-tol' the note IGNORED is written; without it the choice
    is refused BY NAME, with both remedies.
    """
    refused_list = []
    for (test, choice), size in sorted(
            spoke_db.items(),
            key=lambda item: (item[0][0], item[0][1] or "")):
        note = store.stderr_note(test, choice)
        if note is E_StderrNote.IGNORED: continue
        if tolerate_f:
            store.note_stderr(test, choice, E_StderrNote.IGNORED)
            write("NOTE: stderr of '%s%s' is now IGNORED (%d bytes "
                  "spoke)" % (test,
                              "" if choice is None else " " + choice,
                              size))
            continue
        refused_list.append((test, choice, size))
    return refused_list


def token_terminated_f(text):
    """
    RETURN: bool, True where the stream's LAST LINE is the closing
            token '<hwut-end>' (R-70) -- the stream's own testimony
            that it completed.
    """
    if text is None: return False
    line_list = text.splitlines()
    return bool(line_list) and line_list[-1] == "<hwut-end>"


def classify(key, force_f):
    """
    RETURN: str, what accept is to do with the key -- one of:

            'bless'   no nominal stands: the first pole
            'merge'   a nominal stands and '--force' was not said:
                      this is a CHANGE, and 'hwut.merge's business
            'force'   a nominal stands and '--force' was said
    """
    if   not key.nominal_stands_f: return "bless"
    elif force_f:                  return "force"
    else:                          return "merge"


def ask(key, text, write, read_line):
    """
    RETURN: bool, True where the user blessed this key.

    The CANDIDATE is shown -- the canonicalised record, which is what
    the framework compares. Anything but 'y' leaves the pole alone.
    """
    write("")
    write("=" * 78)
    write("ACCEPT  %s" % key.name)
    write("-" * 78)
    for line in text.splitlines():
        write("    %s" % line)
    write("-" * 78)
    write("    candidate: %s" % key.candidate_path.name)
    write("    nominal:   %s" % key.nominal_path.name)
    write("accept this as the nominal? [y/N] ")
    answer = read_line()
    return answer.strip().lower() in ("y", "yes")


def main(argv=None, write=None, read_line=None):
    """
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
    if "--help" in argv:
        write(HELP)
        return E_ExitCode.OK

    try:
        wish, rest_list = parse_wish(argv)
    except WishError as error:
        write("REFUSED: %s" % error)
        write(USAGE)
        return E_ExitCode.REFUSED

    directory    = "."
    yes_f        = False
    force_f      = False
    stderr_tol_f = False
    word_list   = []
    unknown     = []
    for argument in rest_list:
        if   argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        elif argument == "--yes":         yes_f   = True
        elif argument == "--force":       force_f = True
        elif argument in ("--stderr-tol", "--stderr-tolerated"):
            stderr_tol_f = True
        elif argument.startswith("-"):    unknown.append(argument)
        else:                             word_list.append(argument)
    if unknown:
        write("REFUSED: 'hwut.accept' does not take: %s"
              % ", ".join(sorted(unknown)))
        write(USAGE)
        return E_ExitCode.REFUSED
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
        inherited, ascent_fault_list = ascended_spec(directory)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    for fault in ascent_fault_list:
        write(str(fault))

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

    #  ONE ACTION, ONE PLACE ('exploration/selection.py'). The
    #  Bookkeeper is the SELECTION'S -- 'base_f=True' because this
    #  face reads candidates whatever the wish asked, and a bare wish
    #  asks no base.
    try:
        found = selection.of_directory(directory, wish, label_view,
                                       inherited=inherited,
                                       base_f=True)
        result     = found.result_db["."]
        bookkeeper = found.bookkeeper_db["."]
        for fault in found.fault_tuple:
            write("FAULT: %s" % fault)
        id_db = TestIdDb(directory)
        store = Store(bookkeeper)
        case_sequence = [entry.case for entry in found.case_list]
        #  A FACE THAT NAMES A RUN AND BLESSES NOTHING MUST SAY WHY:
        #  a literal target lifts the silence, and a glob wholly
        #  swallowed by it speaks (disc-8).
        for text in found.warning_tuple:
            write(text)
    except SelectionError as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED

    #  SUBJECT PROVISION, THROUGH THE ONE CHANNEL (operations disc-2):
    #  'provider_of' decides per case whether the recording is current
    #  or the test must run; where it must, it RUNS -- this face is
    #  the source of the nominal and cannot wait on a run somebody
    #  else makes (E-40). The run goes through the session, so it is
    #  held, recorded and booked exactly as 'hwut.run' books it.
    language_setup = result.app_set.directory_spec.language_setup
    for case in case_sequence:
        configuration = test_configuration_of(
                            result.app_set.app_db[case.source_file],
                            directory, language_setup=language_setup)
        _, decision = subject_provision.provider_of(configuration, store,
                                                    case.choice)
        if decision.what is not subject_provision.E_Decision.PROVIDE:
            continue
        write("RUN: %s%s   %s" % (case.source_file,
                                  "" if case.choice is None
                                  else " " + case.choice,
                                  decision.because))
        try:
            asyncio.run(run_test(configuration,
                                 Request(choice=case.choice, record=True),
                                 bookkeeper=bookkeeper))
        except DirectoryBusy as error:
            write("REFUSED: %s" % error)
            return E_ExitCode.REFUSED

    #  STDERR FIRST: where it spoke and nothing tolerates it, the
    #  whole choice is refused before any pole is touched.
    refused_list = stderr_decision(store,
                                   stderr_spoke_db(store, case_sequence),
                                   stderr_tol_f, write)
    if refused_list:
        write("REFUSED: stderr SPOKE and no note tolerates it --")
        for test, choice, size in refused_list:
            write("    %s%s   (%d bytes)"
                  % (test, "" if choice is None else " " + choice,
                     size))
        write("stderr is for ERROR REPORTING and is never subject to")
        write("testing. Either state '--stderr-tol' to note it IGNORED,")
        write("or -- where the reporting is itself under test -- flush")
        write("it to a FILE and name that file in 'output'.")
        return E_ExitCode.FAULT

    #  A STAINED CHOICE IS NEVER PROMOTED, and never silently: the
    #  refusal is spoken, by name, with the way out.
    stained_list = [(case.source_file, case.choice)
                    for case in case_sequence
                    if store.bookkeeper.stain(
                           case.source_file,
                           case.choice) is not None]
    for test, choice in stained_list:
        write("REFUSED to bless: '%s%s' bears a STAIN -- it switched "
              "results between repeats." % (test,
                                            "" if choice is None
                                            else " " + choice))
    if stained_list:
        write("    Acceptance declares the POLE of the good cluster; a "
              "test that will not hold")
        write("    still has no cluster. Prove it steady with "
              "'hwut.stability --repeat=<n>',")
        write("    or -- urgently -- 'hwut.remove' it and accept afresh.")

    key_list = key_list_of(store, case_sequence)
    if not key_list:
        write("NOTE: nothing to accept -- the selection holds no "
              "recorded candidate")
        return E_ExitCode.EMPTY

    #  A shared nominal whose choices DISAGREE cannot be blessed: the
    #  author's premise is broken, and picking a winner would hide it.
    conflict_db = shared_conflict_db(key_list)
    conflict_set = set()
    for path_text, group in sorted(conflict_db.items()):
        write("REFUSED to pick: the choices below share ONE nominal "
              "('same') and DISAGREE --")
        write("    nominal: %s" % os.path.basename(path_text))
        for key in group:
            write("    %s" % key.name)
            conflict_set.add(id(key))
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

    blessed_list, merge_list, skipped_list = [], [], []
    for key in key_list:
        if id(key) in conflict_set:
            skipped_list.append(key)
            continue
        verdict = classify(key, force_f)
        if verdict == "merge":
            merge_list.append(key)
            continue
        text = read_text(key.candidate_path)
        if text is None:
            write("FAULT: the candidate of '%s' cannot be read"
                  % key.name)
            skipped_list.append(key)
            continue
        if key.shared_f and not yes_f:
            write("NOTE: '%s' shares its nominal with every choice of "
                  "the test" % key.name)
        if not yes_f and not ask(key, text, write, read_line):
            skipped_list.append(key)
            continue
        store.accept(key.test, key.choice, key.subject, text)
        #  THE REGISTER: an id is born at first accept (test_id_db).
        #  Idempotent -- a standing run returns its standing id.
        id_db.run_id_of(key.test, key.choice, allocate_f=True)
        #  THE BOOK: the acceptance's instant (E-36), so the three
        #  records of acceptance agree (E-41). Before this line the
        #  face itself accepted outside the book.
        store.bookkeeper.note_accept(key.test, key.choice)
        blessed_list.append(key)

    write("")
    write("=" * 78)
    write("ACCEPTED  %d of %d" % (len(blessed_list), len(key_list)))
    write("-" * 78)
    for key in blessed_list:
        write("    blessed        %s" % key.name)
    for key in merge_list:
        write("    merge required %s" % key.name)
    for key in skipped_list:
        write("    left alone     %s" % key.name)
    if merge_list:
        write("")
        write("A nominal already stands for the keys above. That is a "
              "CHANGE, not a")
        write("first blessing: use 'hwut.merge', or '--force' to "
              "overwrite the pole.")
    write("=" * 78)

    if result.fault_list or merge_list or conflict_db:
        return E_ExitCode.FAULT
    return E_ExitCode.OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
