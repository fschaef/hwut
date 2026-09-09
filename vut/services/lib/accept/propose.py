# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
hwut.accept.propose -- the differences, as a file to read and hand back.

    hwut.accept.propose -o <file> [<n>] [<target>...] [--directory=<path>]

WHAT IT IS FOR. A run reports thirty failures across seven directories.
Blessing them one by one is a day's work; blessing them in bulk is
blind, and a real regression hides in the mass. This face writes what
WOULD be blessed, as a file you read and edit, so that the bulk act
happens with your eyes open.

IT BLESSES NOTHING AND RUNS NOTHING. It reads what already stands.
Where a recording is stale, run 'hwut.run' first: a proposal built on
old candidates proposes old text.

    hwut.run                             produce the candidates
    hwut.accept.propose -o p.txt 5       write what could be blessed
    <read p.txt, delete or '#' out what you disagree with>
    hwut.accept.apply p.txt              bless what is left

-------------------------------------------------------------------
WHAT GOES WHERE
-------------------------------------------------------------------
'-o <file>' IS REQUIRED. The file holds ONLY what can be blessed, so
it is handed back unedited save for the targets you refuse. What
CANNOT be proposed goes to STDOUT, one line each:

    DIFF(<dir>/<test-app> <choice>) > <n> lines

Those you open yourself, with 'hwut.report.details'. A proposal one must strip
before use is not a proposal, which is why the two never mix.

-------------------------------------------------------------------
WHAT A PROPOSAL SAYS
-------------------------------------------------------------------
    # TEST RUN: <dir>/<test-app> <choice>
    # -- [4711] OUT:  "<what the run produced>"
    #    [4712] OUT:  "<and the next line, if it differs too>"
    # => [4721] GOOD: "<what stands as the nominal today>"
    #    [4722] GOOD: "<and the next>"
    <dir>/<test-app> <choice>

ACCEPT THIS AND THE 'OUT' LINES BECOME THE NOMINAL, in place of the
'GOOD' lines under them. Nothing else in the nominal moves. A line
that AGREES never appears -- a proposal shows only what would change.

ADJACENT DIFFERENCES ARE ONE BLOCK: several lines replaced by several
read as one replacement. '--' opens what the run produced, '=>' what
it replaces, a bare indent continues either. Every line carries its
own number, padded to one width per case; both sides are QUOTED and
start at one column, so space at either end is visible. An empty
'OUT' is a nominal line that GOES; an empty 'GOOD', a line that
ARRIVES.

The text shown is THE FILE'S OWN LINE, not the engine's compared cell
-- what becomes the nominal is what you see, spaces and all.

    SUBJECT (what the run produced)   NOMINAL (what stands today)
        Hans was a nice man.              Hans was a Nazi.
        Berta was his bride.              Berta was his bride.
        Frederik was a baker.             Frederik was a maker.

    # TEST RUN: suite/TEST/story.sh
    # -- [1] OUT:  "Hans was a nice man."
    # => [1] GOOD: "Hans was a Nazi."
    # -- [3] OUT:  "Frederik was a baker."
    # => [3] GOOD: "Frederik was a maker."
    suite/TEST/story.sh

-------------------------------------------------------------------
WHAT IS NEVER PROPOSED
-------------------------------------------------------------------
ONLY A DIVERGENCE FROM THE NOMINAL. A proposal is an act on the pole,
and it makes sense only where the run COMPLETED and the judgement went
against the recording -- the book's

    not-equivalent-with-nominal   the shapes of a difference
    not-equivalent-grew           (E_TestRunResult)
    not-equivalent-shrank
    not-equivalent-diverged

EVERY OTHER VERDICT NAMES A RUN THAT BROKE: a source not found, an
interpreter missing, an application contained by a cap, a session
gone, a stream that never testified, a witness convicted of
instability. Whatever such a run left behind is WRECKAGE, and wreckage
is not a pole. Fix the run; then judge what it produces.

    NO CANDIDATE     nothing ran, so there is nothing to judge.
    NO NOMINAL       a FIRST blessing declares the pole and is a
                     deliberate act, focussed on the one subject it
                     speaks for -- never one line among fifty in a
                     file somebody skimmed. Use 'hwut.accept' on it
                     by name.
    A DIFFERENCE     it is a real difference the engine found, but
    OVER <n>         too large to take on trust. Named on stdout for
                     'hwut.report.details'.
    NO DIFFERENCE    the compare engine holds the two equivalent under
                     THIS choice's own tolerances -- a numeric inside
                     its ratio, an eq-pattern, an ignored region.
                     Not a difference, so not proposed.

