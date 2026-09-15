"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.stability' COMMAND LINE -- run the same wish SEVERAL
         TIMES and report what did not stay the same.

    hwut.stability <wish> [--repeat=<n>] [--cadence]
                          [--directory=<path>] [--strategy=<name>]

A suite that passes once has said one thing: it passed once. Whether it
passes RELIABLY is a different question, and nothing answers it by being
asked more politely. This face asks it by repetition.

FOUR FINDINGS, one fault and three warnings:

    VERDICT     the same key came out 'ok' in one repeat and not in
                another. THE FAULT: a suite nobody can trust, and the
                only finding that moves the exit status.

    BYTES       every repeat agreed on the verdict, and the recorded
                subjects DIFFER. The tolerance absorbed it -- which is
                what tolerance is for -- but the test is one tightening
                away from flaky and nobody would know. A warning.

    LENGTH      the cadences differ in LINE COUNT. Nothing can be
                aligned line by line after that, so it is said first
                and the timing arithmetic of that key is not attempted.
                A warning.

    CADENCE     the SAME LINE took GROSSLY different times across the
                repeats -- ASKED FOR by '--cadence', never by default.
                TWO BARS, BOTH REQUIRED: a spread above FIVE SECONDS,
                far past any resolution question, AND some FIFTY TIMES
                the usual delta of that line. Not two, not five.
                Nothing clearing both is noise; nothing below them can
                be told from noise by any means the framework has. A
                warning, and only ever a warning.

TIMING IS NOT CHECKED UNLESS ASKED. '--cadence' asks. The framework
sets '--jobs', which is ITS OWN parallelism and NOT the machine's
load: a hundred niced processes and ten busy ones are not comparable,
and nothing recorded tells them apart. No ratio it could form, no null
model it could fit and no threshold it could calibrate would mean
anything. THE TESTER WHO ASKS KNOWS THE MACHINE AND CHOSE THE MOMENT;
they are the calibration, and the framework has none.

CADENCE IS NEVER A SHOW STOPPER: it does not stain and it does not
move the exit status, asked for or not. Only a VERDICT does that --
two runs of one test that disagree on a verdict disagree, full stop,
with no statistics between the reading and the report.

WHAT IS NEVER PRINTED: a delta, an average, a ratio -- no number the
machine chose. The findings are COUNTS and NAMES, so that this face can
itself be tested. '--verbose' opens the numbers for a human reading a
terminal; a GOOD file never holds them.

THE CADENCE MUST BE ASKED FOR: the repeats run with '--timing', which
is what writes the per-line deltas beside each candidate. Without it
there is nothing to compare and the cadence findings do not arise.

EXIT STATUS (E-1, services/_exit.py):
    0  every repeat agreed on every verdict (warnings do not move it)
    1  a verdict differed between repeats
    2  the command line cannot be read
    3  the command line reads, and asks for nothing
