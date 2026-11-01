/*  SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
    ___________________________________________________________________________

    PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- the port of
             'python/hwut_vterm.py' (its README explains the screen, the
             terminal an application runs in, the raw events and the
             regions; this module prints the same words).

        setup_call_cleanup(vterm_screen_new(24, 80, S),
                           ( vterm_feed(S, "\e[1mbold\e[0m plain"),
                             vterm_line(S, 0, Line),            % "bold plain"
                             vterm_cell(S, 0, 0, Cell),
                             vterm_cell_attribute(Cell, bold),  % succeeds
                             vterm_cursor(S, Row, Column) ),    % 0, 10
                           vterm_close(S))

    LIBVTERM THROUGH THE C PORT, BY SWI-PROLOG'S FOREIGN INTERFACE. Prolog
    cannot call a C library, open a pseudo-terminal or wait on one with a
    timeout; SWI-Prolog's foreign interface can. 'hwut_vterm4pl.c' puts
    '../c/hwut_vterm.c', UNCHANGED, behind foreign predicates; 'make' in this
    directory builds the shared object on first load (a C compiler and
    SWI-Prolog's header, which the 'swi-prolog' package installs). libvterm
    itself is found at run time, as the C port finds it: 'libvterm.so.0', or
    the file HWUT_LIBVTERM names.

    TWO KINDS OF HANDLE:
        vterm_screen(Address, Rows, Columns)      the grid alone
        vterm_terminal(Address, Rows, Columns)    a screen an application
                                                  runs in, observed by
                                                  callbacks
    Every screen predicate takes either. 'with Screen() as s' is
    'setup_call_cleanup(vterm_screen_new(...), Goal, vterm_close(S))'.

    PYTHON'S VALUES, PROLOG'S WAYS:
        an exception          error(vterm_error(Kind, Message), _) -- Kind
                              Python's name: 'LibraryMissing', 'IndexError',
                              'KeyError', 'RuntimeError', 'TimeoutError'
        a bool                success: 'vterm_run', 'vterm_send',
                              'vterm_press', 'vterm_pump' SUCCEED where the
                              application still runs afterwards
        bytes                 bytes(Codes); a text (string, atom) is sent as
                              UTF-8
        a Cell                cell(Text, Width, Bold, Italic, Underline,
                              Blink, Reverse, Conceal, Strike, Foreground,
                              Background) -- flags true/false, a colour
                              none or tuple([Red, Green, Blue])
        an Event              event(Kind, Row, Column, RowEnd, ColumnEnd,
                              Name, Value) -- none where no part of the kind
        keyword arguments     options: settle_s(S), react_s(S), start_s(S),
                              cwd(Dir), timeout_s(S); region row(R),
                              row_n(N), column(C), column_n(N)
        a callback            a closure: 'call(C, Event)' (on_event),
                              'call(C, Name, Lines)' (on_change), called
                              while the predicate that caused it runs
    The application's ENVIRONMENT is the process's at 'vterm_run' (setenv/2
    before it), less LINES and COLUMNS, TERM 'xterm-256color'.
    ___________________________________________________________________________
*/
:- module(hwut_vterm,
          [ vterm_detection_text/1,     % -Text
            vterm_reset_library/0,
            vterm_screen_new/1,         % -Screen                 (24 x 80)
            vterm_screen_new/3,         % +Rows, +Columns, -Screen
            vterm_terminal_new/4,       % +Rows, +Columns, +Options, -Terminal
            vterm_close/1,              % +ScreenOrTerminal
            vterm_feed/2,               % +S, +Data
            vterm_feed/3,               % +S, +Data, -Taken
            vterm_cursor/3,             % +S, -Row, -Column
            vterm_cell/4,               % +S, +Row, +Column, -Cell
            vterm_line/3,               % +S, +Row, -Line
            vterm_line_list/2,          % +S, -Lines
            vterm_cell_text/2,          % +Cell, -Text
            vterm_cell_width/2,         % +Cell, -Width
            vterm_cell_attribute/2,     % +Cell, ?Name
            vterm_cell_attribute_text/2,% +Cell, -Text
            vterm_cell_foreground/2,    % +Cell, -Colour
            vterm_cell_background/2,    % +Cell, -Colour
            vterm_attribute_sgr/2,      % ?Name, ?Code
            vterm_event_text/2,         % +Event, -Text
            vterm_on_event/2,           % +T, :Closure
            vterm_on_change/2,          % +T, :Closure
            vterm_region/3,             % +T, +Name, +Options
            vterm_region_text/3,        % +T, +Name, -Lines
            vterm_report/2,             % +T, -ChangedNames
            vterm_answer/2,             % +T, -Bytes
            vterm_send/2,               % +T, +Text
            vterm_send/3,               % +T, +Text, +Options
            vterm_press/2,              % +T, +Key
            vterm_press/3,              % +T, +Key, +Modifiers
            vterm_press/4,              % +T, +Key, +Modifiers, +Options
            vterm_run/2,                % +T, +Argv
            vterm_run/3,                % +T, +Argv, +Options
            vterm_pump/2,               % +T, +FirstS
            vterm_expect/5,             % +T, +Text, +Options, -Row, -Column
            vterm_wait/2,               % +T, -Status
            vterm_wait/3                % +T, +Options, -Status
          ]).
