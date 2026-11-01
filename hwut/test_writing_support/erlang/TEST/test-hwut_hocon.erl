%% @hwut {
%%     title      = "HOCON parser: subset (A), annotated tree"
%%     choices {
%%         comments  { features = ["erlang-hocon"] }
%%         faults    { features = ["erlang-hocon"] }
%%         fuzz      { features = ["erlang-hocon"] }
%%         numbers   { features = ["erlang-hocon"] }
%%         oneline   { features = ["erlang-hocon"] }
%%         positions { features = ["erlang-hocon"] }
%%         quoting   { features = ["erlang-hocon"] }
%%         refused   { features = ["erlang-hocon"] }
%%         scalars   { features = ["erlang-hocon"] }
%%         structure { features = ["erlang-hocon"] }
%%         triple    { features = ["erlang-hocon"] }
%%         unclosed  { features = ["erlang-hocon"] }
%%     }
%%     interactive = true
%% }
%%
%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% PURPOSE: The Erlang port of 'python/TEST/test-hwut_hocon.py', choice for
%%          choice, held against its GOOD files by '.link'. The fuzz bound is
%%          a process per parse, killed past it: Python's SIGALRM.
%%_____________________________________________________________________________
-mode(compile).
-include("../hwut_boot.hrl").
-include("../hwut_hocon.hrl").

-define(Q, "\"\"\"").

main(Argv) ->
    hwut_boot(),
    hwut_runner:run(Argv, "HOCON parser: subset (A), annotated tree;",
                    #{"scalars"   => fun test_scalars/0,
                      "numbers"   => fun test_numbers/0,
                      "quoting"   => fun test_quoting/0,
                      "structure" => fun test_structure/0,
                      "oneline"   => fun test_oneline/0,
                      "comments"  => fun test_comments/0,
                      "refused"   => fun test_refused/0,
                      "triple"    => fun test_triple/0,
                      "unclosed"  => fun test_unclosed/0,
                      "fuzz"      => fun test_fuzz/0,
                      "faults"    => fun test_faults/0,
                      "positions" => fun test_positions/0}).

%% RETURN: ok; the section heading is printed.
banner(Label) -> io:format("~n--- ~ts ---~n", [Label]).

