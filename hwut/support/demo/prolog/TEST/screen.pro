% @hwut {
%     title     = "Demo: a terminal program's screen, as a person sees it"
%     tolerance { regions    = false
%                 comment    = false
%                 whitespace = false }
%     choices {
%         open   { features = ["demo-prolog+cover-terminal-screen", "demo-prolog+cover-screen-as-seen"] }
%         scroll { features = ["demo-prolog+cover-terminal-screen", "demo-prolog+cover-screen-as-seen"] }
%     }
% }
%
/*
______________________________________________________________________________
SUBJECT  the screen of 'viewer.pro', a full-screen file viewer, run in a
         terminal of 9 rows and 40 columns and driven by its keys.
REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
             as they fit, and a status line -- the keys flush left, the lines
             shown flush right; 'j' and the down key go one line further,
             'k' one back.

hwut_vterm's terminal ('vterm_terminal_new') runs the viewer on a
pseudo-terminal: the viewer cannot tell it from a real one. The test
PRESSES KEYS and is told what CHANGED: three regions are declared -- title,
body, status -- and after every key, once the viewer has gone quiet, each
region whose text changed is printed (the closure given 'vterm_on_change').
A redraw that changes nothing is not told: the title is told once.

THE SCREEN IS COMPARED AS A PERSON SEES IT -- three tolerances switched
off, in the header:

    regions = false     the file shown is a GOOD file of hwut, with a
                        '##! potpourri' ... '####' block. On this screen
                        those are characters, not a region to open.
    comment = false     '## ...' lines are characters too, not notes.
    whitespace = false  the status line's two halves stand flush left and
                        flush right: every blank between them counts. A
                        half moved by one column is red. (A line's leading
                        and trailing blanks are stripped all the same.)

libvterm must be installed ('apt install libvterm0'); where it is not, the
test prints why and probes nothing -- its output differs from GOOD and the
reason stands in the difference. The Prolog 'hwut_vterm' reaches libvterm
through a foreign library of its own, built by 'make' in the support's
directory when it is first loaded (a C compiler and 'SWI-Prolog.h').

CHOICES  open    the viewer opened, then quit.
         scroll  down, down, 'j', then 'k': three lines on, one back.
______________________________________________________________________________
*/
:- encoding(utf8).
:- use_module('support_path.pro').
:- use_module(hwut('hwut_vterm.pro')).
:- initialization(main, main).

:- prolog_load_context(directory, Here), asserta(here(Here)).

sample("## demo.py race -- three workers
start
##! potpourri
worker B done: 5 jobs
worker A done: 3 jobs
worker C done: 2 jobs
####
all joined
## the order between the markers is
## free; the lines are not.
").

%   show(+Name, +Lines)
%   RETURN: true. Prints one region that changed, its rows as they stand on
%           the screen, from the first column.
show(Name, Lines) :-
    format("-- ~w~n", [Name]),
    forall(member(Line, Lines), format("~s~n", [Line])).

%   view(+Keys)
%   RETURN: true. Runs the viewer on the sample, presses 'Keys', quits, and
%           prints what changed after each step.
view(Keys) :-
    here(Here),
    directory_file_path(Here, 'TMP/race.txt', Path),
    file_directory_name(Path, Dir), make_directory_path(Dir),
    sample(Sample),
    setup_call_cleanup(open(Path, write, Out, [encoding(utf8)]), format(Out, "~s", [Sample]), close(Out)),
    directory_file_path(Here, 'viewer.pro', Viewer),
    current_prolog_flag(executable, Swipl),
    setup_call_cleanup(
        vterm_terminal_new(9, 40, [], T),
        ( vterm_region(T, title,  [row(0)]),
          vterm_region(T, body,   [row(1), row_n(7)]),
          vterm_region(T, status, [row(-1)]),
          vterm_on_change(T, show),
          format("> viewer.pro race.txt~n"),
          ignore(vterm_run(T, [Swipl, Viewer, Path])),
          vterm_cell(T, 0, 1, Cell),
          vterm_cell_attribute_text(Cell, Attributes),
          ( Attributes == "" -> Said = "plain" ; Said = Attributes ),
          format("title bar: ~s~n", [Said]),
          forall(member(Key, Keys),
                 ( format("> ~w~n", [Key]),
                   (   atom_length(Key, 1)
                   ->  ignore(vterm_send(T, Key))
                   ;   ignore(vterm_press(T, Key))
                   ) )),
          ignore(vterm_send(T, "q")),
          vterm_wait(T, Status),
          format("> q -- exit status ~d~n", [Status]) ),
        vterm_close(T)).

choice(open,   []).
choice(scroll, [down, down, j, k]).

main :-
    set_stream(user_output, encoding(utf8)),
    current_prolog_flag(argv, Argv),
    (   Argv = [Choice|_], choice(Choice, Keys)
    ->  catch(view(Keys),
              error(vterm_error('LibraryMissing', Message), _),
              ( format("~w~n", [Message]), halt(1) )),
        format("<hwut-end>~n")
    ;   format("choices: open, scroll~n"),
        halt(1)
    ).
