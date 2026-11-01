% @hwut {
%     title      = "HOCON parser: subset (A), annotated tree"
%     choices {
%         comments  { features = ["prolog-hocon"] }
%         faults    { features = ["prolog-hocon"] }
%         fuzz      { features = ["prolog-hocon"] }
%         numbers   { features = ["prolog-hocon"] }
%         oneline   { features = ["prolog-hocon"] }
%         positions { features = ["prolog-hocon"] }
%         quoting   { features = ["prolog-hocon"] }
%         refused   { features = ["prolog-hocon"] }
%         scalars   { features = ["prolog-hocon"] }
%         structure { features = ["prolog-hocon"] }
%         triple    { features = ["prolog-hocon"] }
%         unclosed  { features = ["prolog-hocon"] }
%     }
%     interactive = true
% }
%
% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%______________________________________________________________________________
%
% PURPOSE: The Prolog port of 'python/TEST/test-hwut_hocon.py', choice for
%          choice, held against its GOOD files by '.link'. The fuzz draws its
%          mutations from the deterministic stream exactly as the Python does
%          -- the same 3000 headers from seed 4711 -- and bounds every parse
%          by 'call_with_time_limit'.
%______________________________________________________________________________
:- encoding(utf8).
:- use_module('../hwut_runner.pro').
:- use_module('../hwut_pytext.pro').
:- use_module('../hwut_hocon.pro').
:- use_module('../deterministic_random.pro').
:- use_module(library(time)).
:- initialization(main, main).

banner(Label) :- format("~n--- ~w ---~n", [Label]).

%   show(+Node, +Indent)
%   RETURN: the annotated tree, positions included.
show(object_node(P, Entries), I) :- !,
    pad(I, Pad), hocon_position_text(P, PT),
    format("~w{ at ~w~n", [Pad, PT]),
    forall(member(entry(K, KP, Node), Entries),
           (   hocon_position_text(KP, KT),
               format("~w  key '~w' at ~w ->~n", [Pad, K, KT]),
               I1 is I + 1, show(Node, I1)
           )),
    format("~w}~n", [Pad]).
show(list_node(Items, P), I) :- !,
    pad(I, Pad), hocon_position_text(P, PT),
    format("~w[ at ~w~n", [Pad, PT]),
    I1 is I + 1, forall(member(Item, Items), show(Item, I1)),
    format("~w]~n", [Pad]).
show(scalar_node(V, P), I) :-
    pad(I, Pad), hocon_position_text(P, PT), py_repr(V, R), hocon_type_name(V, T),
    format("~w~w (~w) at ~w~n", [Pad, R, T, PT]).

