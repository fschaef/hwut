%% SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
%%_____________________________________________________________________________
%%
%% THE FIRST LINE OF EVERY ERLANG TEST: it finds the support modules.
%%
%%     -include("../hwut_boot.hrl").
%%     main(Argv) -> hwut_boot(), hwut_runner:run(Argv, ...).
%%
%% An escript is ONE FILE; the modules it uses are compiled ('ebin/*.beam'
%% beside this file) and put on the code path -- found from the script's own
%% place, so a test runs from any directory. Where a module is missing or
%% older than its source, 'make' builds it first ('Makefile' here, atomic
%% renames: tests that start at once may build at once).
%%_____________________________________________________________________________

%% RETURN: ok; the support modules are on the code path, built first where
%%         one was missing or stale; the VM halts with status 1 and make's
%%         words on stderr where the build failed.
hwut_boot() ->
    Support = filename:dirname(filename:dirname(filename:absname(escript:script_name()))),
    Ebin    = filename:join(Support, "ebin"),
    Header  = lists:max([0 | [filelib:last_modified(H) || H <- filelib:wildcard(filename:join(Support, "*.hrl"))]]),
    StaleF  = lists:any(fun(Source) ->
                                Beam = filename:join(Ebin, filename:basename(Source, ".erl") ++ ".beam"),
                                Built = filelib:last_modified(Beam),
                                Built == 0 orelse Built < filelib:last_modified(Source) orelse Built < Header
                        end, filelib:wildcard(filename:join(Support, "*.erl"))),
    StaleF andalso hwut_boot_make(Support),
    true = code:add_patha(Ebin),
    ok.

%% RETURN: true, once 'make all' in 'Support' succeeded; never else.
hwut_boot_make(Support) ->
    Port = open_port({spawn_executable, os:find_executable("make")},
                     [{args, ["-s", "-C", Support, "all"]}, exit_status, stderr_to_stdout, binary]),
    hwut_boot_wait(Port, []).

%% RETURN: true, the build ended well; never else (halts with status 1).
hwut_boot_wait(Port, Said) ->
    receive
        {Port, {data, Data}}  -> hwut_boot_wait(Port, [Said, Data]);
        {Port, {exit_status, 0}} -> true;
        {Port, {exit_status, _}} -> io:put_chars(standard_error, Said), halt(1)
    end.
