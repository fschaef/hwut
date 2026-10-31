==============================================================================
test_writing_support/perl -- THE PYTHON TEST SUPPORT, IN PERL
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to a Perl
test author here, under the same name and with the same behaviour:

    Hwut::Runner                hwut_runner.py           the front end of a test
                                                         application: --hwut-info,
                                                         one choice, --interactive
    Hwut::DeterministicStream   deterministic_random.py  a random stream that is
    Hwut::SelectionMarker                                the same everywhere
    Hwut::TriggerDispatcher     deterministic_timeline.py  races drawn as strings
    Hwut::Trigger, Hwut::Task
    Hwut::SpaceIterator         space_iterator.py        every combination of a
                                                         parameter basis
    Hwut::Fsm                   hwut_fsm.py              a state machine as the
                                                         test's model
    Hwut::Hocon                 hwut_hocon.py            the HOCON subset, the
                                                         annotated tree
    Hwut::Vterm                 hwut_vterm.py            a terminal's screen, read
                                                         by a test (libvterm)
    Hwut::PyText                --                       text as Python prints it

A Perl test starts:

    #! /usr/bin/env perl
    # @hwut { choices = ["plain", "tricky"] }
    use FindBin;  use lib "$FindBin::Bin/<path to test_writing_support/perl>";
    use Hwut::Runner;
    Hwut::Runner->new(argv => \@ARGV, title => "...",
                      choice_map => { plain => \&plain, tricky => \&tricky })->run;

The modules' own heads say how each is used; where a Python README
explains a module ('../python/README-hwut_fsm.txt', '-hwut_hocon',
'-hwut_vterm', '-hwut_runner'), it explains the Perl module too.


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.pl--masks.link
        ../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

So the Perl module is held against what the Python module was accepted for,
byte for byte, and a change of either that the other does not follow is a
failure in one of the two directories. 'hwut.good.link.show TEST/GOOD' lists
them; 47 cases in six tests.

What Python prints of its own values -- True, None, a tuple, a float's
shortest form, a bytes literal -- the Perl tests print by 'Hwut::PyText', so
the text is the same:

    float_repr(0.1) '0.1'    tuple_repr(['a'], 1) "('a',)"    bool_text(1) 'True'
    list_repr([3, 1]) '[3, 1]'    str_repr("it's") "\"it's\""    bytes_repr("\e[A") "b'\\x1b[A'"

WHERE PERL DIFFERS FROM PYTHON, and how the port meets it:

    one scalar, two types    a value carries Python's kind where it matters:
                             a Hocon scalar's 'kind' is 'int', 'float',
                             'str', 'bool' or 'null'
    no coroutines            a TASK is a step closure: one 'step' runs to the
                             next yield. 'Hwut::Task::gather' steps tasks in
                             turn, in the order given -- asyncio.gather's
                             order -- and 'cancel' abandons one, so its end
                             is never run
    'exit' in a choice       ends the choice, not the interactive session,
                             as SystemExit does in Python ('Hwut::Runner'
                             installs the override when it is loaded)
    identity in a marker     Python remembers a candidate by 'id()'; a Perl
                             array of strings holds copies, so a candidate is
                             remembered by its reference where it is one and
                             by its value else -- two equal strings are one
    a context manager        'disallowed' and 'forbidding' take the block:
                             $m->disallowed($event, $state, $where, sub {...})
    'where' of a breach      a number names a line ('line 3'); any other text
                             stands as written
    a raised exception       a fault dies with an object: Hwut::FsmError
                             ('message'), Hwut::Vterm::Error ('kind' is
                             Python's exception name, 'message' its text)


3  WHAT IT WANTS
------------------------------------------------------------------------------
Perl 5.26 or later, its core modules -- and, for 'Hwut::Vterm' alone:

    libvterm         Debian: apt install libvterm0 (as for Python)
    FFI::Platypus    Debian: apt install libffi-platypus-perl
                     CPAN:   cpanm FFI::Platypus

Perl's core has no binding to a C library, as Python's has 'ctypes'.
FFI::Platypus also provides the pseudo-terminal ('openpty' in libc), so no
further module is needed. Where libvterm is missing, every choice of
'test-hwut_vterm.pl' but 'missing' says 'NOT PROBED' -- and differs from its
GOOD, as the Python test does.

    perl -I. -MHwut::Vterm -e 'print Hwut::Vterm::detection_text(), "\n"'

asks by hand whether the library is there.


4  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'script_runner.py'   a fixture for hwut's own tests of its faces, not given
                     to test authors.
'hwut_pype'          a face ('hwut.pype') and its scripts, not a library a
                     test imports: a Perl test pipes through it as a Python
                     test does.
==============================================================================
