% @hwut {
%     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
%     tolerance { constraints = ["overshoot <= 0.5 K",
%                                "settle <= 4 min",
%                                "verdict == 'settled'"] }
%     choices {
%         heat { features = ["region-verbatim", "region-table", "region-point-cloud",
%                            "region-ignore", "laws-in-units", "string-binding",
%                            "test-level-tolerance", "annotation-lines"] }
%         cool { features = ["region-verbatim", "region-table", "region-point-cloud",
%                            "region-ignore", "laws-in-units", "string-binding",
%                            "test-level-tolerance", "annotation-lines"] }
%     }
% }
%
/*
______________________________________________________________________________
SUBJECT  a climate chamber driven from one temperature to another by a PI
         controller: its configuration, its sensors at the end, its step
         response, and the three numbers its requirement names.
REQUIREMENT  The chamber reaches the setpoint within 4 minutes, overshoots
             it by no more than 0.5 K, and reports itself 'settled'.

Every run is seeded by the clock: the sensors are noisy, the four sensor
rows come out in a different order, the calibration stamps are today's.
Both choices pass on every run anyway; each part of the output says how:

'##' lines     notes for the reader. The comparison skips them on both
               sides, anywhere -- even inside a region.

verbatim       '##! verbatim' ... '####': the configuration as loaded. It is
               YAML, where indentation is meaning, so nothing is tolerated:
               no whitespace folding, no numeric band.

table          '##! table key=0 ignore=1 numeric={2:0.0005}': one row per
               sensor, matched by its NAME (column 0) whatever the order;
               column 1, the calibration stamp, is not compared; column 2,
               the reading in K, within 0.05 %.

point-cloud    '##! point-cloud limit=0.5 constraint={...}': the step
               response as points (t, T). Every point lies within 0.5 of a
               point of the GOOD file ('limit'), AND every point keeps the
               envelope stated in the region ('constraint') -- the GOOD's
               points, too, so a GOOD that breaks its envelope is refused.

ignore         '##! ignore': a picture for the human eye. One noisy sample
               moves a star; the picture's presence is compared, its
               contents are not.

units          '((settle: 150 s))' is a quantity; the law says 'settle <= 4
               min' and the comparison converts. A temperature DIFFERENCE is
               printed in K, never in degC (an offset unit).

string law     '((verdict: "settled"))' binds a string; 'verdict ==
               'settled'' judges it.

test-level     the three laws stand ONCE, in the header's own 'tolerance',
tolerance      and hold for both choices.

CHOICES  heat  20 degC -> 40 degC.
         cool  40 degC -> 20 degC.

PROLOG'S WAYS: the step response is a list of T-Measured pairs, made by a
recursion over the simulated seconds; the integrator's state is its
arguments.
______________________________________________________________________________
*/
:- encoding(utf8).
:- initialization(main, main).

dt_s(1).                         % simulation step
duration_s(400).                 % simulated time
sample_s(20).                    % one point of the cloud every 20 s
band_k(0.3).                     % 'settled' = within 0.3 K of the setpoint
noise_k(0.02).                   % sensor noise, one sigma
plant(300.0, 0.15).              % the plant: tau in s, rate in K/s
controller(0.6, 0.01).           % the controller: kp, ki

