==============================================================================
test_writing_support/rust -- THE PYTHON TEST SUPPORT, IN RUST
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to a Rust
test author here, as a module of ONE library crate, 'hwut' ('src/lib.rs'),
with the same behaviour and the same printed words:

    hwut::hwut_runner             hwut_runner.py           the front end of a test
                                                           application: --hwut-info,
                                                           one choice, --interactive
    hwut::deterministic_random    deterministic_random.py  a random stream that is
                                                           the same everywhere
    hwut::deterministic_timeline  deterministic_timeline.py  races drawn as strings
    hwut::space_iterator          space_iterator.py        every combination of a
                                                           parameter basis
    hwut::hwut_fsm                hwut_fsm.py              a state machine as the
                                                           test's model
    hwut::hwut_hocon              hwut_hocon.py            the HOCON subset, the
                                                           annotated tree
    hwut::hwut_vterm              hwut_vterm.py            a terminal's screen, read
                                                           by a test (libvterm)
    hwut::hwut_pytext             --                       text as Python prints it

Rust's standard library only -- no crate from outside, no cargo. The few C
functions the crate calls ('fork', 'dup2', 'waitpid', 'openpty', 'ioctl',
'setsid', 'poll', 'dlopen', 'dlsym', ...) are declared by hand in
'src/posix.rs' (Linux, glibc).

A Rust test starts:

    // @hwut {
    //     build   { framework = "make", executable = "%.exe" }
    //     choices = ["plain", "tricky"]
    //     interactive = true
    // }
    use hwut::hwut_runner::HwutRunner;
    fn plain()  { ... }
    fn tricky() { ... }
    fn main() {
        HwutRunner::new(std::env::args().collect(), "my title",
                        vec![("plain", plain), ("tricky", tricky)]).exit();
    }

and beside it a Makefile that builds 'test-x.exe' from 'test-x.rs' and the
crate. The build runs IN THE TEST DIRECTORY, where the Makefile stands
(services E-210); 'TEST/Makefile' is the example: per target, the crate is
compiled to 'build-<stem>/libhwut.rlib' and the test linked against it by
'rustc --extern hwut=...'. No two targets share a file, so hwut may build
the tests of one directory at once. The heads of the modules say how each is
used; where a Python README explains a module ('../python/README-hwut_fsm.txt',
'-hwut_hocon', '-hwut_vterm', '-hwut_runner'), it explains the Rust module too.

THE CLASSES ARE STRUCTS WITH 'impl', the names Python's:

    Python                          Rust
    m = Machine.from_string(text)   let mut m = Machine::from_string(text, true, "fsm")?;
    m.fire("grant", where=3)        m.fire("grant", 3);   m.fire("x", Where::Nowhere);
    stream.next_int(0, 9)           stream.next_int(0, 9)
    with Screen(24, 80) as s: ...   { let mut s = Screen::new(24, 80)?; ... }   -- dropped
    class Terminal(Screen)          struct Terminal: Deref<Target = Screen>
    class MyTrigger(Trigger)        struct MyTrigger { base: TriggerBase }; impl Trigger for MyTrigger
    space_iterator.do(basis)        space_iterator::r#do(&basis)   -- 'do' is a keyword


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.rs--masks.link
        ../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

So the Rust module is held against what the Python module was accepted for,
byte for byte -- as the Perl and the C modules are; 47 cases in six tests.
'hwut.good.link.show TEST/GOOD' lists them.

What Python prints of its own values -- True, None, a float's shortest form,
a str or bytes literal, a tuple, a list -- the Rust tests print by
'hwut_pytext', the trait 'PyRepr':

    float_repr(0.1)  '0.1'    1e-6 -> '1e-06'    bool_text(true)  'True'
    vec!["a"].py_repr()  "['a']"      PyTuple(&["a"]).py_repr()  "('a',)"
    None::<i32>.py_repr()  'None'     PyBytes(b"\x1b[A").py_repr()  "b'\\x1b[A'"

WHERE RUST DIFFERS FROM PYTHON, and how the port meets it:

    no exceptions          what Python raises is returned: 'Result<_, FsmError>'
                           (its message Python's text), 'Result<_, VtermError>'
                           ('kind()' is Python's exception name, the Display
                           its text), 'TimelineError::NotImplemented' for
                           NotImplementedError. Hocon's faults are a list (it
                           never raised)
    no default arguments   'where' is 'impl Into<Where>' -- an integer, a text
                           or 'Where::Nowhere'; 'start=None/"now"' is
                           'Option<&str>'; 'gauss(mu, sigma, lower, upper)' is
                           'gauss_within'
    one type per value     a Hocon scalar is a 'Value' -- Python's type is its
                           variant, 'type_name()' says 'int', 'str', ...; an
                           int is i128 (Python's are unbounded)
    no coroutines          a TASK is stepped ('Task::step' runs to the next
                           yield); the dispatcher is one, a closure
                           'FnMut() -> Step' is one. 'gather' steps tasks in
                           turn, in the order given -- asyncio.gather's
                           order -- and 'TaskHandle::cancel' abandons one
    shared, mutable        a trigger is 'Rc<RefCell<..>>' ('shared(..)'),
                           held by the test and the dispatcher; 'stop()' from
                           inside a firing goes through 'dispatcher.stopper()'
    no inheritance         a trigger holds a 'TriggerBase' and implements the
                           trait 'Trigger' (whose 'fire' refuses unless
                           overridden); 'Terminal' derefs to its 'Screen'
    no 'with'              'Machine::disallowed' and '::forbidding' take the
                           block as a closure handed the machine; a Screen is
                           freed, a Terminal's application killed, when it is
                           dropped
    identity ('id()')      a SelectionMarker remembers a candidate by the
                           address it REFERS to: candidates are references
                           ('&[&T]'), as Python's names are
    Python's float repr    Rust's '{}' is shortest too, but laid out otherwise
                           ('1e-6', '6.02e23'): 'float_repr' takes the digits
                           of '{:e}' and lays them out as Python, fixed for a
                           decimal point in (-4, 16]
    a choice ends          by returning; in --interactive mode each choice
                           runs in a child process ('fork'), so an 'exit' or a
                           panic in a choice ends that choice alone (status 1
                           for a panic, its message in the error sink)
    a hung parse           the fuzz runs each parse in a thread of its own and
                           waits 0.5 s for it (Python: SIGALRM)


3  WHAT IT WANTS
------------------------------------------------------------------------------
rustc (written with 1.97, edition 2021) and make -- offline; nothing else to
build. For 'hwut_vterm' alone: libvterm AT RUN TIME (Debian: apt install
libvterm0, as for Python). NO HEADER of libvterm is needed: the module
declares the library's few structures itself and loads it by 'dlopen' --
'libvterm.so.0', or the file HWUT_LIBVTERM names. Where the library is
missing, every choice of 'test-hwut_vterm.rs' but 'missing' says 'NOT
PROBED' -- and differs from its GOOD, as the Python test does. The two
applications 'test-hwut_vterm.rs' runs on its pseudo-terminal are the
Python test's own (they are the system under test), so 'python3' must stand
on the PATH.

    hwut::hwut_vterm::detection_text()

says whether the library is there.


4  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'script_runner.py'   a fixture for hwut's own tests of its faces, not given
                     to test authors.
'hwut_pype'          a face ('hwut.pype') and its scripts, not a library a
                     test links: a Rust test pipes through it as a Python
                     test does.
==============================================================================
