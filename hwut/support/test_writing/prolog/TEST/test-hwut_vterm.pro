% @hwut {
%     title      = "A terminal's screen read by a test: libvterm through the C port, a foreign library."
%     choices {
%         attributes { features = ["prolog-vterm"] }
%         colours    { features = ["prolog-vterm"] }
%         events     { features = ["prolog-vterm"] }
%         keys       { features = ["prolog-vterm"] }
%         missing    { features = ["prolog-vterm"] }
%         regions    { features = ["prolog-vterm"] }
%         screen     { features = ["prolog-vterm"] }
%         text       { features = ["prolog-vterm"] }
%         unnoticed  { features = ["prolog-vterm"] }
%     }
%     interactive = true
% }
%
% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%______________________________________________________________________________
%
% PURPOSE: The Prolog port of 'python/TEST/test-hwut_vterm.py', choice for
%          choice, held against its GOOD files by '.link'. WANTS libvterm --
%          reached through the C port, by the foreign library
%          'hwut_vterm4pl.so', which 'hwut_vterm.pro' builds on first load
%          (cc, make). The two APPLICATIONS a terminal runs here are the
%          Python test's, unchanged -- verbatim, in quasi-quotations: they are
%          the system under test, and what they print is in the shared GOOD
%          files.
%______________________________________________________________________________
:- encoding(utf8).
:- use_module('../hwut_runner.pro').
:- use_module('../hwut_pytext.pro').
:- use_module('../hwut_vterm.pro').
:- use_module(library(strings)).
:- initialization(main, main).

esc("\e").

%   shown(+S)
%   RETURN: every row that holds something, framed, then the cursor.
shown(S) :-
    vterm_line_list(S, Lines),
    forall(( nth0(Row, Lines, Line), Line \== "" ), format("    ~d |~w|~n", [Row, Line])),
    vterm_cursor(S, R, C),
    format("    cursor (~d, ~d)~n", [R, C]).

%   probe(:Goal)
%   RETURN: Goal, run on a library that is there; one line where it is
%           not.
:- meta_predicate probe(0).
probe(Goal) :-
    catch(Goal, error(vterm_error('LibraryMissing', Message), _),
          format("NOT PROBED: ~w~n", [Message])).

with_screen(R, C, S, Goal) :- setup_call_cleanup(vterm_screen_new(R, C, S), Goal, vterm_close(S)).
with_terminal(R, C, O, T, Goal) :- setup_call_cleanup(vterm_terminal_new(R, C, O, T), Goal, vterm_close(T)).

run_text :-
    with_screen(4, 12, S1,
        (   format("-- plain, then carriage return and line feed~n"),
            vterm_feed(S1, bytes(`hello\r\nworld`)),
            shown(S1) )),
    with_screen(4, 12, S2,
        (   format("-- UTF-8: two bytes, one cell; a wide character, two~n"),
            vterm_feed(S2, "ä日x"),
            shown(S2),
            forall(between(0, 3, Column),
                   (   vterm_cell(S2, 0, Column, Cell),
                       vterm_cell_text(Cell, Text), vterm_cell_width(Cell, Width),
                       py_repr(Text, R), py_ljust(R, 6, RT),
                       format("    column ~d: ~w width ~d~n", [Column, RT, Width]) )) )),
    with_screen(3, 5, S3,
        (   format("-- seven characters on five columns: the line wraps~n"),
            vterm_feed(S3, bytes(`abcdefg`)),
            shown(S3) )),
    with_screen(2, 4, S4,
        (   format("-- a str is sent as UTF-8; the bytes taken are counted~n"),
            vterm_feed(S4, "aä", Taken),
            format("    taken: ~d~n", [Taken]),
            format("-- a place off the screen~n"),
            catch(vterm_cell(S4, 2, 0, _), error(vterm_error('IndexError', M), _),
                  format("    IndexError: ~w~n", [M])) )).

