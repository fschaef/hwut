%% @hwut {
%%     title   = "Demo: a door's state machine, watched by a pype"
%%     pype    = "door.pype"
%%     choices {
%%         kept   { features = ["demo-passes-on-every-run", "fsm-law-kept"] }
%%         broken { features = ["demo-passes-on-every-run", "fsm-law-broken"] }
%%     }
%% }
%%
%%_____________________________________________________________________________
%% A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
%% may do.
%%
%% The application prints its log as it happens: noise, and a line 'door:
%% <event>' for each thing the door does. It prints no '<hwut-end>': the
%% header names 'door.pype', which stands between it and the comparison and
%% closes the stream at '<eof>'.
%%
%% 'door.pype' parses the log and fires every event into a state machine.
%% A pype script is Python whatever the application's language: the model
%% is Python's 'hwut_fsm' (support/test_writing/python) -- the Erlang port's
%% 'hwut_fsm' is the same machine, for a model inside an Erlang test:
%%
%%     closed ---( open )---> open ---( close )---> closed
%%     closed ---( lock )---> locked ---( unlock )---> closed
%%     open   ---( slam )---> jammed          # forbidden
%%
%% kept     the door does what the model allows; the report shows which
%%          transitions were taken and which not, and 'ended in closed'.
%% broken   the controller locks an open door, slams it into a jam and
%%          tries to unlock it: each surprise is ONE 'BREACH' line in the
%%          output, the jam included, and the end outside the final states
%%          is one more. The GOOD file holds them and a run that stops
%%          breaching -- or breaches differently -- shows up as a difference.
%%
%% Both choices pass on every run: what they print does not depend on time.
%%_____________________________________________________________________________
-mode(compile).

%% RETURN: [string], the door's events for the choice 'Choice'; none, no
%%         such choice.
story("kept")   -> ["open", "close", "lock", "unlock", "open", "close"];
story("broken") -> ["open", "lock", "slam", "unlock"];
story(_)        -> none.

%% RETURN: never; the VM halts with 0 once the log of the door for the choice
%%         'Argv' names was printed; with 1, naming the choices, else.
main(Argv) ->
    case Argv of
        [Choice] when Choice == "kept"; Choice == "broken" ->
            io:format("controller 2.1 up~n"),
            [io:format("tick ~b: sensors read~ndoor: ~s~n", [N, Event])
             || {N, Event} <- lists:zip(lists:seq(1, length(story(Choice))), story(Choice))],
            io:format("controller down~n");
        _ ->
            io:format("error: a choice is required: broken, kept~n"),
            halt(1)
    end.