:- encoding(utf8).
:- use_module(library(process)).
:- use_module(library(option)).
:- use_module(library(lists)).

:- meta_predicate vterm_on_event(+, 1), vterm_on_change(+, 2).

:- dynamic callback/3.          % Address, event | change, Closure

/* ---------------------------------------------- the foreign library, built */

:- prolog_load_context(directory, Dir), asserta(support_directory(Dir)).

%   foreign_built
%   RETURN: 'make' has made 'hwut_vterm4pl.so' current, and it is
%           loaded; its own output (none on success) is kept off stdout -- stdout is
%           the test's.
foreign_built :-
    support_directory(Dir),
    process_create(path(make), ['-s', '-C', Dir, 'hwut_vterm4pl.so'],
                   [stdout(null), process(Pid)]),
    process_wait(Pid, Status),
    (   Status == exit(0)
    ->  directory_file_path(Dir, 'hwut_vterm4pl.so', Library),
        load_foreign_library(Library)
    ;   throw(error(vterm_error('RuntimeError',
                                "the foreign library 'hwut_vterm4pl.so' could not be built (make: see stderr)"), _))
    ).

:- initialization(foreign_built, now).

/* ------------------------------------------------------------ the library */

%!  vterm_detection_text(-Text) is det.
%
%   RETURN: Text, 'libvterm found: <name>', where the library loads; else the
%           text of 'LibraryMissing' -- what is wrong and how to install it.
vterm_detection_text(Text) :- '$vterm_detection_text'(Text).

%!  vterm_reset_library is det.
%
%   RETURN: true; the library is looked for again at the next screen, and
%           its layout measured again -- Python's 'hwut_vterm._library = None'.
vterm_reset_library :- '$vterm_reset_library'.

/* ------------------------------------------------------------- the screen */

address(vterm_screen(A, _, _), A).
address(vterm_terminal(A, _, _), A).

%!  vterm_screen_new(-Screen) is det.
%!  vterm_screen_new(+Rows, +Columns, -Screen) is det.
%
%   RETURN: Screen, 'vterm_screen(Address, Rows, Columns)' (24 x 80 where not
%           given), blank, the cursor at (0, 0), if success; raises
%           error(vterm_error('LibraryMissing', Message), _), where libvterm
%           is not found -- Message says how to install it.
vterm_screen_new(S) :- vterm_screen_new(24, 80, S).
vterm_screen_new(R, C, vterm_screen(A, R, C)) :- '$vterm_screen_new'(R, C, A).

%!  vterm_terminal_new(+Rows, +Columns, +Options, -Terminal) is det.
%
%   RETURN: Terminal, 'vterm_terminal(Address, Rows, Columns)', blank,
%           nothing running in it, if success; raises as 'vterm_screen_new'.
%           settle_s(S) (0.1): how long the application must write nothing
%           before its screen is taken as drawn.
vterm_terminal_new(R, C, Options, vterm_terminal(A, R, C)) :-
    option(settle_s(S0), Options, 0.1), S is float(S0),
    '$vterm_terminal_new'(R, C, S, A).

%!  vterm_close(+ScreenOrTerminal) is det.
%
%   RETURN: true; an application still running is killed, the
%           pseudo-terminal closed, the terminal's memory freed, its
%           callbacks forgotten. The handle names nothing from now on.
vterm_close(vterm_screen(A, _, _)) :- '$vterm_screen_free'(A).
vterm_close(vterm_terminal(A, _, _)) :- retractall(callback(A, _, _)), '$vterm_terminal_free'(A).