-------------------------------------------------------------------
HOW THE DIFFERENCE IS READ
-------------------------------------------------------------------
A LINE WALK. Line i of the candidate faces line i of the nominal;
where they differ, the candidate's line is recorded as the
REPLACEMENT of the nominal's -- which is exactly what accepting does.
Past <n> replacements the answer is already 'more than n' and the walk
stops.

THE ENGINE JUDGES EACH POSITION, so a tolerance holds here as it holds
in the run. It is asked only where the BYTES already disagree: an
identical line cannot differ under any tolerance, so an agreeing file
of a thousand lines costs no engine call at all.

NO ALIGNMENT IS ATTEMPTED. Pairing two streams properly is an A* over
edit sequences costing the square of the text; it was tried and did
not return on a rewritten file. A proposal does not need it -- a
replacement is POSITIONAL. THE COST OF THAT: a file with a line
INSERTED near its top differs at every position after it, so it reads
as many replacements and is named on stdout rather than shown as the
single insertion it is. The safe direction: you are told to look,
never told there is nothing to look at.

-------------------------------------------------------------------
THE WISH
-------------------------------------------------------------------
Every word 'hwut.accept' takes is taken here and means the same:
'--glob', '--dir', '--exclude', '--label', '--wishlist <file>', the
positional short form. It NARROWS the set considered, and nothing
more.

'--fail' IS SUPERFLUOUS, AND MISLEADING. A proposal is by construction
about what differs, so the failing set is what a bare call already
reads. And '--fail' selects on the BOOK's last verdict, a MEMORY,
where the proposal is a MEASUREMENT taken now: edit a nominal by hand
and the book still says the case passed, so '--fail' hides a real
difference. Ask the wish which FILES to look at; never what differs.

-------------------------------------------------------------------
OPTIONS
-------------------------------------------------------------------
    -o <file>           REQUIRED. Where the proposal is written.
    <n>                 a bare number: the most replacements a case
                        may show and still be proposed. 4 by default.
    --directory=<path>  one directory; the whole tree otherwise.
    --help              this text.

EXIT: OK where something was proposed, EMPTY where every selected case
agrees with its nominal, REFUSED where '-o' is missing or the
selection could not be made.

SET 'VUT_PROPOSE_TRACE=1' to watch the reading: one line on STDERR per
subject with the replacements found, the time, and how many positions
the engine was asked about. Stdout stays the proposal.

    [propose] mid1.sh.txt: 901 line(s), 1 replacement(s)  (0.001s, 1 asked)
    [propose] huge.sh.txt: 901 line(s), ABORTED past 5    (0.003s, 6 asked)
"""
import sys

from vut.services         import accept
from vut.services._exit   import E_ExitCode


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).

    THE FACE IS A SPELLING, NOT A SECOND ENGINE: the line count is
    read off the command line and handed to 'accept.main' as its
    'propose_n' -- a PARAMETER, never an option, since 'hwut.accept'
    does not propose and must not be asked to. Every other word
    travels untouched, so the wish, '--directory' and the targets mean
    here exactly what they mean there.
    """
    if argv is None:  argv  = sys.argv[1:]
    if write is None: write = print
    if "--help" in argv:
        write(__doc__.strip())
        return E_ExitCode.OK

    #  A BARE NUMBER IS THE LINE COUNT -- 'hwut.accept.propose -o p 8'.
    #  Anything else is the wish's, and is passed on as it stands.
    line_n, file_name, rest_list = "4", None, []
    skip_f = False
    for index, argument in enumerate(argv):
        if skip_f: skip_f = False; continue
        if   argument in ("-o", "--output"):
            if index + 1 >= len(argv):
                write("REFUSED: '%s' wants a file name" % argument)
                return E_ExitCode.REFUSED
            file_name = argv[index + 1]; skip_f = True
        elif argument.startswith("--output="):
            file_name = argument[len("--output="):]
        elif argument.isdigit() and line_n == "4" and not rest_list:
            line_n = argument
        else:
            rest_list.append(argument)

    #  REQUIRED, NOT DEFAULTED. A proposal is a file to READ and hand
    #  back; writing it to a terminal by default would invite the very
    #  redirection that mixes it with what belongs on stdout.
    if file_name is None:
        write("REFUSED: '-o <file>' is required -- the proposal is "
              "written there;")
        write("         what cannot be proposed is written to stdout.")
        return E_ExitCode.REFUSED

    try:
        with open(file_name, "w", encoding="utf-8") as handle:
            def put(text):
                """RETURN: None. One line into the proposal file."""
                handle.write(text + "\n")
            return accept.main(rest_list, write=write, put=put,
                               propose_n=int(line_n))
    except OSError as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded("hwut.accept.propose", main))
