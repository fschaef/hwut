==============================================================================
support/test_writing/powershell -- THE PYTHON TEST SUPPORT, IN POWERSHELL 7
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to a
PowerShell test author here, with the same behaviour and the same printed
words -- one script module ('.psm1') per Python module, its classes named as
Python's:

    hwut_runner.psm1            hwut_runner.py           the front end of a test
      HwutRunner, Out-Py                                 application: --hwut-info,
                                                         one choice, --interactive
    deterministic_random.psm1   deterministic_random.py  a random stream that is
      DeterministicStream, SelectionMarker               the same everywhere
    deterministic_timeline.psm1 deterministic_timeline.py races drawn as strings
      Trigger, TriggerDispatcher, AsyncTask, CancelledError, NotImplementedError
    space_iterator.psm1         space_iterator.py        every combination of a
      SpaceIterator ([SpaceIterator]::Do = 'do')         parameter basis
    hwut_fsm.psm1               hwut_fsm.py              a state machine as the
      FsmMachine, FsmError, FsmPhase                     test's model
    hwut_hocon.psm1             hwut_hocon.py            the HOCON subset, the
      Hocon (::Parse, ::Cleandoc), SourceLine, ...       annotated tree
    hwut_vterm.psm1             hwut_vterm.py            a terminal's screen, read
      VtermScreen, VtermTerminal, VtermCell, ...         by a test (libvterm)
    hwut_vterm_native.cs        --                       its native edge (P/Invoke)
    hwut_pytext.psm1            --                       text as Python prints it
      PyText

A PowerShell test is 'test-<stem>.ps1', run by 'pwsh' as it stands -- the
'powershell' interpreter of 'hwut-root.conf'; nothing is built. It finds the
modules by 'using module' with a path relative to its OWN file, so it runs
from any working directory:

    # @hwut {
    #     choices     = ["plain", "tricky"]
    #     caps        { file_size_mb = 2097152 }      # see section 3
    #     interactive = true
    # }
    using module ../hwut_runner.psm1
    $plain  = { 'one line'; Out-Py 'another' }
    $tricky = { ... }
    [HwutRunner]::new(@{
        argv       = @($PSCommandPath) + $args          # as Python's 'sys.argv'
        title      = 'my title'
        choice_map = @{ plain = $plain; tricky = $tricky }   # '-' alone: choice-less
    }).Run()