%!  vterm_feed(+S, +Data) is det.
%!  vterm_feed(+S, +Data, -Taken) is det.
%
%   RETURN: Taken, the number of bytes the terminal took -- all of them,
%           where it works as documented. 'Data' is what a program wrote:
%           bytes(Codes), or a text sent as UTF-8. On a terminal the raw
%           events fire before this returns, and what the terminal answered
%           goes to the application, where one runs.
vterm_feed(S, Data) :- vterm_feed(S, Data, _).
vterm_feed(vterm_screen(A, _, _), Data, N) :- '$vterm_feed'(A, false, Data, N).
vterm_feed(vterm_terminal(A, _, _), Data, N) :- '$vterm_feed'(A, true, Data, N).

%!  vterm_cursor(+S, -Row, -Column) is det.
%
%   RETURN: Row, Column, the cursor's place, from 0.
vterm_cursor(S, R, C) :- address(S, A), '$vterm_cursor'(A, R, C).

%!  vterm_cell(+S, +Row, +Column, -Cell) is det.
%
%   RETURN: Cell, what stands at that place (see the head), if success;
%           raises error(vterm_error('IndexError', _), _), where the place is
%           not on the screen.
vterm_cell(S, R, C, Cell) :- address(S, A), '$vterm_cell'(A, R, C, Cell).

%!  vterm_line(+S, +Row, -Line) is det.
%
%   RETURN: Line, the row's characters as a string, blanks at its end
%           dropped; a cell nothing was written to reads as a blank.
vterm_line(S, R, L) :- address(S, A), '$vterm_line'(A, R, L).

%!  vterm_line_list(+S, -Lines) is det.
%
%   RETURN: Lines, every row as 'vterm_line' gives it, top first.
vterm_line_list(S, Lines) :-
    ( S = vterm_screen(_, Rows, _) ; S = vterm_terminal(_, Rows, _) ), !,
    Last is Rows - 1,
    findall(L, ( between(0, Last, R), vterm_line(S, R, L) ), Lines).

/* --------------------------------------------------------------- the cell */

%!  vterm_attribute_sgr(?Name, ?Code) is nondet.
%
%   RETURN: Name and the SGR code that sets it, in the fixed order of the
%           attributes: bold 1, italic 3, underline 4, blink 5, reverse 7,
%           conceal 8, strike 9.
vterm_attribute_sgr(bold, "1").
vterm_attribute_sgr(italic, "3").
vterm_attribute_sgr(underline, "4").
vterm_attribute_sgr(blink, "5").
vterm_attribute_sgr(reverse, "7").
vterm_attribute_sgr(conceal, "8").
vterm_attribute_sgr(strike, "9").

attribute_arg(bold, 3). attribute_arg(italic, 4). attribute_arg(underline, 5).
attribute_arg(blink, 6). attribute_arg(reverse, 7). attribute_arg(conceal, 8).
attribute_arg(strike, 9).

%!  vterm_cell_text(+Cell, -Text) is det.
%
%   RETURN: Text, what stands in the cell -- "" for a cell nothing was
%           written to, and for the right half of a wide character.
vterm_cell_text(Cell, T) :- arg(1, Cell, T).

%!  vterm_cell_width(+Cell, -Width) is det.
%
%   RETURN: Width, the columns the cell's character takes (1, or 2 wide).
vterm_cell_width(Cell, W) :- arg(2, Cell, W).

%!  vterm_cell_attribute(+Cell, ?Name) is nondet.
%
%   RETURN: Name, an attribute set in the cell -- on backtracking each, in
%           the fixed order; fails where none (or not 'Name') is set.
vterm_cell_attribute(Cell, Name) :-
    vterm_attribute_sgr(Name, _), attribute_arg(Name, I), arg(I, Cell, true).

%!  vterm_cell_attribute_text(+Cell, -Text) is det.
%
%   RETURN: Text, the attributes set, by name and in the fixed order,
%           separated by blanks -- 'bold reverse'; "" where none is set.
vterm_cell_attribute_text(Cell, Text) :-
    findall(N, vterm_cell_attribute(Cell, N), Ns),
    atomic_list_concat(Ns, ' ', A), atom_string(A, Text).

