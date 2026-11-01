%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% WHERE THE ERLANG TEST SUPPORT STANDS -- no test, the one place of this
%% directory that names it. Included by the tests that use the support
%% ('garage.erl', 'screen.erl'):
%%
%%     -include("hwut_support.hrl").
%%     main(Argv) -> hwut_support(), hwut_runner:run(Argv, ...).
%%
%% ERLANG'S OWN MECHANISM FIRST: 'ERL_LIBS' names directories of libraries;
%% the VM puts '<lib>/ebin' of every library there on its code path when it
%% starts. With 'ERL_LIBS=<dir>' and the support at '<dir>/erlang' (built:
%% 'make -C <dir>/erlang'), 'hwut_runner' is found and nothing is done here.
%%
%% ELSE THE FALLBACK on the marked line, relative to this directory: its
%% 'ebin' is put on the code path, and where a module is missing or older
%% than its source, 'make' builds it there first (the support's Makefile
%% renames each product into place: tests that start at once may build at
%% once).
%%
%% WHY A HEADER, NOT A MODULE: an escript is one file; what it includes is
%% read when it is compiled, at its start -- before any code path is set.
%%_____________________________________________________________________________

%% RETURN: ok; the support modules are on the code path -- by ERL_LIBS, else
%%         from the fallback, built first where stale;
%%         never else: the VM halts with status 1, the reason on stderr.
hwut_support() ->
    hwut_support(code:which(hwut_runner), "../../../test_writing/erlang").   %% HWUT-SUPPORT-PATH

%% RETURN: ok, the support is on the code path; never else (halts with 1).
hwut_support(non_existing, Fallback) ->
    Here    = filename:dirname(filename:absname(escript:script_name())),
    Support = filename:absname(Fallback, Here),
    case filelib:is_regular(filename:join(Support, "hwut_runner.erl")) of
        false -> io:put_chars(standard_error,
                              ["the Erlang test support is not found: neither on ERL_LIBS nor at '",
                               Support, "'\n"]),
                 halt(1);
        true  -> hwut_support_stale(Support) andalso hwut_support_make(Support),
                 true = code:add_patha(filename:join(Support, "ebin")),
                 ok
    end;
hwut_support(_ByErlLibs, _Fallback) ->
    ok.

%% RETURN: true, a module of 'Support' has no '.beam' in its 'ebin', or one
%%         older than its source or than a header; false, else.
hwut_support_stale(Support) ->
    Ebin   = filename:join(Support, "ebin"),
    Header = lists:max([0 | [filelib:last_modified(H)
                             || H <- filelib:wildcard(filename:join(Support, "*.hrl"))]]),
    lists:any(fun(Source) ->
                      Built = filelib:last_modified(
                                filename:join(Ebin, filename:basename(Source, ".erl") ++ ".beam")),
                      Built == 0 orelse Built < filelib:last_modified(Source) orelse Built < Header
              end, filelib:wildcard(filename:join(Support, "*.erl"))).

%% RETURN: true, once 'make all' in 'Support' succeeded; never else (halts
%%         with status 1, make's words on stderr).
hwut_support_make(Support) ->
    Port = open_port({spawn_executable, os:find_executable("make")},
                     [{args, ["-s", "-C", Support, "all"]}, exit_status, stderr_to_stdout, binary]),
    hwut_support_wait(Port, []).

%% RETURN: true, the build ended well; never else (halts with status 1).
hwut_support_wait(Port, Said) ->
    receive
        {Port, {data, Data}}     -> hwut_support_wait(Port, [Said, Data]);
        {Port, {exit_status, 0}} -> true;
        {Port, {exit_status, _}} -> io:put_chars(standard_error, Said), halt(1)
    end.