%% RETURN: [#source_line{}], 'Text' split at its newlines, the offsets
%%         applied uniformly.
lines(Text) -> lines(Text, 0, 0).
lines(Text, LineOffset, ColumnOffset) ->
    Parts = binary:split(iolist_to_binary(Text), <<"\n">>, [global]),
    [#source_line{text = T, line = I + LineOffset, column_offset = ColumnOffset}
     || {I, T} <- lists:zip(lists:seq(1, length(Parts)), Parts)].

%% RETURN: ok; the annotated tree is printed, positions included.
show(Node) -> show(Node, 0).
show(#hocon_object{position = P, entry_list = Entries}, Indent) ->
    Pad = pad(Indent),
    io:format("~ts{ at ~ts~n", [Pad, hwut_hocon:position_text(P)]),
    [begin
         io:format("~ts  key '~ts' at ~ts ->~n", [Pad, K, hwut_hocon:position_text(KP)]),
         show(N, Indent + 1)
     end || #hocon_entry{key = K, key_position = KP, node = N} <- Entries],
    io:format("~ts}~n", [Pad]);
show(#hocon_list{position = P, item_list = Items}, Indent) ->
    Pad = pad(Indent),
    io:format("~ts[ at ~ts~n", [Pad, hwut_hocon:position_text(P)]),
    [show(I, Indent + 1) || I <- Items],
    io:format("~ts]~n", [Pad]);
show(#hocon_scalar{position = P, value = V}, Indent) ->
    io:format("~ts~ts (~ts) at ~ts~n", [pad(Indent), pytext:repr(V), type_name(V), hwut_hocon:position_text(P)]).

%% RETURN: string, the blanks of one indentation level times 'Indent'.
pad(Indent) -> lists:duplicate(4 * Indent, $\s).

%% RETURN: string, the name of the value's Python type.
type_name(V) when is_boolean(V)                -> "bool";
type_name(none)                                -> "NoneType";
type_name(V) when is_integer(V)                -> "int";
type_name(V) when is_float(V); V == inf; V == '-inf' -> "float";
type_name(V) when is_binary(V)                 -> "str".

%% RETURN: ok; 'Text' is parsed, its tree and faults printed.
run(Label, Text) -> run(Label, Text, 0, 0).
run(Label, Text, LineOffset, ColumnOffset) ->
    banner(Label),
    {Document, Faults} = hwut_hocon:parse(lines(Text, LineOffset, ColumnOffset), "f.hocon"),
    show(Document),
    [io:format("FAULT ~ts~n", [hwut_hocon:fault_text(F)]) || F <- Faults],
    ok.

%% RETURN: ok; every scalar shape.
test_scalars() ->
    run("scalars",
        "a = bare\n"
        "b = \"quoted \\\"x\\\" and \\n\"\n"
        "c = 42\n"
        "d = -3.14\n"
        "e = 1e-6\n"
        "f = true\n"
        "g = no\n"
        "h = make %.exe\n"
        "i: \"colon-bound\"\n"
        "j = null\n"
        "k = nihil\n"
        "l =\n").

%% RETURN: ok; every radix, the helper, and the split sign.
test_numbers() ->
    run("decimal, with sign and exponent",
        "a = 42\nb = -0.12\nc = +7e212\nd = 6.02e23\ne = .5\n"),
    run("the visual helper enters no value",
        "a = 1_000\nb = 7_000.5_5\n"),
    run("hexadecimal, binary, octal",
        "a = 0xDEAD_BEEF\nb = 0b0111_11_01\nc = 0o3124\nd = 0XFF\ne = -0b1010\n"),
    run("roman",
        "a = 0rIV\nb = 0rMCMLXXXIV\nc = -0rX\n"),
    run("a sign standing apart from its digits",
        "a = - 0.12\nb = + 7\nc = - 0xFF\nd = - -1.5e3\n"),
    run("what spells no number is a string, and carries quotes",
        "a = 1.2.3\nb = 0x\nc = 0b012\nd = 1__0\ne = 0rIIII\nf = 0rVX\n"),
    run("no arithmetic: this language computes nothing",
        "a = 5 - 1\n").

%% RETURN: ok; the quoted string, and the unquoted word.
test_quoting() ->
    run("quoted: blanks, comment markers and binders are content",
        "a = \"make %.exe\"\nb = \"not # a comment\"\nc = \"x = y\"\nd = \"yes\"\n"),
    run("unquoted: refused, and shown in the quotes it wants",
        "a = make\nb = strip.pype\nc = [one, two]\nd = 1\n").

%% RETURN: ok; objects, lists, nesting.
test_structure() ->
    run("nesting and key-brace",
        "outer {\n    inner = { deep = 1 }\n    braced { x = 2 }\n}\n"),
    run("lists",
        "commas   = [one, two, three]\n"
        "newlines = [\n    1\n    2\n]\n"
        "objects  = [ { a = 1 }, { a = 2 } ]\n"
        "empty    = []\n").

%% RETURN: ok; entries sharing a line, without commas.
test_oneline() ->
    run("two entries, one line, no comma",
        "caps { timeout_sec = 30  network = false }\n"),
    run("a quoted value with blanks, beside a following key",
        "a { build = \"make %.exe\"  timeout_sec = 5 }\n"),
    run("three entries, one line",
        "x { a = 1  b = \"two\"  c = { d = 3 } }\n").

%% RETURN: ok; both comment forms, whole-line and trailing.
test_comments() ->
    run("comments",
        "# whole line\na = 1   # trailing\n// slashes too\nb = 2   // trailing slashes\n"
        "c = bare value # comment cut\n").

%% RETURN: ok; the three constructs that do not exist here.
test_refused() ->
    run("refused, each by name",
        "include \"other.conf\"\na = ${outside.value}\nb += appended\nd = survives\n").

%% RETURN: ok; the text of several lines.
test_triple() ->
    run("several lines: indentation and blank ends go",
        "doc = " ?Q "\n    First line.\n\n      indented more\n    last line\n    " ?Q "\nafter = 1\n"),
    run("on one line; beside another entry; in a list",
        "a = " ?Q "one line" ?Q "  b = 2\nc = [" ?Q "x" ?Q ", \"y\"]\n"),
    run("as written: a quote, a backslash-n, a comment marker",
        "a = " ?Q "says \"no\" \\n # not a comment" ?Q "\n"),
    run("never closed: a fault, at its beginning",
        "a = 1\nb = " ?Q "open\nc = 2\n").

%% RETURN: ok; faults accumulate, the parse completes.
test_faults() ->
    run("faults accumulate",
        "a = 1\na = 2\nb = \"unterminated\n}\nc {\n    d = 3\n").

%% RETURN: ok; a list whose ']' was forgotten ENDS, the fault said once.
test_unclosed() ->
    run("a list closed by the object's brace",
        "@hwut { title = \"B\" choices = [ }\nafter = 1\n"),
    run("a stray character in a list",
        "a = [1, ; 2]\n").

-define(FUZZ_SEED_TUPLE,
        {<<"@hwut {\n"
           "    title    = \"T\"\n"
           "    choices  = [\"a\", \"b\"]\n"
           "    tolerance { eq_pattern = [\"x.*\"] }\n"
           "    n        = -1.5e3\n"
           "    f        = true\n"
           "}\n">>,
         <<"hwut {\n"
           "    target     { clean = \"./c.sh\" }\n"
           "    dependency { \"a.py\" = [\"b.py one\"] }\n"
           "    ignore     = [\"x\"]   // comment\n"
           "    # comment\n"
           "}\n">>}).
%%  WHAT A TYPO IS MADE OF: the characters HOCON gives meaning to, a few
%%  that it refuses by name, and some ordinary ones.
-define(FUZZ_ALPHABET, [<<C>> || C <- "{}[]\",=:#/\\$ \n\t-+.eE0a"] ++
                       [<<"\"\"\"">>, <<"${">>, <<"//">>, <<"+=">>]).
-define(FUZZ_INPUT_N, 3000).
-define(FUZZ_BOUND_MS, 500).            % one parse takes well under a millisecond

%% RETURN: {Text, Stream}, 'Text0' edited by one to four random insertions,
%%         deletions and duplications of a short stretch.
mutated(Text0, S0) ->
    {N, S1} = deterministic_random:next_int(1, 4, S0),
    lists:foldl(fun(_, {Text, Si}) ->
                        {I, Sa} = deterministic_random:next_int(0, byte_size(Text), Si),
                        {Head, Tail} = split_binary(Text, I),
                        case deterministic_random:next_int(0, 2, Sa) of
                            {0, Sb} -> {Insert, Sc} = deterministic_random:select(?FUZZ_ALPHABET, Sb),
                                       {<<Head/binary, Insert/binary, Tail/binary>>, Sc};
                            {1, Sb} -> {<<Head/binary, (slice(Tail, 1, byte_size(Tail)))/binary>>, Sb};
                            {_, Sb} -> {J, Sc} = deterministic_random:next_int(0, byte_size(Text), Sb),
                                       {<<Head/binary, (slice(Text, J, J + 5))/binary, Tail/binary>>, Sc}
                        end
                end, {Text0, S1}, lists:seq(1, N)).

%% RETURN: binary, Python's 'Text[From:To]' -- the bounds clamped.
slice(Text, From, To) ->
    F = min(From, byte_size(Text)),
    binary:part(Text, F, max(0, min(To, byte_size(Text)) - F)).

%% RETURN: clean | 'with faults' | hang | {exception, Reason}, the verdict
%%         on one parse of 'Text' run in a process of its own -- killed past
%%         the bound, which is the hang.
bounded_parse(Text) ->
    {Pid, Ref} = spawn_monitor(fun() ->
                                       {_, Faults} = hwut_hocon:parse(lines(Text), "f.hocon"),
                                       exit({parsed, Faults})
                               end),
    receive
        {'DOWN', Ref, process, Pid, {parsed, []}} -> clean;
        {'DOWN', Ref, process, Pid, {parsed, _}}  -> 'with faults';
        {'DOWN', Ref, process, Pid, Reason}       -> {exception, Reason}
    after ?FUZZ_BOUND_MS ->
        exit(Pid, kill),
        receive {'DOWN', Ref, process, Pid, _} -> hang end
    end.

%% RETURN: ok; every mutated header ends and answers faults -- only the
%%         counts are printed, and the first hang and exception if any.
test_fuzz() ->
    {Tally, Example, _} =
        lists:foldl(fun(_, {T, E, S0}) ->
                            {Seed, S1} = deterministic_random:select(?FUZZ_SEED_TUPLE, S0),
                            {Text, S2} = mutated(Seed, S1),
                            {Key, Said} = case bounded_parse(Text) of
                                              {exception, R} -> {exception, io_lib:format("~p~n~ts", [R, Text])};
                                              hang           -> {hang, Text};
                                              K              -> {K, none}
                                          end,
                            {maps:update_with(Key, fun(N) -> N + 1 end, T),
                             case Said of none -> E; _ -> maps:merge(#{Key => Said}, E) end, S2}
                    end, {#{clean => 0, 'with faults' => 0, hang => 0, exception => 0}, #{},
                          deterministic_random:new(4711)},
                    lists:seq(1, ?FUZZ_INPUT_N)),
    banner(io_lib:format("~b mutated headers", [?FUZZ_INPUT_N])),
    [io:format("    ~ts ~b~n", [pytext:ljust(atom_to_list(K), 12), maps:get(K, Tally)])
     || K <- [clean, 'with faults', hang, exception]],
    [io:format("FIRST ~ts:~n~ts~n", [string:uppercase(atom_to_list(K)), maps:get(K, Example)])
     || K <- [hang, exception], is_map_key(K, Example)],
    ok.

%% RETURN: ok; offsets carried: the same text at its place in a larger file.
test_positions() ->
    Text = "@hwut {\n    title = \"T\"\n}",
    run("plain: as its own file", Text),
    run("offset: same text, region begins at line 40, 3 columns stripped", Text, 39, 3).