%!  vterm_cell_foreground(+Cell, -Colour) is det.
%!  vterm_cell_background(+Cell, -Colour) is det.
%
%   RETURN: Colour, tuple([Red, Green, Blue]); none where the cell wears the
%           terminal's default -- also where a program asked by number for
%           the very colour the default is.
vterm_cell_foreground(Cell, C) :- arg(10, Cell, C).
vterm_cell_background(Cell, C) :- arg(11, Cell, C).

/* ------------------------------------------------------------- the events */

%!  vterm_event_text(+Event, -Text) is det.
%
%   RETURN: Text, the event on one line, as a test prints it:
%           'damage    rows 0..1  columns 0..2', 'cursor    (1, 4)  hidden',
%           'property  cursor-visible = 0', 'bell'.
vterm_event_text(event(damage, R, C, RE, CE, _, _), T) :- !,
    format(string(T), "damage    rows ~d..~d  columns ~d..~d", [R, RE, C, CE]).
vterm_event_text(event(cursor, R, C, _, _, _, V), T) :- !,
    ( V == true -> H = "" ; H = "  hidden" ),
    format(string(T), "cursor    (~d, ~d)~w", [R, C, H]).
vterm_event_text(event(property, _, _, _, _, N, V), T) :- !,
    ( V == none -> VT = "None" ; VT = V ),
    format(string(T), "property  ~w = ~w", [N, VT]).
vterm_event_text(event(K, _, _, _, _, _, _), T) :- atom_string(K, T).

%  THE DOORS THE C SIDE CALLS, while the predicate that caused it runs.
'$vterm_event'(A, Event) :- forall(callback(A, event, C), call(C, Event)).
'$vterm_change'(A, Name, Lines) :-
    (   nb_current('$vterm_reported', R0), R0 \== off
    ->  append(R0, [Name], R), nb_setval('$vterm_reported', R)
    ;   true
    ),
    forall(callback(A, change, C), call(C, Name, Lines)).

%!  vterm_on_event(+Terminal, :Closure) is det.
%
%   RETURN: true; 'call(Closure, Event)' is called with every raw event from
%           now on -- damage, cursor, property, bell, as libvterm reports it.
vterm_on_event(vterm_terminal(A, _, _), C) :- assertz(callback(A, event, C)).

%!  vterm_on_change(+Terminal, :Closure) is det.
%
%   RETURN: true; 'call(Closure, Name, Lines)' is called for every region
%           whose text changed, once the screen is quiet -- one call per
%           changed region and pause, in the order the regions were declared.
vterm_on_change(vterm_terminal(A, _, _), C) :- assertz(callback(A, change, C)).

%!  vterm_region(+Terminal, +Name, +Options) is det.
%
%   RETURN: true; the rectangle 'Name' is observed from now on: row_n(N)
%           (1) rows from row(R), column_n(N) columns from column(C) (0) --
%           to the right edge where not given. A NEGATIVE row counts from the
%           bottom: -1 is the last row. What stands there now is known, not
%           news: only a change is told.
vterm_region(vterm_terminal(A, _, _), Name, Options) :-
    option(row(R), Options), option(row_n(RN), Options, 1),
    option(column(C), Options, 0), option(column_n(CN), Options, -1),
    '$vterm_region'(A, Name, R, RN, C, CN).

%!  vterm_region_text(+Terminal, +Name, -Lines) is det.
%
%   RETURN: Lines, the region's rows as they stand now (strings), blanks at
%           each row's end dropped, if success; raises
%           error(vterm_error('KeyError', _), _) where no such region was
%           declared.
vterm_region_text(vterm_terminal(A, _, _), Name, Lines) :- '$vterm_region_text'(A, Name, Lines).

%!  vterm_report(+Terminal, -ChangedNames) is det.
%
%   RETURN: ChangedNames, the regions whose text differs from what was last
%           told, in the order of declaration -- each told to every
%           'on_change' closure.
vterm_report(vterm_terminal(A, _, _), Names) :-
    setup_call_cleanup(nb_setval('$vterm_reported', []),
                       ( '$vterm_report'(A, _), nb_getval('$vterm_reported', Names) ),
                       nb_setval('$vterm_reported', off)).

%!  vterm_answer(+Terminal, -Bytes) is det.
%
%   RETURN: Bytes, bytes(Codes): what the terminal said since the last call
%           and no application took -- the reply to a question fed by hand,
%           the sequence of a key pressed with nothing running.
vterm_answer(vterm_terminal(A, _, _), bytes(Codes)) :- '$vterm_answer'(A, Codes).