run_screen :-
    esc(E),
    with_screen(5, 20, S,
        (   format("-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'~n"),
            vterm_feed(S, bytes(`first line\r\nsecond line\r\nthird line`)),
            format(string(Go), "~w[2;4HX", [E]), vterm_feed(S, Go),
            shown(S),
            format("-- erase to the end of that line~n"),
            format(string(K), "~w[K", [E]), vterm_feed(S, K),
            shown(S),
            format("-- clear the screen, home, one word~n"),
            format(string(C), "~w[2J~w[Hclean", [E, E]), vterm_feed(S, C),
            shown(S) )).

run_attributes :-
    esc(E),
    with_screen(3, 20, S,
        (   forall(vterm_attribute_sgr(Name, Code),
                   (   sub_atom(Name, 0, 1, _, Initial),
                       format(string(F), "~w[~wm~w~w[0m", [E, Code, Initial, E]),
                       vterm_feed(S, F) )),
            format("-- one cell per attribute, set by its own code~n"),
            findall(N, vterm_attribute_sgr(N, _), Names),
            forall(nth0(Column, Names, Name),
                   (   vterm_cell(S, 0, Column, Cell),
                       %  'conceal' IS NOT KNOWN TO EVERY LIBRARY: said, not pinned.
                       (   Name == conceal -> Said = "conceal, or (none) on libvterm 0.1"
                       ;   said(Cell, Said)
                       ),
                       vterm_cell_text(Cell, T), py_repr(T, R),
                       format("    ~w  ~w~n", [R, Said]) )),
            format("-- bold, underline and reverse at once; then reset~n"),
            format(string(F2), "\r\n~w[1;4;7mA~w[0mB", [E, E]), vterm_feed(S, F2),
            forall(member(Column, [0, 1]),
                   (   vterm_cell(S, 1, Column, Cell),
                       said(Cell, Said), vterm_cell_text(Cell, T), py_repr(T, R),
                       format("    ~w  ~w~n", [R, Said]) )),
            format("-- double underline (SGR 21) is underlined~n"),
            format(string(F3), "~w[21mD", [E]), vterm_feed(S, F3),
            vterm_cell(S, 1, 2, D), vterm_cell_attribute_text(D, DT),
            format("    'D'  ~w~n", [DT]) )).

said(Cell, Said) :-
    vterm_cell_attribute_text(Cell, T), ( T == "" -> Said = "(none)" ; Said = T ).

run_colours :-
    esc(E),
    with_screen(2, 20, S,
        (   format(string(F), "d~w[31mr~w[0m~w[38;5;196mp~w[0m~w[38;2;10;20;30mt~w[0m", [E, E, E, E, E, E]),
            vterm_feed(S, F),
            format(string(B), "~w[48;2;1;2;3mb~w[0m", [E, E]), vterm_feed(S, B),
            forall(nth0(Column, ["default", "indexed 31", "palette 196", "direct 10;20;30",
                                 "background 1;2;3"], What),
                   (   vterm_cell(S, 0, Column, Cell),
                       vterm_cell_foreground(Cell, Fg), vterm_cell_background(Cell, Bg),
                       %  THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE:
                       %  that one is a colour and mostly red is the claim.
                       (   What == "indexed 31"
                       ->  Fg = tuple([Red, Green, Blue]),
                           py_bool(Red > 2 * max(Green, Blue), M),
                           format(string(Said), "fg mostly red: ~w", [M])
                       ;   py_repr(Fg, FT), py_repr(Bg, BT),
                           format(string(Said), "fg ~w  bg ~w", [FT, BT])
                       ),
                       vterm_cell_text(Cell, T), py_repr(T, R), py_ljust(What, 18, W),
                       format("    ~w ~w  ~w~n", [W, R, Said]) )) )).

