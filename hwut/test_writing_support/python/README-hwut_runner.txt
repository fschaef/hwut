==============================================================================
hwut_runner -- FRONT END OF A HWUT TEST APPLICATION
==============================================================================

A test application constructs one HwutRunner and calls '.run()'.

    from hwut_runner import HwutRunner

    HwutRunner(sys.argv, "My Title;",
               { "first": test_first, "second": test_second },
               parallel=None).run()

'choice_map' maps choice name -> test function; a function may be a plain
function or a coroutine function. Key 'None' names the single choice-less
test; then it is the only entry.

'parallel' selects the execution scheme of interactive mode:

    None        sequential, in-process           (default)
    "process"   one forked child per choice; choices run concurrently;
                POSIX only


1  COMMAND LINE -- THE TWO FRAMEWORK MODES
______________________________________________________________________________

    app --hwut-info     print the info block; exit 0.
    app <choice>        NORMAL MODE. Run one choice. Test output flows on
                        the process's stdout and stderr. Exit status is the
                        process's exit status.
    app --interactive   INTERACTIVE MODE. Section 2.
    app                 manual mode: list choices with indices, read one
                        index from stdin, run it, exit.
    app -h | --hi | --sos | --wtf     same as '--hwut-info'.

Info block:

    <title>;
    CHOICES: <name>, <name>, ...;         (absent for a choice-less app)
    HAPPY: <pattern>;                     (zero or more)
    SAME;                                 (if 'same_f')
    INTERACTIVE;                          (always)

'INTERACTIVE;' announces: the app accepts '--interactive'. Every app with a
HwutRunner front end announces it.


2  INTERACTIVE MODE
______________________________________________________________________________

Channels of a session:

    stdin               DOWN   commands from the framework
    original stdout     UP     protocol replies
    per-choice sinks           test output: two files named per 'run'

On entry the original stdout is duplicated onto a private control
descriptor. Descriptors 1 and 2 are then pointed at a session stray sink
(a temp file). Output written outside a running choice lands in the stray
sink. Output written before '.run()' precedes the session; the framework's
UP reader skips lines that match no UP message.

DOWN grammar, one command per line, fields separated by blanks:

    run <choice> <sink-out> <sink-err>
    info
    quit | q | exit

'<choice>' is a choice name, a decimal index into the sorted choice list,
or '-' for the choice-less test. '<sink-out>' and '<sink-err>' are file
paths; the app opens them (created, truncated) and points descriptor 1 at
the first, descriptor 2 at the second, for the duration of the choice.
Processes spawned by the choice inherit these descriptors.

UP grammar, one message per line:

    done <choice> <status>       the choice ran; see BARRIER
    fail <choice> <reason>       the command did not execute
                                 reasons: unknown-choice, bad-command
    info: <line>                 reply lines to 'info', one per info-block
                                 line, terminated by 'done - 0'
    bye                          session end; every child is reaped

End of session: 'quit' or end of stdin. Both drain outstanding children,
then emit 'bye'.

<status> of 'done':

    0        the test function ran and returned
    n != 0   the test function raised SystemExit(n), or raised an
             exception (=> 1; traceback in the error sink), or -- in
             "process" mode -- the child exited with n; a negative n is
             a terminating signal number.


3  EXECUTION SCHEMES
______________________________________________________________________________

SEQUENTIAL ('parallel=None'). One choice at a time, in the app's own
process. Per choice: streams flushed, descriptors 1 and 2 saved, pointed
at the sinks, restored afterwards. 'done' follows immediately.

PROCESS ('parallel="process"'). One 'fork()' per 'run' command; the child
performs the sequential procedure and exits with the status; the parent
keeps reading DOWN commands. A reaper thread reports 'done' upon each
child's end. 'done' messages therefore arrive in COMPLETION order, not in
submission order; the framework matches by the choice token. POSIX only.


4  BARRIER -- WHAT 'done' GUARANTEES
______________________________________________________________________________

At the instant 'done <choice> <status>' is readable:

    - every write of the app's own process (in "process" mode: of the
      child) to the sinks is flushed and the sinks are closed;
    - descriptors 1 and 2 of the app are restored.

Writes of processes SPAWNED BY THE CHOICE that outlive the choice are the
choice's concern. A choice that spawns uses the procsitter, which contains
its process groups; a choice that spawns by other means owns its own
containment.


5  RESET DISCIPLINE (SEQUENTIAL MODE)
______________________________________________________________________________

In sequential mode consecutive choices share the process. State a choice
alters and a later choice reads -- working directory, environment,
module-level caches, RNG state -- is the test author's concern. The
byte-exactness check: run the suite once in normal mode, once
interactively, diff the sinks. In "process" mode each choice starts from
the state at session entry.


6  FURTHER CONTENT OF THE MODULE
______________________________________________________________________________

make_script_application()   generate a temporary executable script
ScriptApplication           context manager around it; deletes on exit