seconds(Options, Name, Default, S) :-
    Option =.. [Name, S0], ( option(Option, Options) -> true ; S0 = Default ), S is float(S0).

%!  vterm_send(+Terminal, +Text) is semidet.
%!  vterm_send(+Terminal, +Text, +Options) is semidet.
%
%   RETURN: true, the application still runs after 'Text' was typed,
%           character by character, as a keyboard sends it, and the screen
%           read until quiet (react_s(S), 1.0, to begin answering); fails,
%           else.
vterm_send(T, Text) :- vterm_send(T, Text, []).
vterm_send(vterm_terminal(A, _, _), Text, Options) :-
    seconds(Options, react_s, 1.0, S), '$vterm_send'(A, Text, S, true).

%!  vterm_press(+Terminal, +Key) is semidet.
%!  vterm_press(+Terminal, +Key, +Modifiers) is semidet.
%!  vterm_press(+Terminal, +Key, +Modifiers, +Options) is semidet.
%
%   RETURN: true, the application still runs after 'Key' was pressed with
%           the 'Modifiers' (a list of shift, alt, ctrl) and the screen read
%           until quiet (react_s(S), 1.0); fails, else; raises
%           error(vterm_error('KeyError', _), _) where the key or a modifier
%           has no name. 'Key' is enter, tab, backspace, escape, up, down,
%           left, right, insert, delete, home, end, pageup, pagedown, f1..f12
%           -- or one character: 'vterm_press(T, c, [ctrl])' is Ctrl-C.
vterm_press(T, Key) :- vterm_press(T, Key, [], []).
vterm_press(T, Key, Modifiers) :- vterm_press(T, Key, Modifiers, []).
vterm_press(vterm_terminal(A, _, _), Key, Modifiers, Options) :-
    seconds(Options, react_s, 1.0, S),
    atomic_list_concat(Modifiers, ' ', M),
    '$vterm_press'(A, Key, M, S, true).

%!  vterm_run(+Terminal, +Argv) is semidet.
%!  vterm_run(+Terminal, +Argv, +Options) is semidet.
%
%   RETURN: true, the application 'Argv' (a list of texts) still runs once
%           its first screen stands (start_s(S), 10.0); fails, else; raises
%           error(vterm_error('RuntimeError', _), _) where one was already
%           run here. It runs on a pseudo-terminal of this terminal's size:
%           its three streams are that terminal, it is the controlling one;
%           cwd(Dir) its directory.
vterm_run(T, Argv) :- vterm_run(T, Argv, []).
vterm_run(vterm_terminal(A, _, _), Argv, Options) :-
    seconds(Options, start_s, 10.0, S), option(cwd(Dir), Options, none),
    '$vterm_run'(A, Argv, Dir, S, true).

%!  vterm_pump(+Terminal, +FirstS) is semidet.
%
%   RETURN: true, the application still runs; fails, else. READ UNTIL QUIET:
%           up to 'FirstS' for the application to write at all, then on until
%           it wrote nothing for settle_s; then the changed regions are told.
vterm_pump(vterm_terminal(A, _, _), First) :- S is float(First), '$vterm_pump'(A, S, true).

%!  vterm_expect(+Terminal, +Text, +Options, -Row, -Column) is det.
%
%   RETURN: Row, Column, where 'Text' stands on the screen, once it does
%           (Column in characters), if success; raises
%           error(vterm_error('TimeoutError', _), _), carrying the screen,
%           where it does not within timeout_s(S) (10.0).
vterm_expect(vterm_terminal(A, _, _), Text, Options, R, C) :-
    seconds(Options, timeout_s, 10.0, S), '$vterm_expect'(A, Text, S, R, C).

%!  vterm_wait(+Terminal, -Status) is det.
%!  vterm_wait(+Terminal, +Options, -Status) is det.
%
%   RETURN: Status, the application's exit status (negative: the signal that
%           ended it), once it has ended and its last words are on the
%           screen; none, where no application was run; raises
%           error(vterm_error('TimeoutError', _), _) where it still runs after
%           timeout_s(S) (10.0) -- it is killed first.
vterm_wait(T, Status) :- vterm_wait(T, [], Status).
vterm_wait(vterm_terminal(A, _, _), Options, Status) :-
    seconds(Options, timeout_s, 10.0, S), '$vterm_wait'(A, S, Status).