______________________________________________________________________________
"""
import asyncio
import os
import statistics
import sys

from   vut.engine.bookkeeper.api              import Bookkeeper
from   vut.engine.bookkeeper.api            import Store
from   vut.engine.operations                import subject_provision
from   vut.engine.orchestrator.exploration.task_list import SelectionError
from   vut.engine.orchestrator.plan.wish             import (HELP as WISH_HELP,
                                                             WishError,
                                                             parse_wish)
from   vut.engine.orchestrator.plan.wish             import USAGE_TOKEN_TUPLE \
                                                             as WISH_TOKEN_TUPLE
from   vut.engine.orchestrator.run.strategy          import (STRATEGY_DB,
                                                             DEFAULT_STRATEGY_NAME)
from   ._core                                        import usage_line
from   ._target import split_words, TargetError
from   ._exit                                        import E_ExitCode
from   vut.services.lib.cmdline import did_you_mean, option_tuple

REPEAT_DEFAULT  = 3
#  THE TWO BARS a cadence finding must clear (disc-7). High enough that
#  no calibration is needed: the framework cannot measure the machine's
#  load, so it speaks only of the gross.
ABSOLUTE_MIN = 5.0     # seconds of spread, far past any resolution
FACTOR_MIN   = 50.0    # times the usual delta -- not 2, not 5

USAGE = usage_line("usage: hwut.stability",
                   WISH_TOKEN_TUPLE
                   + ("[<file-glob> [choice-glob]...]",
                      "[--repeat=<n>]",
                      "[--cadence]", "[--strategy=<name>]",
                      "[--verbose]", "[--directory=<path>]"))

#  The licence line and the rule are the FILE's, not the face's.
HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + WISH_HELP + "\n" + USAGE


class CFinding:
    """ONE KEY'S ANSWER, over all repeats.

    'key'      (directory, node) as the run's own summary names it.
    'verdict'  the set of verdict words seen, one per repeat.
    'note'     list of str, what did not stay the same. Empty: steady.
    'detail'   list of str, THE NUMBERS behind the notes -- ratios and
               deltas, all of them the machine's. Shown under
               '--verbose' and never otherwise, so a GOOD file cannot
               come to hold one.
    'unstable' True where a VERDICT differed -- the one fault.
    """
    __slots__ = ("key", "verdict_tuple", "note_list", "detail_list",
                 "unstable_f")

    def __init__(self, key, verdict_tuple):
        self.key           = key
        self.verdict_tuple = verdict_tuple
        self.note_list     = []
        self.detail_list   = []
        self.unstable_f    = False


def mean_of(value_tuple):
    """RETURN: float, the arithmetic mean; 0.0 for an empty tuple."""
    if not value_tuple: return 0.0
    return sum(value_tuple) / len(value_tuple)


def deviation_of(value_tuple):
    """
    RETURN: float, the POPULATION standard deviation of the values;
            0.0 where fewer than two stand.

    Population, not sample: the repeats are not a sample of a larger
    set of repeats, they are all the repeats there are.
    """
    if len(value_tuple) < 2: return 0.0
    average = mean_of(value_tuple)
    return (sum((v - average) ** 2 for v in value_tuple)
            / len(value_tuple)) ** 0.5



def unsteady_line_tuple(cadence_tuple, factor_min=FACTOR_MIN,
                        absolute_min=ABSOLUTE_MIN):
    """
    YIELD: [0] int    the line index, from 0, whose delta was GROSSLY
                      out of step across the repeats
           [1] float  that line's spread, in SECONDS
           [2] float  that line's factor: spread / the usual delta

    TWO BARS, BOTH REQUIRED (disc-7):

        ABSOLUTE  the spread exceeds 'absolute_min' -- five seconds,
                  so far past the timer's resolution that precision is
                  not in question
        RELATIVE  AND is 'factor_min' times THE MEDIAN delta of that
                  line -- fifty, not two, not five

    THE MEDIAN, NOT THE AVERAGE. 'spread / average' cannot exceed the
    number of repeats -- one slow run among four is at most 4x, whatever
    its size -- so a 50x bar against the average is unreachable below
    fifty repeats. The median is what the line USUALLY costs, and one
    slow repeat does not move it: the same outlier scores thousands.

    NOTHING CLEARING BOTH BARS IS NOISE, and nothing below them can be
    told from noise by any means the framework has. It sets '--jobs',
    which is ITS OWN parallelism and NOT the machine's load: a hundred
    niced processes and ten busy ones are not comparable, and nothing
    recorded tells them apart. So no ratio is formed, no null model is
    fitted, and no threshold is calibrated -- the bars are high enough
    that none of it is needed.

    'cadence_tuple' holds one delta list per repeat, all of the same
    length -- a differing length is LENGTH's finding and is answered
    before this is asked.
    """
    if not cadence_tuple: return
    for index in range(len(cadence_tuple[0])):
        across  = tuple(cadence[index] for cadence in cadence_tuple)
        spread  = max(across) - min(across)
        if spread < absolute_min:                   continue
        #  'THE USUAL DELTA' IS THE MEDIAN, not the average. The
        #  average is dragged up by the very outlier being measured,
        #  and 'spread / average' can never exceed the REPEAT COUNT --
        #  so a 50x bar against it is unreachable below 50 repeats.
        #  The median is not moved by one slow repeat, which is
        #  exactly what 'usually' means.
        usual   = statistics.median(across)
        if usual <= 0.0:                            continue
        factor  = spread / usual
        if factor < factor_min:                     continue
        yield index, spread, factor


def key_of(node_name):
    """
    RETURN: (test, choice), the store's key parts for a plan node --
            'test-ok.sh'       -> ('test-ok.sh', None)
            'test-ok.sh green' -> ('test-ok.sh', 'green')

    THE FILE NAME WHOLE keys a record (configuration.key_name): two
    tests of one name and two extensions belong together and must not
    share a record.
            None, for a node that is not a test: a build or a session,
            which records no subject and has no cadence.

    The node's own name is the plan's word (plan/form.py): the target
    form for a test, a bracketed word for the rest.
    """
    if "[" in node_name: return None
    file_name, _, choice = node_name.partition(" ")
    return file_name, (choice if choice else None)


def snapshot_of(root, verdict_db, subject_tuple):
    """
    RETURN: dict, (directory, node) -> (verdict, {subject: text},
            {subject: cadence}) for every test node of one repeat.

    THE STREAMS COME THROUGH THE ONE CHANNEL (operations disc-2,
    'subject_provision.bare_provider_of': read, never execute -- a
    snapshot is of what a repeat produced). A subject with no
    candidate is absent from the text map, a subject with no cadence
    absent from the cadence map -- never an empty stand-in for either.
    """
    result   = {}
    store_db = {}
    for key, verdict in verdict_db.items():
        directory, node_name = key
        parts = key_of(node_name)
        if parts is None: continue
        test, choice = parts
        if directory not in store_db:
            store_db[directory] = Store(
                Bookkeeper(os.path.join(root, directory)))
        store   = store_db[directory]
        text_db = {}
        time_db = {}
        for subject in subject_tuple:
            provider, decision = subject_provision.bare_provider_of(
                                     store, test, choice,
                                     subject_name_list=(subject,))
            if decision.what is not subject_provision.E_Decision.ABSENT:
                subjects = asyncio.run(provider.provide())
                if subject in subjects:
                    with subjects[subject].open() as reader:
                        text_db[subject] = reader.read()
            cadence = store.timing(test, choice, subject)
            if cadence is not None:
                time_db[subject] = cadence
        result[key] = (verdict, text_db, time_db)
    return result


def finding_list_of(snapshot_list, cadence_f):
    """
    RETURN: list[CFinding], one per key that any repeat saw, sorted by
            key; a key seen by some repeats and not others is itself a
            verdict instability ('absent' stands for the repeats that
            did not see it).

    The four findings of this face's PURPOSE, in that order: VERDICT
    first because it is the fault, LENGTH before CADENCE because an
    unalignable pair cannot be timed.
    """
    key_set = set()
    for snapshot in snapshot_list: key_set.update(snapshot)

    finding_list = []
    for key in sorted(key_set):
        verdict_tuple = tuple(snapshot[key][0] if key in snapshot
                              else "absent" for snapshot in snapshot_list)
        finding = CFinding(key, verdict_tuple)
        if len(set(verdict_tuple)) > 1:
            finding.unstable_f = True
            finding.note_list.append(
                "VERDICT differs between repeats: %s"
                % ", ".join(verdict_tuple))
            finding_list.append(finding)
            continue

        seen_list = [snapshot[key] for snapshot in snapshot_list
                     if key in snapshot]
        subject_set = set()
        for _, text_db, _ in seen_list: subject_set.update(text_db)
        for subject in sorted(subject_set):
            text_tuple = tuple(text_db.get(subject)
                               for _, text_db, _ in seen_list)
            if len(set(text_tuple)) > 1:
                finding.note_list.append(
                    "BYTES differ, verdict did not: subject '%s' -- the "
                    "tolerance absorbed it" % subject)

        #  TIMING IS NOT CHECKED UNLESS ASKED (disc-7). The framework
        #  cannot measure the machine's load, so it does not pretend
        #  to: the cautious tester who knows the machine asks for it,
        #  and THEY are the calibration.
        if not cadence_f:
            if finding.note_list: finding_list.append(finding)
            continue

        cadence_subject_set = set()
        for _, _, time_db in seen_list: cadence_subject_set.update(time_db)
        for subject in sorted(cadence_subject_set):
            cadence_tuple = tuple(time_db[subject]
                                  for _, _, time_db in seen_list
                                  if subject in time_db)
            if len(cadence_tuple) < 2: continue
            if len(set(len(c) for c in cadence_tuple)) > 1:
                finding.note_list.append(
                    "LENGTH differs: subject '%s' emitted a different "
                    "number of lines; not timed" % subject)
                continue
            unsteady = tuple(unsteady_line_tuple(cadence_tuple))
            if unsteady:
                finding.note_list.append(
                    "CADENCE unsteady: subject '%s', %d line(s) of %d, "
                    "first at line %d"
                    % (subject, len(unsteady), len(cadence_tuple[0]),
                       unsteady[0][0] + 1))
                for index, spread, factor in unsteady:
                    finding.detail_list.append(
                        "line %d  spread=%.3fs  factor=%.0fx  deltas %s"
                        % (index + 1, spread, factor,
                           " ".join("%.6f" % cadence[index]
                                    for cadence in cadence_tuple)))
        if finding.note_list: finding_list.append(finding)
    return finding_list


def report_line_tuple(finding_list, repeat_n, key_n, verbose_f=False,
                      stained_list=(), cleared_list=()):
    """
    YIELD: [0] str  one line of the report, in reading order: the
                    steady statement or the findings, then the tally.

    NO NUMBER THE MACHINE CHOSE, unless 'verbose_f': a delta, an
    average and a ratio are all the machine's, and a GOOD file that
    held one would be a lie on the next host.
    """
    yield "REPEATS: %d   KEYS: %d" % (repeat_n, key_n)
    yield ""
    if not finding_list:
        yield "STEADY: every repeat agreed, on every key."
    else:
        for finding in finding_list:
            directory, node_name = finding.key
            yield "%s: %s" % (directory, node_name)
            for note in finding.note_list:
                yield "    %s" % note
            if verbose_f:
                for detail in finding.detail_list:
                    yield "        %s" % detail
    for key in stained_list:
        yield ""
        yield "STAINED: %s: %s -- not run again until proven steady " \
              "over %d repeat(s)." % (key[0], key[1], repeat_n)
        yield "         In an urgent case: 'hwut.remove <test> " \
              "[<choice>]' and accept afresh."
    for key in cleared_list:
        yield ""
        yield "CLEARED: %s: %s -- steady over %d repeat(s); the stain " \
              "is gone." % (key[0], key[1], repeat_n)
    yield ""
    unstable_n = sum(1 for f in finding_list if f.unstable_f)
    warned_n   = len(finding_list) - unstable_n
    yield "TALLY: %d unstable, %d warned, %d steady" \
          % (unstable_n, warned_n, key_n - len(finding_list))


def main(argv=None, write=None, write_error=None):
    """
    RETURN: E_ExitCode, the exit status (E-1): OK where every repeat
            agreed on every verdict -- WARNINGS DO NOT MOVE IT -- FAULT
            where one differed, REFUSED where the command line cannot
            be read, EMPTY where it reads and asks for nothing.

    'write' takes one line at a time; 'print' where none is given, so a
    suite captures the face without a process.
    """
    if write is None:
        write = print
    if write_error is None:
        def write_error(line): \
           print(line, file=sys.stderr)
    if argv is None:
        argv = sys.argv[1:]
    if "--help" in argv:
        write(HELP)
        return E_ExitCode.OK

    try:
        wish, rest_list = parse_wish(argv)
    except WishError as error:
        write("REFUSED: %s" % error)
        write(USAGE)
        return E_ExitCode.REFUSED

    directory  = "."
    repeat_n   = REPEAT_DEFAULT
    strategy   = DEFAULT_STRATEGY_NAME
    verbose_f  = False
    cadence_f  = False
    subject_tuple = ("stdout",)
    unknown    = []
    #  BARE WORDS ARE TARGETS (the 1.0 short form): this face does not
    #  desugar them itself -- they travel in 'argv' to 'hwut.run',
    #  which does. Collected here only so the door does not refuse
    #  them as unknown options.
    word_list = []
    for argument in rest_list:
        if   argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        elif argument == "--verbose": verbose_f = True
        elif argument == "--cadence": cadence_f = True
        elif argument.startswith("--repeat="):
            text = argument[len("--repeat="):]
            if not text.isdigit() or int(text) < 2:
                write("REFUSED: '--repeat' takes an integer of 2 or more, "
                      "not '%s' -- one run cannot disagree with itself"
                      % text)
                write(USAGE)
                return E_ExitCode.REFUSED
            repeat_n = int(text)
        elif argument.startswith("--strategy="):
            name = argument[len("--strategy="):]
            if name not in STRATEGY_DB:
                write("REFUSED: '--strategy' takes one of %s, not '%s'%s"
                      % (", ".join(sorted(STRATEGY_DB)), name,
                         did_you_mean(name, sorted(STRATEGY_DB),
                                      among_listed_f=True)))
                write(USAGE)
                return E_ExitCode.REFUSED
            strategy = name
        else:
            if argument.startswith("-"): unknown.append(argument)
            else:                        word_list.append(argument)
    if unknown:
        write("REFUSED: 'hwut.stability' does not take: %s"
              % ", ".join(sorted(unknown))
              + did_you_mean(unknown[0], option_tuple(USAGE)))
        write(USAGE)
        return E_ExitCode.REFUSED
    #  A TEST NAMED BY PATH stands in the directory the path names
    #  ('services/_target.py').
    try:
        directory, word_list = split_words(word_list, directory)
    except TargetError as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist" % directory)
        write(USAGE)
        return E_ExitCode.REFUSED
    root = os.path.abspath(directory)
    #  THE REPEAT RE-READS THE WORDS, so it must see the BARE names:
    #  the directory the path named is 'root' now.
    argv_bare = [os.path.basename(word)
                 if "/" in word and not word.startswith("-") else word
                 for word in argv]

    try:
        snapshot_list = _repeat(root, argv_bare, repeat_n, strategy,
                                subject_tuple, write_error)
    except SelectionError as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    if not any(snapshot_list):
        write("EMPTY: the wish selects no test in '%s'" % directory)
        return E_ExitCode.EMPTY

    key_set = set()
    for snapshot in snapshot_list: key_set.update(snapshot)
    finding_list = finding_list_of(snapshot_list, cadence_f)
    stained_list, cleared_list = _judge(root, key_set, finding_list,
                                        repeat_n)
    for line in report_line_tuple(finding_list, repeat_n, len(key_set),
                                  verbose_f, stained_list, cleared_list):
        write(line)

    if any(finding.unstable_f for finding in finding_list):
        return E_ExitCode.FAULT
    return E_ExitCode.OK


def _judge(root, key_set, finding_list, repeat_n):
    """
    RETURN: (list, list) -- the keys STAINED by this run, and the keys
            whose stain this run CLEARED, both sorted.

    THE STAIN IS THE POINT OF THIS FACE. A key whose verdict differed
    bears one, stating the count that convicted it. A key that was
    stained, stood steady here, and was repeated AT LEAST as often as
    the conviction, is cleared -- fewer repeats than convicted it have
    not answered the charge and leave the stain standing.
    """
    unstable_set = {f.key for f in finding_list if f.unstable_f}
    verdict_db   = {f.key: f.verdict_tuple for f in finding_list}
    stained, cleared = [], []
    store_db = {}
    for key in sorted(key_set):
        directory, node_name = key
        parts = key_of(node_name)
        if parts is None: continue
        test, choice = parts
        if directory not in store_db:
            store_db[directory] = Bookkeeper(os.path.join(root, directory))
        book = store_db[directory]
        if key in unstable_set:
            book.note_stain(test, choice, repeat_n,
                            verdict_db.get(key, ()))
            stained.append(key)
            continue
        stain = book.stain(test, choice)
        if stain is None: continue
        if repeat_n >= stain.get("repeat_n", 0):
            book.clear_stain(test, choice)
            cleared.append(key)
    return stained, cleared


def _float_or_none(text):
    """RETURN: float, the number that text spells
               None,  it spells none."""
    try:                return float(text)
    except ValueError:  return None


def _repeat(root, argv, repeat_n, strategy, subject_tuple, write_error):
    """
    RETURN: list[dict], one snapshot per repeat -- 'snapshot_of' over
            the verdicts that repeat came to.

    EVERY REPEAT IS A WHOLE RUN of the same wish, through 'hwut.run'
    with '--timing': the same face a person would call, so what is
    measured is what they would get. The run's own output is swallowed;
    this face reports on the runs, not for them.
    """
    from . import run as run_service
    from vut.engine.protocol.summary import fold

    #  THE FACE'S OWN OPTIONS DO NOT TRAVEL to 'hwut.run', which does
    #  not take them. THE WISH'S WORDS DO -- options and bare targets
    #  alike: one selection language, and the repeats must run the
    #  very wish the person stated.
    wish_argv = [a for a in argv
                 if not a.startswith(("--repeat=", "--strategy=",
                                      "--directory="))
                 and a not in ("--verbose", "--cadence")]
    snapshot_list = []
    for _ in range(repeat_n):
        event_list = []
        run_service.main(wish_argv + ["--timing",
                                      "--strategy=%s" % strategy,
                                      "--directory=%s" % root,
                                      "--silent"],
                         write=lambda line: None,
                         write_error=lambda line: None,
                         event_sink=event_list.append,
                         despite_stain_f=True,
                         #  EVERY REPEAT MUST EXECUTE: subject
                         #  provision (disc-2) would otherwise hand
                         #  the second repeat the first one's
                         #  recording, and five readings of one file
                         #  agree about anything.
                         force_run_f=True)
        snapshot_list.append(
            snapshot_of(root, fold(event_list).verdict_db, subject_tuple))
    return snapshot_list


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ._exit import guarded
    sys.exit(guarded("hwut.stability", main))
