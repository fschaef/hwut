% @hwut {
%     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
%     pype    = "build.pypes"
%     same    = true
%     choices = ["serial", "parallel"]
%     features = ["pype-in-header", "pype-system", "same-nominal", "choices-as-list",
%                 "pype-push-pop", "pype-entry-exit", "pype-import", "pype-repeat-group",
%                 "pype-quantity", "pype-anchors-globs-flush"]
%     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
% }
%
/*
______________________________________________________________________________
SUBJECT  the log of a recursive build -- configure, then the directories
         'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
         a pype system makes of it.
REQUIREMENT  A parallel build builds what the serial build builds: the same
             sources, the same warnings, the same archives and the same
             program, linked from the same parts.

The application only REPORTS the build as it happens, as 'make -w' would.
The header's 'pype = "build.pypes"' puts a SYSTEM of two pype scripts
between it and the comparison (hwut runs it; the application prints no
'<hwut-end>'):

    build.pypes       --> normalise.pype         stdin to the first
                      normalise.pype --> build.pype
    normalise.pype    a parallel build tags each line with its job,
                      'job2: cc -c ...'; the tag goes, every other line
                      passes unchanged ('flush')
    build.pype        the summary, sorted -- see its own comments: modes
                      pushed on 'Entering directory' and popped on
                      'Leaving' (nested: 'app/plugins' inside 'app'),
                      '<entry>'/'<exit>' around each, a vocabulary
                      imported from 'compiler.pype', a repeat group over
                      the parts of a link, durations read as quantities

'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.pro.txt'. Serial or
parallel, the summary must be the same -- that is the requirement, and
the header says it once. 'choices' is a list: no choice states anything
of its own.

The laws: the compile times sum to under 5 s ('((compile: ...))', in
s, whatever unit the log used), and nothing in the log broke the build's
grammar ('((breaches: 0))').

A HEADER'S PYPE READS THE OUTPUT AFTER THE RUN: the whole stream at once.
Time as the pype sees it -- 'pype.time()', 'tick:' -- is no time of the
build here; a pype that judges time is fed live ('protocol.sh slow').
______________________________________________________________________________
*/
:- encoding(utf8).
:- initialization(main, main).

%  What each directory does: its sources, warnings and products.
directory(lib, ["lib/str.c", "lib/num.c", "lib/map.c"],
          ["lib/num.c"-"lib/num.c:14:9: warning: unused variable 'n'"],
          "ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o").
directory('app/plugins', ["app/plugins/png.c", "app/plugins/svg.c"],
          ["app/plugins/svg.c"-"app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'"],
          "ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o").
directory(app, ["app/main.c", "app/cli.c"],
          [],
          "ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a").

%   compile_lines(+Name, -Lines)
%   RETURN: Lines, the strings building directory 'Name' prints, its sources
%           compiled in the time each takes.
compile_lines(Name, Lines) :-
    directory(Name, Sources, Warnings, _),
    foldl(compile_source(Warnings), Sources, Lines, []).

compile_source(Warnings, Source, Lines0, Lines) :-
    random(U), Took is 0.04 + 0.08 * U,
    sleep(Took),
    (   Took < 0.1
    ->  Ms is truncate(Took * 1000), format(string(Spent), "~d ms", [Ms])
    ;   format(string(Spent), "~2f s", [Took])
    ),
    sub_string(Source, 0, _, 2, Stem),
    format(string(Line), "cc -c ~s -o ~s.o (took ~s)", [Source, Stem, Spent]),
    Lines0 = [Line|Lines1],
    (   memberchk(Source-Warning, Warnings)
    ->  Lines1 = [Warning|Lines]
    ;   Lines1 = Lines
    ).

%   directory_block(+Name, +Level, +Inner, -Lines)
%   RETURN: Lines, the block 'make -w' prints for 'Name' at 'Level', the
%           block of 'Inner' ('none' where none) nested before the product.
directory_block(Name, Level, Inner, Lines) :-
    format(string(Enter), "make[~d]: Entering directory '~w'", [Level, Name]),
    compile_lines(Name, Compiled),
    (   Inner == none
    ->  Nested = []
    ;   Level1 is Level + 1, directory_block(Inner, Level1, none, Nested)
    ),
    directory(Name, _, _, Product),
    format(string(Leave), "make[~d]: Leaving directory '~w'", [Level, Name]),
    append([[Enter], Compiled, Nested, [Product, Leave]], Lines).

%   configure
%   RETURN: true. Prints what 'configure' prints, and that make enters the
%           top directory.
configure :-
    format("configure: checking for cc... cc~n"),
    format("configure: checking for ar... ar~n"),
    format("make: Entering directory 'demo'~n").

say(Line) :- format("~s~n", [Line]), flush_output.

%   serial
%   RETURN: true. Builds one directory after the other.
serial :-
    configure,
    directory_block(lib, 1, none, Lib), maplist(say, Lib),
    directory_block(app, 1, 'app/plugins', App), maplist(say, App),
    format("make: Leaving directory 'demo'~n").

%   parallel
%   RETURN: true. Builds 'lib' and 'app' at once. Each job prints its block
%           whole when done ('make -O'), every line tagged with the job;
%           which job finishes first is the scheduler's.
parallel :-
    configure,
    thread_create(job(1, lib, none), A, []),
    thread_create(job(2, app, 'app/plugins'), B, []),
    thread_join(A), thread_join(B),
    format("make: Leaving directory 'demo'~n").

job(Slot, Name, Inner) :-
    directory_block(Name, 1, Inner, Block),
    with_mutex(build_print,
               forall(member(Line, Block), ( format("job~d: ~s~n", [Slot, Line]), flush_output ))).

main :-
    set_stream(user_output, encoding(utf8)),
    get_time(T), Seed is truncate(T * 1.0e9), set_random(seed(Seed)),
    current_prolog_flag(argv, Argv),
    (   Argv = [Word|_], atom_string(Choice, Word), memberchk(Choice, [serial, parallel])
    ->  call(Choice)
    ;   format("choices: serial, parallel~n"),
        halt(1)
    ).