pad(I, Pad) :- N is 4 * I, length(Cs, N), maplist(=(0' ), Cs), string_codes(Pad, Cs).

%   run(+Label, +Text[, +LineOffset, +ColumnOffset])
%   RETURN: 'Text' parsed, tree
%           and faults printed.
run(Label, Text) :- run(Label, Text, 0, 0).
run(Label, Text, LO, CO) :-
    banner(Label),
    hocon_lines(Text, LO, CO, Lines),
    hocon_parse(Lines, "f.hocon", Document, Faults),
    show(Document, 0),
    forall(member(F, Faults), ( hocon_fault_text(F, T), format("FAULT ~w~n", [T]) )).

test_scalars :-
    run("scalars",
        "a = bare\nb = \"quoted \\\"x\\\" and \\n\"\nc = 42\nd = -3.14\ne = 1e-6\nf = true\ng = no\nh = make %.exe\ni: \"colon-bound\"\nj = null\nk = nihil\nl =\n").

test_numbers :-
    run("decimal, with sign and exponent", "a = 42\nb = -0.12\nc = +7e212\nd = 6.02e23\ne = .5\n"),
    run("the visual helper enters no value", "a = 1_000\nb = 7_000.5_5\n"),
    run("hexadecimal, binary, octal", "a = 0xDEAD_BEEF\nb = 0b0111_11_01\nc = 0o3124\nd = 0XFF\ne = -0b1010\n"),
    run("roman", "a = 0rIV\nb = 0rMCMLXXXIV\nc = -0rX\n"),
    run("a sign standing apart from its digits", "a = - 0.12\nb = + 7\nc = - 0xFF\nd = - -1.5e3\n"),
    run("what spells no number is a string, and carries quotes",
        "a = 1.2.3\nb = 0x\nc = 0b012\nd = 1__0\ne = 0rIIII\nf = 0rVX\n"),
    run("no arithmetic: this language computes nothing", "a = 5 - 1\n").

test_quoting :-
    run("quoted: blanks, comment markers and binders are content",
        "a = \"make %.exe\"\nb = \"not # a comment\"\nc = \"x = y\"\nd = \"yes\"\n"),
    run("unquoted: refused, and shown in the quotes it wants",
        "a = make\nb = strip.pype\nc = [one, two]\nd = 1\n").

test_structure :-
    run("nesting and key-brace", "outer {\n    inner = { deep = 1 }\n    braced { x = 2 }\n}\n"),
    run("lists",
        "commas   = [one, two, three]\nnewlines = [\n    1\n    2\n]\nobjects  = [ { a = 1 }, { a = 2 } ]\nempty    = []\n").

test_oneline :-
    run("two entries, one line, no comma", "caps { timeout_sec = 30  network = false }\n"),
    run("a quoted value with blanks, beside a following key", "a { build = \"make %.exe\"  timeout_sec = 5 }\n"),
    run("three entries, one line", "x { a = 1  b = \"two\"  c = { d = 3 } }\n").

test_comments :-
    run("comments", "# whole line\na = 1   # trailing\n// slashes too\nb = 2   // trailing slashes\nc = bare value # comment cut\n").

test_refused :-
    run("refused, each by name", "include \"other.conf\"\na = ${outside.value}\nb += appended\nd = survives\n").

test_triple :-
    Q = "\"\"\"",
    format(string(T1), "doc = ~w\n    First line.\n\n      indented more\n    last line\n    ~w\nafter = 1\n", [Q, Q]),
    run("several lines: indentation and blank ends go", T1),
    format(string(T2), "a = ~wone line~w  b = 2\nc = [~wx~w, \"y\"]\n", [Q, Q, Q, Q]),
    run("on one line; beside another entry; in a list", T2),
    format(string(T3), "a = ~wsays \"no\" \\n # not a comment~w\n", [Q, Q]),
    run("as written: a quote, a backslash-n, a comment marker", T3),
    format(string(T4), "a = 1\nb = ~wopen\nc = 2\n", [Q]),
    run("never closed: a fault, at its beginning", T4).

test_faults :-
    run("faults accumulate", "a = 1\na = 2\nb = \"unterminated\n}\nc {\n    d = 3\n").

test_unclosed :-
    run("a list closed by the object's brace", "@hwut { title = \"B\" choices = [ }\nafter = 1\n"),
    run("a stray character in a list", "a = [1, ; 2]\n").

test_positions :-
    Text = "@hwut {\n    title = \"T\"\n}",
    run("plain: as its own file", Text),
    run("offset: same text, region begins at line 40, 3 columns stripped", Text, 39, 3).

/* ---------------------------------------------------------------- the fuzz */

fuzz_seed(["@hwut {\n    title    = \"T\"\n    choices  = [\"a\", \"b\"]\n    tolerance { eq_pattern = [\"x.*\"] }\n    n        = -1.5e3\n    f        = true\n}\n",
           "hwut {\n    target     { clean = \"./c.sh\" }\n    dependency { \"a.py\" = [\"b.py one\"] }\n    ignore     = [\"x\"]   // comment\n    # comment\n}\n"]).

%  WHAT A TYPO IS MADE OF: the characters HOCON gives meaning to, a few that
%  it refuses by name, and some ordinary ones.
fuzz_alphabet(A) :-
    string_chars("{}[]\",=:#/\\$ \n\t-+.eE0a", Cs),
    maplist([C, S]>>string_chars(S, [C]), Cs, Singles),
    append(Singles, ["\"\"\"", "${", "//", "+="], A).

fuzz_input_n(3000).
fuzz_bound_s(0.5).

%   mutated(+Alphabet, +Text0, -Text)//
%   RETURN: 'Text0' edited by one to four
%           random insertions, deletions and duplications of a short stretch -- the
%           stream threaded as the Python consumes it.
mutated(Alphabet, T0, T) --> dr_next_int(1, 4, N), edits(N, Alphabet, T0, T).

edits(0, _, T, T) --> !.
edits(N, Alphabet, T0, T) -->
    { string_length(T0, Len) }, dr_next_int(0, Len, I), dr_next_int(0, 2, Op),
    edit(Op, Alphabet, I, Len, T0, T1),
    { N1 is N - 1 }, edits(N1, Alphabet, T1, T).

edit(0, Alphabet, I, _, T0, T) --> !,
    dr_select(Alphabet, Insert),
    { sub_string(T0, 0, I, After, Head), sub_string(T0, I, After, 0, Tail),
      atomic_list_concat([Head, Insert, Tail], A), atom_string(A, T) }.
edit(1, _, I, Len, T0, T) --> !,
    {   sub_string(T0, 0, I, _, Head),
        ( I < Len -> J is I + 1 ; J = Len ), sub_string(T0, J, _, 0, Tail),
        string_concat(Head, Tail, T) }.
edit(_, _, I, Len, T0, T) -->
    dr_next_int(0, Len, J),
    {   K is min(5, Len - J), sub_string(T0, J, K, _, Stretch),
        sub_string(T0, 0, I, _, Head), sub_string(T0, I, _, 0, Tail),
        atomic_list_concat([Head, Stretch, Tail], A), atom_string(A, T) }.

%   fuzz(+N, +Seeds, +Alphabet, +Bound, +Tally0, -Tally, +Example0, -Example)//
fuzz(0, _, _, _, T, T, E, E) --> !.
fuzz(N, Seeds, Alphabet, Bound, T0, T, E0, E) -->
    dr_select(Seeds, Seed), mutated(Alphabet, Seed, Text),
    {   hocon_lines(Text, 0, 0, Lines),
        catch(call_with_time_limit(Bound,
                  ( hocon_parse(Lines, "f.hocon", _, Faults) -> Verdict = parsed(Faults)
                  ; Verdict = failed )),
              Error, Verdict = raised(Error)),
        verdict(Verdict, Text, T0, T1, E0, E1),
        N1 is N - 1
    },
    fuzz(N1, Seeds, Alphabet, Bound, T1, T, E1, E).

verdict(parsed([]), _, t(C, F, H, X), t(C1, F, H, X), E, E) :- !, C1 is C + 1.
verdict(parsed(_), _, t(C, F, H, X), t(C, F1, H, X), E, E) :- !, F1 is F + 1.
verdict(raised(time_limit_exceeded), Text, t(C, F, H, X), t(C, F, H1, X), E0, E) :- !,
    H1 is H + 1, first_example(hang, Text, E0, E).
verdict(Other, Text, t(C, F, H, X), t(C, F, H, X1), E0, E) :-
    X1 is X + 1, format(string(S), "~q\n~w", [Other, Text]), first_example(exception, S, E0, E).

first_example(Key, Text, E0, E) :- ( memberchk(Key-_, E0) -> E = E0 ; append(E0, [Key-Text], E) ).

test_fuzz :-
    fuzz_seed(Seeds), fuzz_alphabet(Alphabet), fuzz_input_n(N), fuzz_bound_s(Bound),
    dr_stream_new(4711, S0),
    fuzz(N, Seeds, Alphabet, Bound, t(0, 0, 0, 0), t(C, F, H, X), [], Examples, S0, _),
    format(string(L), "~d mutated headers", [N]), banner(L),
    forall(member(K-V, ["clean"-C, "with faults"-F, "hang"-H, "exception"-X]),
           ( py_ljust(K, 12, KT), format("    ~w ~d~n", [KT, V]) )),
    forall(member(K-Text, Examples),
           ( upcase_atom(K, U), format("FIRST ~w:~n~w~n", [U, Text]) )).

main :-
    hwut_runner_run("HOCON parser: subset (A), annotated tree;",
                    [ scalars-test_scalars,
                      numbers-test_numbers,
                      quoting-test_quoting,
                      structure-test_structure,
                      oneline-test_oneline,
                      comments-test_comments,
                      refused-test_refused,
                      triple-test_triple,
                      unclosed-test_unclosed,
                      fuzz-test_fuzz,
                      faults-test_faults,
                      positions-test_positions ],
                    []).
