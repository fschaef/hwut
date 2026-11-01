% @hwut {
%     title   = "Demo: a door's state machine, watched by a pype"
%     pype    = "door.pype"
%     choices {
%         kept   { features = ["demo-passes-on-every-run", "fsm-law-kept"] }
%         broken { features = ["demo-passes-on-every-run", "fsm-law-broken"] }
%     }
% }
%
/*
______________________________________________________________________________
A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
may do.

The application prints its log as it happens: noise, and a line 'door:
<event>' for each thing the door does. It prints no '<hwut-end>': the
header names 'door.pype', which stands between it and the comparison and
closes the stream at '<eof>'.

'door.pype' parses the log and fires every event into a state machine
('hwut_fsm'):

    closed ---( open )---> open ---( close )---> closed
    closed ---( lock )---> locked ---( unlock )---> closed
    open   ---( slam )---> jammed          # forbidden

A pype script is Python whatever the language of the application it reads,
so the model is fired by the Python module 'hwut_fsm'; a Prolog test that
holds a model itself loads 'hwut_fsm.pro' of the Prolog support, which
prints the same report.

kept     the door does what the model allows; the report shows which
         transitions were taken and which not, and 'ended in closed'.
broken   the controller locks an open door, slams it into a jam and
         tries to unlock it: each surprise is ONE 'BREACH' line in the
         output, the jam included, and the end outside the final states
         is one more. The GOOD file
         holds them and a run that stops breaching -- or breaches
         differently -- shows up as a difference.

Both choices pass on every run: what they print does not depend on time.
______________________________________________________________________________
*/
:- encoding(utf8).
:- initialization(main, main).

story(kept,   [open, close, lock, unlock, open, close]).
story(broken, [open, lock, slam, unlock]).

%   door_log(+Choice)
%   RETURN: true, once the log of the door for 'Choice' is printed.
door_log(Choice) :-
    story(Choice, Events),
    format("controller 2.1 up~n"),
    forall(nth1(Number, Events, Event),
           format("tick ~d: sensors read~ndoor: ~w~n", [Number, Event])),
    format("controller down~n").

main :-
    current_prolog_flag(argv, Argv),
    (   Argv = [Word], atom_string(Choice, Word), story(Choice, _)
    ->  door_log(Choice)
    ;   format("error: a choice is required: broken, kept~n"),
        halt(1)
    ).
