==============================================================================
test_writing_support/java -- THE PYTHON TEST SUPPORT, IN JAVA
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to a Java
test author here, package 'hwut', with the same behaviour and the same
printed words:

    hwut/HwutRunner.java          hwut_runner.py           the front end of a
                                                           test application:
                                                           --hwut-info, one
                                                           choice, --interactive
    hwut/DeterministicStream.java deterministic_random.py  a random stream that
    hwut/SelectionMarker.java                              is the same everywhere
    hwut/Trigger.java             deterministic_timeline.py races drawn as
    hwut/TriggerDispatcher.java                            strings
    hwut/Async.java               (asyncio)                the coroutines the
                                                           timeline runs in
    hwut/SpaceIterator.java       space_iterator.py        every combination of
                                                           a parameter basis
    hwut/FsmMachine.java          hwut_fsm.py              a state machine as
    hwut/FsmError.java                                     the test's model
    hwut/Hocon.java               hwut_hocon.py            the HOCON subset, the
                                                           annotated tree
    hwut/Vterm.java               hwut_vterm.py            a terminal's screen,
    hwut/VtermScreen.java                                  read by a test
    hwut/VtermTerminal.java                                (libvterm)
    hwut/VtermCell.java, VtermEvent.java, LibraryMissing.java
    hwut/Posix.java               (os.openpty, Popen)      the pseudo-terminal
    hwut/PyText.java              --                       text as Python
                                                           prints it