A choice is a script block. What it puts on the pipeline is printed, line by
line, as it comes; 'Out-Py' prints directly -- the one way that works inside
a class method too (a method's pipeline output is not heard). The heads of
the modules say how each is used; where a Python README explains a module
('../python/README-hwut_fsm.txt', '-hwut_hocon', '-hwut_vterm',
'-hwut_runner'), it explains the PowerShell module too.


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.ps1--masks.link
        ../../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

47 cases in six tests, the same that hold the other ports.

What Python prints of its own values the tests print by 'PyText':

    [PyText]::FloatRepr(0.1)          '0.1'      [PyText]::BoolText($true)  'True'
    [PyText]::FloatRepr(-1500)        '-1500.0'  [PyText]::NoneOr($null)    'None'
    [PyText]::TupleRepr(@('a'), $true) "('a',)"  [PyText]::ListRepr(@(3,1)) '[3, 1]'
    [PyText]::StrRepr("it's")         "\"it's\"" [PyText]::BytesRepr($b)    "b'\x1b[A'"

WHERE POWERSHELL DIFFERS FROM PYTHON, and how the port meets it:

    names              Python's in PowerShell's casing: 'next_int' is
                       'NextInt', 'path_to' 'PathTo', 'line_list' 'LineList';
                       fields keep theirs ('breach_n', 'row_n', 'bold_f').
                       Python's properties 'state', 'forbidden' are methods.
    case               PowerShell compares without case ('-eq', '@{}'); the
                       modules compare by case where Python does (ordinal
                       dictionaries and sets, '-ceq', ordinal sort).
    keyword arguments  overloads, positional in Python's order -- 'Fire(event,
                       where)', 'PathTo(state, start, masked)', 'Press(key,
                       modifier_list, react_s)'; options of a constructor are
                       a hashtable ('FromString(text, @{ DFA = $false })').
    tuples             arrays ('Cursor()' is @(row, column)).
    'with'             '$m.Disallowed(e, s, w).Run({ ... })',
                       '$screen.Use({ param($screen) ... })': the block runs,
                       its output printed as it comes, the phase ends or the
                       screen closes whatever way it leaves.
    exceptions         thrown, PowerShell classes named as Python's --
                       FsmError, NotImplementedError, CancelledError,
                       LibraryMissing, IndexError, KeyError, TimeoutError,
                       RuntimeError -- 'Message' is Python's text. A choice
                       runs with $ErrorActionPreference 'Stop': an error ends
                       it, status 1, as an exception does in Python. HOCON
                       throws nothing, as in Python.
    asyncio            none in PowerShell. A task is a STEP FUNCTION (as in
                       the C port): '$d.Task()' is the run, each step one
                       firing then a yield; '[AsyncTask]::Gather(@(...))'
                       steps the tasks in turn in the order given, as
                       asyncio's ready queue; '.Cancel()' is told at the next
                       step, '.Await()' throws CancelledError. '$d.Run()' is
                       'asyncio.run(d.run())'. The GOODs' interleavings come
                       out line for line.
    ints and floats    [long] (BigInteger beyond) and [double]; the caller
                       says which Python printed. HOCON's ScalarNode carries
                       'py_type' and 'Repr()'. .NET's 'ToString("R")' digits
                       are Python's shortest round-trip ones; only the layout
                       ('1E+16', '1E-05', '-0') is rewritten.
    one process        --interactive runs every choice IN THIS PROCESS
                       (Python's sequential scheme): [Console]::Out and
                       [Console]::Error are pointed at the two sinks for the
                       choice's span ('Console.SetOut'); 'exit n' in a choice
                       ends that choice alone with status n (a nested
                       pipeline catches it). What a NATIVE child writes on an
                       inherited fd 1 or 2 is not redirected -- it lands in
                       the session's stray sink. 'parallel = "process"' runs
                       each choice in a child pwsh whose writers are the sinks.
    no ctypes          'hwut_vterm_native.cs' declares libvterm's and libc's
                       functions for P/Invoke, compiled by Add-Type on the
                       first Screen of a process; the library is loaded by
                       NativeLibrary (HWUT_LIBVTERM or the system's search)
                       and bound by a resolver. libvterm's callbacks only
                       QUEUE what they report; the module drains the queue
                       after each call -- no script runs in a native callback.
    no fork            the application is started by 'posix_spawnp', as
                       'java/hwut/Posix.java' does: a new session, the pty's
                       slave opened as fd 0 -- its controlling terminal -- and
                       dup'ed to 1, 2; every signal at its default. No helper
                       process.
    'fuzz' bound       each parse runs in a second runspace (the HOCON classes
                       carry [NoRunspaceAffinity()]), waited for 500 ms and
                       abandoned past it, where Python sets an interval timer.


3  WHAT IT WANTS
------------------------------------------------------------------------------
PowerShell 7.4 or later ('pwsh', .NET 8) -- nothing else for every module but
'hwut_vterm'. For 'hwut_vterm' alone:

    libvterm AT RUN TIME   Debian: apt install libvterm0, as for Python --
                           'libvterm.so.0', or the file HWUT_LIBVTERM names.
                           No header: the cell's layout is measured.
    glibc                  the libc numbers (O_CLOEXEC, TIOCSWINSZ,
                           POSIX_SPAWN_SETSID) are Linux/glibc's; 'cwd' wants
                           'posix_spawn_file_actions_addchdir_np' (2.29).
    python3                on the PATH, for 'TEST/test-hwut_vterm.ps1' alone:
                           the two applications it runs on its pseudo-terminal
                           are the Python test's own -- the system under test.

    pwsh -NoProfile -c 'using module ./hwut_vterm.psm1; Get-VtermDetection'
                           says whether the library is there

THE FILE CAP. .NET's W^X double mapping sizes a memory file to 2 TiB when the
runtime starts ('ftruncate' of a memfd; sparse, never written). Under hwut's
default cap of 10 MB per file (RLIMIT_FSIZE) pwsh dies of SIGXFSZ before it
reads the script -- under any cap below 2 TiB. Every test here therefore
states 'caps { file_size_mb = 2097152 }'; 'DOTNET_EnableWriteXorExecute=0' in
the caller's environment avoids the mapping instead, but a test cannot set
its own interpreter's environment.

THE INTERPRETER LINE. hwut calls 'pwsh <test> <choice>': a user's profile
script runs first (and may print), and pwsh sends start-up telemetry unless
POWERSHELL_TELEMETRY_OPTOUT=1 is set. Neither can be switched off from inside
the script; see RATIONALE PS-1.


4  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'script_runner.py'   a fixture for hwut's own tests of its faces, not given
                     to test authors.
'hwut.pype'          a face ('services/lib/pype') and its scripts, not a library a
                     test links: a PowerShell test pipes through it as a
                     Python test does.
==============================================================================
