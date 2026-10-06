==============================================================================
HWUT 2.0  --  tolerant golden-master testing
==============================================================================

A test is a picture. The program prints what it does, in the terms of the
problem. A person looks at the picture and blesses it. From then on HWUT
judges every run against the blessed picture -- the GOOD file -- and where
a run may differ, the GOOD file says so, in the place where the expected
behaviour is written.

An assert can only fail on a hypothesis its author already had. A blessed
picture fails on everything.

    test application ----> stdout ----> compare <---- GOOD/<app>--<choice>.txt
    (any executable)                       |            the picture, plus the
                                           v            tolerances it grants
                                  [OK] or [FAIL] + the
                                  two texts side by side

The test application links nothing, imports nothing and registers nothing:
HWUT sees the process boundary only. 'hwut.accept' records a GOOD file. A
stream that does not end in '<hwut-end>' never completed and is not
accepted.


TRY IT                                                      (3 commands, ~1 min)
------------------------------------------------------------------------------
Python 3.10 or newer.

    git clone https://github.com/fschaef/hwut && cd hwut
    pip install bidict rapidfuzz regex typeguard
    cd vut/demo/python/TEST && ../../../bin/hwut --plain

Result:

    RESULTS: 6 ok, 0 fail

'demo.py' and 'protocol.sh' print six choices between them. Every run is
seeded by the clock or the scheduler, so the output differs from run to run,
and every choice passes anyway. The header at the top of each file is the
whole configuration; its comment says what the choice shows.

Optional: 'pip install prompt_toolkit' enables the keyed merge, 'hwut.accept'
on a terminal.


DESCRIBING BEHAVIOUR THE WAY IT HAPPENS
------------------------------------------------------------------------------
There is no assertion API. The program prints, and the printed text is the
specification: a GOOD file reads as a description of the behaviour, line by
line, and a reviewer reads it as such.

Output that varies is described as varying, in the GOOD file:

    "greeting: hello, world"        any of an 'eq_pattern' list of greetings
    "value:    19.93"               a number within a ratio of the GOOD's
    "open  ((df17)) input.txt"      a handle: any value, the same value
    "read  ((df17)) 17 lines"       wherever the handle appears
    "load  ((load: 71.3)) %"        a value that must obey a law: 0..100
    "twice ((twice: 34))"           a law over two values: twice == 2 * once

Blocks are described as blocks. A region opens with '##! <kind>' and closes
with '####', on both sides:

    ##! potpourri   the same lines, in any order
    ##! table       rows of columns; per column numeric tolerance or ignore;
                    rows keyed or in any order
    ##! point-cloud numeric vectors, each within a distance of a partner, or
                    each satisfying an expression
    ##! verbatim    byte-exact, no tolerance of any kind
    ##! ignore      the contents take no part

A line missing, extra or different still fails. The tolerance is a line
somebody wrote; HWUT infers none.


ORDER, TAMED: POTPOURRI
------------------------------------------------------------------------------
The 'race' choice of demo.py: three threads print as they finish. The order
is the scheduler's. The program opens an unordered block and closes it:

    start                           start
    ##! potpourri                   ##! potpourri
    worker A done: 3 jobs           worker C done: 2 jobs
    worker B done: 5 jobs           worker A done: 3 jobs
    worker C done: 2 jobs           worker B done: 5 jobs
    ####                            ####
    all joined                      all joined
    <hwut-end>                      <hwut-end>
    GOOD/demo.py--race.txt          one possible run

15 of 15 runs pass. The same output compared in order, without the markers,
failed 12 of 15 runs on a two-core machine. A worker that did not report, or
reported 4 jobs, fails the block: the order is free, the facts are not.

A potpourri says "any order". It cannot say "this before that", "exactly
once", "answered before shutdown". That is what 'pype' says.


ORDER, TAMED: PYPE, THE LAW AS STATES
------------------------------------------------------------------------------
'hwut.pype' is a filter language between the test application and the
comparison. A script has MODES -- the states the behaviour has -- and
HANDLERS: a line pattern, and what happens when it arrives (switch mode,
push, pop, run Python, print). The application reports as things happen;
the script holds the law and prints a verdict that does not depend on the
order the lines arrived in.

    my-test | ./law.pype            deterministic text, then compared

The 'clean' choice of 'protocol.sh' pipes five concurrent clients through
'protocol.pype'. Its law, abridged:

    SERVING   a request opens an exchange, a response closes it, 'shutdown'
              ends the service
    CLOSED    nothing may arrive any more

    SERVING/on: "request"  <id = int> => { ... open_db.setdefault(id, 0) }
    SERVING/on: "response" <id = int> => { ... open_db[id] += 1 }
    SERVING/on: "shutdown"            => goto CLOSED;
    CLOSED/on:  "request"  <id = int> => { breach_set.add(...) }
    CLOSED/on:  "response" <id = int> => { breach_set.add(...) }
    ANY/on:     <eof>                 => { print the verdicts, sorted }