%  THE APPLICATION UNDER OBSERVATION: it says what it sees, asks the terminal
%  where the cursor is, then names every key until 'q'. (The Python test's
%  SEEING_APP, verbatim.)
seeing_app({|string(_)||
import os, sys, tty, termios
print("streams are terminals: %s %s %s"
      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))
try:    os.close(os.open("/dev/tty", os.O_RDWR)); print("controlling terminal: yes")
except OSError: print("controlling terminal: no")
print("size: %d columns, %d rows" % tuple(os.get_terminal_size()))
print("TERM=%s COLUMNS=%s" % (os.environ.get("TERM"), os.environ.get("COLUMNS")))
old = termios.tcgetattr(0); tty.setraw(0)
sys.stdout.write("\x1b[6;9H\x1b[6n"); sys.stdout.flush()
reply = b""
while not reply.endswith(b"R"): reply += os.read(0, 1)
sys.stdout.write("\r\x1b[7;1Hthe terminal answered: %r" % reply); sys.stdout.flush()
while True:
    key = os.read(0, 32)
    sys.stdout.write("\x1b[9;1H\x1b[Kread: %r" % key); sys.stdout.flush()
    if key == b"q": break
termios.tcsetattr(0, termios.TCSADRAIN, old)
print("\r\nleaving"); sys.exit(3)
|}).

