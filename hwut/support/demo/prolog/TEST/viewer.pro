/*
______________________________________________________________________________
A TERMINAL FILE VIEWER -- the program 'screen.pro' tests; no test itself.

    swipl viewer.pro <file>

Full screen, on the terminal's alternate screen: a title bar (reverse
video), as many lines of the file as fit, and a status line: the keys
flush left, the lines shown flush right. Keys: 'j' or down one line
further, 'k' or up one line back, 'q' quits.

PROLOG'S WAYS: 'with_tty_raw/1' puts the terminal in raw mode around the
loop and gives it back however the loop ends; 'get_single_char/1' reads a
key unbuffered -- a cursor key is three codes, ESC '[' and its letter;
'tty_size/2' asks the terminal its size.
______________________________________________________________________________
*/
:- encoding(utf8).
:- initialization(main, main).

%   draw(+Name, +Lines, +Top, +RowN, +ColumnN)
%   RETURN: true, once the whole screen is drawn with the file's line 'Top'
%           (from 0) first.
draw(Name, Lines, Top, RowN, ColumnN) :-
    BodyN is RowN - 2,
    length(Lines, LineN),
    ShownN is max(0, min(BodyN, LineN - Top)),
    length(Before, Top), append(Before, Rest, Lines),
    length(Shown, ShownN), append(Shown, _, Rest),
    format("\e[H\e[2J"),
    string_concat(" ", Name, Title0), fit(Title0, ColumnN, Title),
    format("\e[7m~s\e[0m\r\n", [Title]),
    forall(member(Line, Shown), ( truncated(Line, ColumnN, L), format("~s\r\n", [L]) )),
    Blank is BodyN - ShownN, forall(between(1, Blank, _), format("\r\n")),
    First is Top + 1, Last is Top + ShownN,
    format(string(Where), "lines ~d-~d of ~d", [First, Last, LineN]),
    Keys = "j k q", string_length(Keys, KeyN),
    Width is ColumnN - 1 - KeyN,
    format("\e[~d;1H~s~|~t~s~*+", [RowN, Keys, Where, Width]),
    flush_output.

%   fit(+Text, +Width, -Fitted)
%   RETURN: Fitted, 'Text' padded with blanks to 'Width', or cut to it.
fit(Text, Width, Fitted) :-
    format(string(Padded), "~s~|~t~*+", [Text, Width]),
    truncated(Padded, Width, Fitted).

truncated(Text, Width, Cut) :-
    string_length(Text, N),
    ( N > Width -> sub_string(Text, 0, Width, _, Cut) ; Cut = Text ).

%   key(-Key)
%   RETURN: Key, the key pressed: a character's code, or 'down' / 'up' for
%           the cursor keys (ESC '[' 'B' / 'A').
key(Key) :-
    get_single_char(C),
    (   C == 27
    ->  get_single_char(_), get_single_char(D),
        ( D == 0'B -> Key = down ; D == 0'A -> Key = up ; Key = D )
    ;   Key = C
    ).

loop(Name, Lines, Top, RowN, ColumnN) :-
    draw(Name, Lines, Top, RowN, ColumnN),
    key(Key),
    length(Lines, LineN),
    (   Key == 0'q
    ->  true
    ;   memberchk(Key, [0'j, down])
    ->  Top1 is min(Top + 1, max(0, LineN - (RowN - 2))),
        loop(Name, Lines, Top1, RowN, ColumnN)
    ;   memberchk(Key, [0'k, up])
    ->  Top1 is max(Top - 1, 0),
        loop(Name, Lines, Top1, RowN, ColumnN)
    ;   loop(Name, Lines, Top, RowN, ColumnN)
    ).

%   main
%   RETURN: true (status 0) once 'q' was pressed.
main :-
    set_stream(user_output, encoding(utf8)),
    current_prolog_flag(argv, [Path|_]),
    read_file_to_string(Path, Text, [encoding(utf8)]),
    split_string(Text, "\n", "", Parts),
    ( append(Lines, [""], Parts) -> true ; Lines = Parts ),     % splitlines
    tty_size(RowN, ColumnN),
    file_base_name(Path, Name),
    format("\e[?1049h"),
    setup_call_cleanup(true,
                       with_tty_raw(loop(Name, Lines, 0, RowN, ColumnN)),
                       ( format("\e[?1049l"), flush_output )).