Five clients, a different order in every run, one text:

    exchange 1: answered
    exchange 2: answered
    ...
    law: kept
    <hwut-end>

The same script on a stream that breaks the law (in 'demo/python/TEST'):

    printf '%s\n' "request 1" "response 1" "response 1" "response 9" \
        "request 2" shutdown "request 4" | ../../../bin/hwut.pype protocol.pype

    exchange 1: answered 2 times
    exchange 2: NOT answered
    BREACH: request 4 after shutdown
    BREACH: response 9 without a request before it
    law: BROKEN
    <hwut-end>

What the laws of this kind say -- precedence ('a response only after its
request'), exactly once, 'every request answered before shutdown', nothing
after the end, a wait that must not exceed a limit ('pype.time()') -- are
what temporal-logic monitors state as formulas. Here they are stated as the
states the protocol has, in its own words, and the verdict is a text that is
blessed like any other picture.

    hwut.pype --dry-run law.pype    syntax, inheritance, mandatory 'else'
    hwut.pype --trace law.pype      every input line against the handler it
                                    fired, on stderr, as 'file:line:'
    hwut.pype --example law.pype    a generated input for the script

Modes inherit ('is:'). Two handlers of one mode whose patterns could match
the same line are refused at parse time, so dispatch does not depend on
definition order. Where a script is part of the oracle, the manual says so:
'vut/test_writing_support/hwut_pype/MANUAL.txt'.

Where a tolerance can absorb a difference, a tolerance is stated. Where the
output can be understood, a pype states the understanding, and what remains
is compared byte-exact.


SEE A FAILURE                                    (run in the same directory)
------------------------------------------------------------------------------
    sed -i 's/1 2 3/1 2 4/' demo.py
    ../../../bin/hwut --plain               # [FAIL], exit status 1
    ../../../bin/hwut.run.diff demo.py plain
    sed -i 's/1 2 4/1 2 3/' demo.py

    =[ demo.py plain ]================================== round 1
    --[ LINE_SEQUENCE/LINE_SEQUENCE ]--
         1    1 | the first line
    S    2      | the second line: 1 2 [4]
    N         2 | the second line: 1 2 [3]
    --[ CLOSING-TOKEN ]--
         3    3 | <hwut-end>

'S' is the subject, what the program printed now; 'N' is the nominal, the
GOOD file. 'hwut.run.diff -y' puts them in two columns.


WHAT IS IN THE TREE
------------------------------------------------------------------------------
    vut/bin/        launchers, one per command: hwut.run, hwut.accept,
                    hwut.run.diff, hwut.report.details, hwut.cov.run, ...
                    (the default command: 'hwut' is 'hwut.run')
    vut/services/   the commands; README.txt lists every one
    vut/engine/     compare (tolerant comparison), orchestrator, bookkeeper,
                    coverage, display, operations, procsitter
    vut/test_writing_support/hwut_pype
                    pype, the filter language of the section above
    vut/demo/       the demos above
    vut/adm/        development tools; PHILOSOPHY.txt states the model

Where to read next:

    vut/engine/compare/MANUAL.txt       every tolerance and region, with
                                        examples
    vut/test_writing_support/hwut_pype/MANUAL.txt
    vut/adm/PHILOSOPHY.txt              what a test is, and when it is worth
                                        having
    vut/services/README.txt             every command, its words, its exit
                                        status

Commands used after the demo ('hwut.accept', 'hwut.run.diff', ...) are in
'vut/bin'; put it on PATH to call them by name:

    export PATH=$PWD/vut/bin:$PATH


STATUS
------------------------------------------------------------------------------
    2.0 is a complete rewrite of 1.0 and a spare-time project.
    Tests: 911 ok, 1 fail ('services/TEST/test-dev_podman.py refused'),
    measured by 'hwut' from the root at commit 70417c0
    (branch 26y10m4d-review-todo-and-done).
    Not there yet: a PyPI package or 'pyproject.toml'; a test suite in a
    language other than Python and shell. All test applications in the tree
    are Python or shell.
    Open work: vut/adm/WORK/TODO.txt.


LICENSE AND NO WARRANTY
------------------------------------------------------------------------------
MIT License. Copyright (c) 2026 fschaef. The full text is in the file
LICENSE. Its warranty clause, verbatim:

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.