%  AN APPLICATION WITH A HEAD, A BODY AND A FOOT: 'n' counts in the body, 'f'
%  rewrites the foot, 'r' redraws everything unchanged, 'q' leaves. (The
%  Python test's DRAWING_APP, verbatim.)
drawing_app({|string(_)||
import os, sys, tty, termios
old = termios.tcgetattr(0); tty.setraw(0)
count, foot = 0, "q=quit"
def draw():
    out = "\x1b[2J\x1b[1;1H\x1b[7m the head \x1b[0m"
    out += "\x1b[3;1Hcount: %d\x1b[4;1H(press n)" % count
    out += "\x1b[8;1H%s" % foot
    sys.stdout.write(out); sys.stdout.flush()
draw()
while True:
    key = os.read(0, 1)
    if   key == b"n": count += 1
    elif key == b"f": foot = "q=quit  f=pressed"
    elif key == b"q": break
    draw()
termios.tcsetattr(0, termios.TCSADRAIN, old)
|}).

python_argv(App, ["python3", "-c", Source]) :- call(App, Text), string_concat("\n", Text, Source).

run_unnoticed :-
    setenv('COLUMNS', '300'),
    python_argv(seeing_app, Argv),
    with_terminal(10, 44, [], T,
        (   py_bool(vterm_run(T, Argv), Running),
            format("-- still running after its first screen: ~w~n", [Running]),
            shown(T),
            ignore(vterm_send(T, "q")),
            vterm_wait(T, Status),
            format("-- after 'q': exit status ~w~n", [Status]),
            shown(T) )).

%   THE KEY PRESSED NOW, which the change closure prints -- Python's closure
%   reads the variable 'pressed'; here a global variable is that variable.
pressed_said(_Name, [Line|_]) :-
    nb_getval(pressed, P), py_ljust(P, 22, PT), format("    ~w ~w~n", [PT, Line]).

press_said(T, Key, Modifiers) :-
    append(Modifiers, [Key], Words), atomic_list_concat(Words, ' ', P),
    nb_setval(pressed, P),
    ignore(vterm_press(T, Key, Modifiers)).

run_keys :-
    python_argv(seeing_app, Argv),
    with_terminal(10, 44, [], T,
        (   vterm_region(T, read, [row(8)]),
            vterm_on_change(T, pressed_said),
            nb_setval(pressed, "(start)"),
            ignore(vterm_run(T, Argv)),
            forall(member(Key-Modifiers, [up-[], enter-[], tab-[], escape-[], f5-[], delete-[],
                                          c-[ctrl], x-[alt], up-[shift]]),
                   press_said(T, Key, Modifiers)),
            nb_setval(pressed, "send 'ä'"), ignore(vterm_send(T, "ä")),
            nb_setval(pressed, "send 'q'"), ignore(vterm_send(T, "q")),
            vterm_wait(T, _) )).

region_said(Name, Lines) :-
    py_ljust(Name, 5, N), py_repr(Lines, L), format("    changed  ~w ~w~n", [N, L]).

run_regions :-
    %  A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must be
    %  ONE report on a loaded machine too.
    python_argv(drawing_app, Argv),
    with_terminal(8, 30, [settle_s(0.3)], T,
        (   vterm_region(T, head, [row(0)]),
            vterm_region(T, body, [row(2), row_n(2)]),
            vterm_region(T, foot, [row(-1)]),
            vterm_on_change(T, region_said),
            forall(member(Said-Act, ["run"-vterm_run(T, Argv),
                                     "'n'"-vterm_send(T, "n"),
                                     "'n'"-vterm_send(T, "n"),
                                     "'r': a redraw, nothing new"-vterm_send(T, "r"),
                                     "'f'"-vterm_send(T, "f"),
                                     "'nnn', typed at once"-vterm_send(T, "nnn"),
                                     "'q'"-vterm_send(T, "q")]),
                   (   format("-- ~w~n", [Said]), ignore(Act) )),
            vterm_wait(T, Status), vterm_region_text(T, body, Body), py_repr(Body, BT),
            format("-- exit status ~w; a region asked by name: ~w~n", [Status, BT]),
            catch(vterm_region_text(T, nosuch, _), error(vterm_error('KeyError', M), _),
                  format("-- no such region: KeyError ~w~n", [M])) )).

event_said(Event) :- vterm_event_text(Event, T), format("    ~w~n", [T]).

run_events :-
    esc(E),
    with_terminal(4, 20, [], T,
        (   vterm_on_event(T, event_said),
            format(string(Hidden), "~w[4;1H~w[?25l", [E, E]),
            format(string(Alt), "~w[?1049h", [E]),
            format(string(Reset), "~w[0m", [E]),
            forall(member(Said-Data, ["'ab'"-"ab",
                                      "a line feed and 'c'"-"\r\nc",
                                      "the cursor to row 4, hidden"-Hidden,
                                      "the alternate screen"-Alt,
                                      "the bell"-"\a",
                                      "nothing that draws: a reset of attributes"-Reset]),
                   (   format("-- fed: ~w~n", [Said]), vterm_feed(T, Data) )),
            format("-- asked where the cursor is, nobody running: the answer waits~n"),
            format(string(Ask), "~w[2;5H~w[6n", [E, E]), vterm_feed(T, Ask),
            vterm_answer(T, A1), py_repr(A1, A1T), format("    answer() = ~w~n", [A1T]),
            format("-- a key pressed with nobody running~n"),
            ignore(vterm_press(T, f1, [], [react_s(0)])),
            vterm_answer(T, A2), py_repr(A2, A2T), format("    answer() = ~w~n", [A2T]) )).

run_missing :-
    setenv('HWUT_LIBVTERM', '/nowhere/libvterm.so'),
    vterm_reset_library,
    catch(( vterm_screen_new(S), vterm_close(S),
            format("a Screen stands on a library that is not there~n") ),
          error(vterm_error('LibraryMissing', Message), _),
          (   %  THE SYSTEM'S OWN WORDS for the failed load are left out; what
              %  this module says -- the line, and the way to install -- stands.
              split_string(Message, "\n", "", [First|Rest]),
              (   sub_string(First, Before, _, _, " -- ") -> sub_string(First, 0, Before, _, Head)
              ;   Head = First
              ),
              format("LibraryMissing: ~w~n", [Head]),
              forall(member(L, Rest), format("~w~n", [L])) )).

main :-
    hwut_runner_run("A terminal's screen read by a test: libvterm through the C port, a foreign library.",
                    [ text-probe(run_text),
                      screen-probe(run_screen),
                      attributes-probe(run_attributes),
                      colours-probe(run_colours),
                      unnoticed-probe(run_unnoticed),
                      keys-probe(run_keys),
                      regions-probe(run_regions),
                      events-probe(run_events),
                      missing-run_missing ],
                    []).