A test compiles the classes it uses with its own source ('javac -sourcepath
..'): there is no jar to install. JDK 21 and nothing beyond it.

A Java test starts:

    /* @hwut {
     *     build   { framework = "make", executable = "%.exe" }
     *     choices = ["plain", "tricky"]
     *     interactive = true
     * } */
    import hwut.HwutRunner;
    final class TestX {
        static void plain()  { ... }
        static void tricky() { ... }
        public static void main(String[] args) {
            new HwutRunner(args, "my title")
                .choice("plain",  TestX::plain)
                .choice("tricky", TestX::tricky)
                .run();
        }
    }

in 'test-x.java' -- the class is not public, so the file's name need be no
class name -- and beside it the Makefile of 'TEST/': 'make test-x.exe'
compiles 'test-x.java' and the support classes it uses into
'test-x.classes/' and writes 'test-x.exe', a launcher that runs
'java -cp test-x.classes TestX' (the class name is the file's stem in
CamelCase). The build runs IN THE TEST DIRECTORY, where the Makefile stands
(services E-210); every target builds into its own directory, so hwut may
build several at once. Where a Python README explains a module
('../python/README-hwut_fsm.txt', '-hwut_hocon', '-hwut_vterm',
'-hwut_runner'), it explains the Java class too; the head of each '.java'
says how it is used.

THE NAMES ARE JAVA'S, THE PYTHON NAMES RECOGNISABLE: a class keeps its name
(the FSM's 'Machine' is 'FsmMachine', as in C), a method is camelCase:

    Python                              Java
    m = Machine.from_string(text)       FsmMachine m = FsmMachine.fromString(text);
    m.fire("grant", where=3)            m.fire("grant", 3);
    m.path_to("busy", masked=False)     m.pathTo("busy", null, false);
    with m.disallowed("x", state="s"):  try (FsmMachine.Phase p = m.disallowed("x", "s", null)) { ... }
    stream.next_int(0, 9)               stream.nextInt(0, 9);
    parse(lines, "f.hocon")             Hocon.Result r = Hocon.parse(lines, "f.hocon");
    with Screen(24, 80) as s: ...       try (VtermScreen s = new VtermScreen(24, 80)) { ... }
    terminal.wait()                     terminal.waitFor()   ('wait' is Object's)
    asyncio.run(d.run())                Async.run(d::run);
    await asyncio.sleep(0)              Async.sleep0();


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.java--masks.link
        ../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

So the Java classes are held against what the Python modules were accepted
for, byte for byte -- as the C and Perl ports are; 47 cases in six tests.
'hwut.good.link.show TEST/GOOD' lists them.

What Python prints of its own values -- True, None, a float's shortest form,
a str or bytes literal, a list, a tuple -- the Java tests print by 'PyText':

    PyText.floatRepr(0.1)         "0.1"        PyText.bool(true)          "True"
    PyText.strRepr("it's")        "\"it's\""   PyText.bytesRepr(b)        "b'\\x1b[A'"
    PyText.repr(List.of(3, 1))    "[3, 1]"     PyText.tupleRepr(list)     "('a',)"
    PyText.repr(null)             "None"       PyText.ljust(text, 6)      '%-6s', by characters

WHERE JAVA DIFFERS FROM PYTHON, and how the port meets it:

    keyword arguments      overloads: 'fire(event)', 'fire(event, where)';
                           an argument Python defaults is given, or the
                           shorter overload taken
    'with'                 AutoCloseable and try-with-resources: VtermScreen,
                           VtermTerminal, FsmMachine.Phase
    exceptions             Java's where one fits, Python's text as the
                           message: FsmError (an IllegalArgumentException),
                           LibraryMissing, IndexOutOfBoundsException for
                           IndexError, NoSuchElementException for KeyError
                           (its message the name quoted, as KeyError says it),
                           IllegalStateException for RuntimeError,
                           VtermTerminal.TimeoutError, and
                           UnsupportedOperationException for the base
                           'Trigger.fire's NotImplementedError
    no coroutines          'Async': a task is a thread that runs only while it
                           holds the baton -- one task at a time, handed on in
                           asyncio's order ('sleep0', 'await_', 'gather',
                           'createTask', 'cancel'; CancelledError at the next
                           yield). 'Trigger.fire' and 'TriggerDispatcher.run'
                           are such coroutines
    values of Python       an integer is Long (BigInteger beyond 64 bits), a
                           float Double, a tuple a List printed by
                           'PyText.tupleRepr', a colour 'VtermCell.Rgb', a
                           place 'VtermScreen.Place' -- each printing as the
                           Python value prints
    'where' of a breach    an Object: an Integer names a line ('line 3'), any
                           other value stands as its text, null no place
    Double.toString        is not Python's 'repr' ('1.0E-5', '4.9E-324'
                           against '1e-05', '5e-324'): 'PyText.floatRepr' lays
                           out the shortest digits as Python does
    the environment        Java cannot set its own: the test 'missing' names
                           the absent library by 'Vterm.resetLibrary(file)',
                           the test 'unnoticed' hands COLUMNS=300 to the
                           application's environment ('run(argv, env, ...)')
    no fork                in --interactive mode every choice runs in a JVM of
                           its own, started with this one's command line and
                           '--hwut-child <choice>': an exit or a crash ends
                           that choice alone; 'parallel(true)' runs them at
                           once
    no pseudo-terminal     'Posix' calls libc through the Foreign Function &
                           Memory API: posix_openpt for the pair, posix_spawnp
                           with POSIX_SPAWN_SETSID for the application, which
                           opens the slave first and so has it as its
                           controlling terminal
    text encoding          'HwutRunner' sets System.out and System.err to
                           UTF-8, whatever the locale -- Python's GOOD files
                           are UTF-8


3  WHAT IT WANTS
------------------------------------------------------------------------------
JDK 21 (javac, java), make, a POSIX shell -- and, for the vterm classes
alone, Linux with glibc (posix_spawn's SETSID; the libc constants in
'Posix.java' are Linux's) and libvterm AT RUN TIME (Debian: apt install
libvterm0, as for Python). NO HEADER of libvterm and NO JAR is needed: the
library is loaded through java.lang.foreign -- 'libvterm.so.0', or the file
HWUT_LIBVTERM names -- and its structures are declared in 'Vterm.java'.

java.lang.foreign is a PREVIEW API in JDK 21 (final in 22): every class is
compiled with '--enable-preview --release 21' and run with
'--enable-preview --enable-native-access=ALL-UNNAMED'; the Makefile and its
launchers do both. The classes are written against JDK 21's preview: JDK 22
made the API final and renamed two methods used here ('allocateUtf8String'
is 'allocateFrom', 'getUtf8String' is 'getString'), and its javac takes
'--enable-preview' only with its own release -- a later JDK wants those two
names changed and the flag dropped (Makefile: JAVAC_FLAGS, JAVA_FLAGS).

Where the library is missing, every choice of 'test-hwut_vterm.java' but
'missing' says 'NOT PROBED' -- and differs from its GOOD, as the Python test
does. The two applications 'test-hwut_vterm.java' runs on its
pseudo-terminal are the Python test's own (they are the system under test),
so 'python3' must stand on the PATH.

    java --enable-preview -cp test-hwut_vterm.classes hwut.Vterm

says whether the library is there ('Vterm.detectionText()').

hwut-root.conf's 'java' entry names the interpreter 'java': a test WITHOUT a
'build' runs as 'java test-x.java', the single-file source launcher, which on
JDK 21 sees no class beside the file -- 'package hwut does not exist'. So a
test of these classes states 'build { framework = "make", executable =
"%.exe" }', and hwut builds it, as a C test.


4  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'script_runner.py'   a fixture for hwut's own tests of its faces, not given
                     to test authors.
'hwut_pype'          a face ('hwut.pype') and its scripts, not a library a
                     test links: a Java test pipes through it as a Python
                     test does.
==============================================================================