%   config_text(-Text)
%   RETURN: Text, the configuration as loaded, line for line.
config_text(Text) :-
    plant(Tau, Rate), controller(Kp, Ki),
    format(string(Text),
"chamber:
  plant:
    time_constant_s: ~0f
    heater_rate_K_per_s: ~w
  controller:
    kind: PI
    kp: ~w
    ki: ~w
    output: [-1.0, 1.0]
  sensors: [top, middle, bottom, door]", [Tau, Rate, Kp, Ki]).

%  Offset of each sensor against the air in the middle of the chamber.
sensor_offset(top,     0.10).
sensor_offset(middle,  0.00).
sensor_offset(bottom, -0.10).
sensor_offset(door,   -0.40).

%   gauss(+Mu, +Sigma, -X)
%   RETURN: X, a float drawn from the normal distribution (Mu, Sigma)
%           -- Box-Muller.
gauss(Mu, Sigma, X) :-
    random(U1), random(U2),
    X is Mu + Sigma * sqrt(-2.0 * log(1.0 - U1)) * cos(2.0 * pi * U2).

%   step_response(+StartC, +SetpointC, -Samples)
%   RETURN: Samples, a list of T-MeasuredC, one sample per simulation step,
%           of the chamber driven from 'StartC' to 'SetpointC' by the PI
%           controller of config_text/1, with sensor noise drawn at random.
step_response(StartC, SetpointC, Samples) :-
    step(0, StartC, 0.0, SetpointC, Samples).

step(T, _, _, _, []) :- duration_s(D), T > D, !.
step(T, Temp, Integral, SetpointC, [T-Measured|Samples]) :-
    plant(Tau, Rate), controller(Kp, Ki), noise_k(Noise), dt_s(Dt),
    gauss(0.0, Noise, N), Measured is Temp + N,
    Error  is SetpointC - Measured,
    Output0 is Kp * Error + Ki * Integral,
    (   Output0 > -1.0, Output0 < 1.0               % anti-windup: integrate
    ->  Integral1 is Integral + Error * Dt          % only while unsaturated
    ;   Integral1 = Integral
    ),
    Output is max(-1.0, min(1.0, Output0)),
    Temp1 is Temp + Dt * ((20.0 - Temp) / Tau + Rate * Output),
    T1 is T + Dt,
    step(T1, Temp1, Integral1, SetpointC, Samples).

%   overshoot_k(+Samples, +StartC, +SetpointC, -K)
%   RETURN: K, how far in K the chamber went past 'SetpointC' in the
%           direction of travel from 'StartC'; 0.0 where it never did.
overshoot_k(Samples, StartC, SetpointC, K) :-
    ( SetpointC > StartC -> Sign = 1.0 ; Sign = -1.0 ),
    aggregate_all(max(D), ( member(_-Temp, Samples), D is Sign * (Temp - SetpointC) ), Max),
    K is max(0.0, Max).

%   settle_s(+Samples, +SetpointC, -S)
%   RETURN: S, the time in s after which every sample stays within band_k/1
%           of 'SetpointC' (the step after the last one outside).
settle_s(Samples, SetpointC, S) :-
    band_k(Band), dt_s(Dt),
    (   aggregate_all(max(T), ( member(T-Temp, Samples), abs(Temp - SetpointC) > Band ), Last)
    ->  S is float(Last + Dt)
    ;   S = 0.0
    ).

%   print_config
%   RETURN: true. Prints the configuration as loaded, byte for byte.
print_config :-
    config_text(Text),
    format("configuration, as loaded (YAML: whitespace is meaning):~n"),
    format("##! verbatim~n"),
    format("~s~n", [Text]),
    format("####~n").

%   print_sensors(+SetpointC)
%   RETURN: true. Prints one row per sensor, in a random order, with today's
%           calibration stamp and the reading at the end in K.
print_sensors(SetpointC) :-
    noise_k(Noise),
    format("sensors at the end, in K (the order is the bus's):~n"),
    format("    sensor  calibrated           reading_K~n"),
    format("##! table key=0 ignore=1 numeric={2:0.0005}~n"),
    random_permutation([top, middle, bottom, door], Names),
    get_time(Now), format_time(string(Stamp), '%FT%T', Now),
    forall(member(Name, Names),
           ( sensor_offset(Name, Offset), gauss(0.0, Noise, N),
             Reading is SetpointC + Offset + N + 273.15,
             format("    ~|~w~t~6+  ~s  ~|~t~2f~9+~n", [Name, Stamp, Reading]) )),
    format("####~n").

%   print_cloud(+Samples, +StartC, +SetpointC)
%   RETURN: true. Prints the step response, one point (t_s, T_degC) every
%           sample_s/1, framed with the envelope the requirement allows.
print_cloud(Samples, StartC, SetpointC) :-
    Low0 is min(StartC, SetpointC), High0 is max(StartC, SetpointC),
    (   SetpointC > StartC -> Low = Low0, High is High0 + 0.5
    ;   Low is Low0 - 0.5, High = High0
    ),
    %  0.1 K beyond the envelope on either side: the sensor's noise.
    format("step response, t in s against T in degC; envelope ~1f .. ~1f:~n", [Low, High]),
    LowC is Low - 0.1, HighC is High + 0.1,
    format("##! point-cloud limit=0.5 constraint={y >= ~1f and y <= ~1f}~n", [LowC, HighC]),
    sample_s(Every),
    forall(( member(T-Temp, Samples), T mod Every =:= 0 ),
           format("    ~|~t~d~5+  ~|~t~2f~6+~n", [T, Temp])),
    format("####~n").

%   print_picture(+Samples, +StartC, +SetpointC)
%   RETURN: true. Prints the step response as stars, for the human eye only:
%           one row per 40 s, one column per 0.5 K.
print_picture(Samples, StartC, SetpointC) :-
    Low is min(StartC, SetpointC) - 1.0,
    format("the same, as a picture ('|' the setpoint):~n"),
    format("##! ignore~n"),
    forall(( member(T-Temp, Samples), T mod 40 =:= 0 ),
           ( Bar  is round((SetpointC - Low) / 0.5),
             Star is max(0, min(45, round((Temp - Low) / 0.5))),
             numlist(0, 45, Columns),
             maplist(picture_code(Bar, Star), Columns, Codes0),
             reverse(Codes0, Reversed0),
             drop_blanks(Reversed0, Reversed),           % Python's rstrip
             reverse(Reversed, Codes),
             format("    ~|~t~d~4+ s  ~s~n", [T, Codes]) )),
    format("####~n").

drop_blanks([0' |Codes0], Codes) :- !, drop_blanks(Codes0, Codes).
drop_blanks(Codes, Codes).

picture_code(_, Star, Star, 0'*) :- !.
picture_code(Bar, _, Bar, 0'|) :- !.
picture_code(_, _, _, 0' ).

%   run(+StartC, +SetpointC)
%   RETURN: true. Drives the chamber and prints every part of the report.
run(StartC, SetpointC) :-
    step_response(StartC, SetpointC, Samples),
    format("## climate chamber, ~0f degC -> ~0f degC, one sample per second~n", [StartC, SetpointC]),
    format("## '##' lines are for the reader: the comparison skips them.~n"),
    print_config,
    print_sensors(SetpointC),
    print_cloud(Samples, StartC, SetpointC),
    print_picture(Samples, StartC, SetpointC),
    overshoot_k(Samples, StartC, SetpointC, Over),
    settle_s(Samples, SetpointC, Settle),
    format("overshoot  ((overshoot: ~2f K))          law <= 0.5 K~n", [Over]),
    format("settled    ((settle: ~0f s))             law <= 4 min~n", [Settle]),
    last(Samples, _-LastTemp), band_k(Band),
    ( abs(LastTemp - SetpointC) =< Band -> Verdict = settled ; Verdict = drifting ),
    format("chamber    ((verdict: \"~w\"))~n", [Verdict]).

choice_db([heat-(20.0-40.0), cool-(40.0-20.0)]).

main :-
    set_stream(user_output, encoding(utf8)),
    get_time(T), Seed is truncate(T * 1.0e9), set_random(seed(Seed)),
    current_prolog_flag(argv, Argv),
    choice_db(Db),
    (   Argv = [Word|_], atom_string(Choice, Word), memberchk(Choice-(Start-Setpoint), Db)
    ->  run(Start, Setpoint),
        format("<hwut-end>~n")
    ;   format("choices: heat, cool~n"),
        halt(1)
    ).
