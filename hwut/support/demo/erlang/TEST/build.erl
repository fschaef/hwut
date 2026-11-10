%% @hwut {
%%     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
%%     pype    = "build.pypes"
%%     same    = true
%%     choices = ["serial", "parallel"]
%%     features = ["demo-erlang+cover-pype-in-header", "demo-erlang+cover-pype-system", "demo-erlang+cover-same-nominal", "demo-erlang+cover-choices-as-list",
%%                 "demo-erlang+cover-pype-push-pop", "demo-erlang+cover-pype-entry-exit", "demo-erlang+cover-pype-import", "demo-erlang+cover-pype-repeat-group",
%%                 "demo-erlang+cover-pype-quantity", "demo-erlang+cover-pype-anchors-globs-flush"]
%%     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
%% }
%%
%%_____________________________________________________________________________
%% SUBJECT  the log of a recursive build -- configure, then the directories
%%          'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
%%          a pype system makes of it.
%% REQUIREMENT  A parallel build builds what the serial build builds: the same
%%              sources, the same warnings, the same archives and the same
%%              program, linked from the same parts.
%%
%% The application only REPORTS the build as it happens, as 'make -w' would.
%% The header's 'pype = "build.pypes"' puts a SYSTEM of two pype scripts
%% between it and the comparison (hwut runs it; the application prints no
%% '<hwut-end>'):
%%
%%     build.pypes       --> normalise.pype         stdin to the first
%%                       normalise.pype --> build.pype
%%     normalise.pype    a parallel build tags each line with its job,
%%                       'job2: cc -c ...'; the tag goes, every other line
%%                       passes unchanged ('flush')
%%     build.pype        the summary, sorted -- see its own comments: modes
%%                       pushed on 'Entering directory' and popped on
%%                       'Leaving' (nested: 'app/plugins' inside 'app'),
%%                       '<entry>'/'<exit>' around each, a vocabulary
%%                       imported from 'compiler.pype', a repeat group over
%%                       the parts of a link, durations read as quantities
%%
%% 'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.erl.txt'. Serial or
%% parallel, the summary must be the same -- that is the requirement, and
%% the header says it once. 'choices' is a list: no choice states anything
%% of its own.
%%
%% The laws: the compile times sum to under 5 s ('((compile: ...))', in
%% s, whatever unit the log used), and nothing in the log broke the build's
%% grammar ('((breaches: 0))').
%%
%% A HEADER'S PYPE READS THE OUTPUT AFTER THE RUN: the whole stream at once.
%% Time as the pype sees it -- 'pype.time()', 'tick:' -- is no time of the
%% build here; a pype that judges time is fed live ('protocol.sh slow').
%%_____________________________________________________________________________
-mode(compile).

%% RETURN: {Sources, Warnings, Product}, what the directory 'Name' does: its
%%         sources, a warning per source that has one, and its product.
directory("lib") ->
    {["lib/str.c", "lib/num.c", "lib/map.c"],
     #{"lib/num.c" => "lib/num.c:14:9: warning: unused variable 'n'"},
     "ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o"};
directory("app/plugins") ->
    {["app/plugins/png.c", "app/plugins/svg.c"],
     #{"app/plugins/svg.c" => "app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'"},
     "ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o"};
directory("app") ->
    {["app/main.c", "app/cli.c"],
     #{},
     "ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a"}.

%% RETURN: [string], what building directory 'Name' prints, its sources
%%         compiled in the time each takes.
compile_lines(Name) ->
    {Sources, Warnings, _} = directory(Name),
    lists:append(
      [begin
           Took = 0.04 + rand:uniform_real() * 0.08,
           timer:sleep(round(Took * 1000)),
           Spent = if Took < 0.1 -> io_lib:format("~b ms", [trunc(Took * 1000)]);
                      true       -> io_lib:format("~.2f s", [Took])
                   end,
           Object = lists:sublist(Source, length(Source) - 2) ++ ".o",
           [lists:flatten(io_lib:format("cc -c ~s -o ~s (took ~s)", [Source, Object, Spent]))
            | [maps:get(Source, Warnings) || is_map_key(Source, Warnings)]]
       end || Source <- Sources]).

%% RETURN: [string], the block 'make -w' prints for 'Name' at 'Level', the
%%         block of 'Inner' nested before the product.
directory_block(Name, Level, Inner) ->
    {_, _, Product} = directory(Name),
    [lists:flatten(io_lib:format("make[~b]: Entering directory '~s'", [Level, Name]))]
    ++ compile_lines(Name)
    ++ case Inner of none -> []; _ -> directory_block(Inner, Level + 1, none) end
    ++ [Product, lists:flatten(io_lib:format("make[~b]: Leaving directory '~s'", [Level, Name]))].

%% RETURN: ok; prints what 'configure' prints, and that make enters the top
%%         directory.
configure() ->
    io:format("configure: checking for cc... cc~n"),
    io:format("configure: checking for ar... ar~n"),
    io:format("make: Entering directory 'demo'~n").

%% RETURN: ok; builds one directory after the other.
serial() ->
    configure(),
    [io:format("~s~n", [Line]) || Line <- directory_block("lib", 1, none)
                                         ++ directory_block("app", 1, "app/plugins")],
    io:format("make: Leaving directory 'demo'~n").

%% RETURN: ok; builds 'lib' and 'app' at once, a process each. Each job
%%         prints its block whole when done ('make -O'), every line tagged
%%         with the job -- one 'io:put_chars', so no other job's line comes
%%         between; which job finishes first is the scheduler's.
parallel() ->
    configure(),
    Job = fun(Slot, Name, Inner) ->
                  fun() ->
                          Block = directory_block(Name, 1, Inner),
                          io:put_chars([io_lib:format("job~b: ~s~n", [Slot, L]) || L <- Block])
                  end
          end,
    Refs = [monitor(process, spawn(F)) || F <- [Job(1, "lib", none), Job(2, "app", "app/plugins")]],
    [receive {'DOWN', Ref, process, _, _} -> ok end || Ref <- Refs],
    io:format("make: Leaving directory 'demo'~n").

%% RETURN: never; the VM halts with 0 after the build the choice 'Argv' names;
%%         with 1, naming the choices, else.
main(Argv) ->
    case Argv of
        ["serial" | _]   -> serial();
        ["parallel" | _] -> parallel();
        _                -> io:format("choices: serial, parallel~n"), halt(1)
    end.
