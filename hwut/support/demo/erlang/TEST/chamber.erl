%% @hwut {
%%     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
%%     tolerance { constraints = ["overshoot <= 0.5 K",
%%                                "settle <= 4 min",
%%                                "verdict == 'settled'"] }
%%     choices {
%%         heat { features = ["region-verbatim", "region-table", "region-point-cloud",
%%                            "region-ignore", "laws-in-units", "string-binding",
%%                            "test-level-tolerance", "annotation-lines"] }
%%         cool { features = ["region-verbatim", "region-table", "region-point-cloud",
%%                            "region-ignore", "laws-in-units", "string-binding",
%%                            "test-level-tolerance", "annotation-lines"] }
%%     }
%% }
%%
%%_____________________________________________________________________________
%% SUBJECT  a climate chamber driven from one temperature to another by a PI
%%          controller: its configuration, its sensors at the end, its step
%%          response, and the three numbers its requirement names.
%% REQUIREMENT  The chamber reaches the setpoint within 4 minutes, overshoots
%%              it by no more than 0.5 K, and reports itself 'settled'.
%%
%% Every run draws from 'rand', seeded by the clock: the sensors are noisy,
%% the four sensor rows come out in a different order, the calibration stamps
%% are today's. Both choices pass on every run anyway; each part of the output
%% says how:
%%
%% '##' lines     notes for the reader. The comparison skips them on both
%%                sides, anywhere -- even inside a region.
%%
%% verbatim       '##! verbatim' ... '####': the configuration as loaded. It is
%%                YAML, where indentation is meaning, so nothing is tolerated:
%%                no whitespace folding, no numeric band.
%%
%% table          '##! table key=0 ignore=1 numeric={2:0.0005}': one row per
%%                sensor, matched by its NAME (column 0) whatever the order;
%%                column 1, the calibration stamp, is not compared; column 2,
%%                the reading in K, within 0.05 %.
%%
%% point-cloud    '##! point-cloud limit=0.5 constraint={...}': the step
%%                response as points (t, T). Every point lies within 0.5 of a
%%                point of the GOOD file ('limit'), AND every point keeps the
%%                envelope stated in the region ('constraint') -- the GOOD's
%%                points, too, so a GOOD that breaks its envelope is refused.
%%
%% ignore         '##! ignore': a picture for the human eye. One noisy sample
%%                moves a star; the picture's presence is compared, its
%%                contents are not.
%%
%% units          '((settle: 150 s))' is a quantity; the law says 'settle <= 4
%%                min' and the comparison converts. A temperature DIFFERENCE is
%%                printed in K, never in degC (an offset unit).
%%
%% string law     '((verdict: "settled"))' binds a string; 'verdict ==
%%                'settled'' judges it.
%%
%% test-level     the three laws stand ONCE, in the header's own 'tolerance',
%% tolerance      and hold for both choices.
%%
%% CHOICES  heat  20 degC -> 40 degC.
%%          cool  40 degC -> 20 degC.
%%_____________________________________________________________________________
-mode(compile).

-define(DT_S,         1.0).            % simulation step
-define(DURATION_S,   400).            % simulated time, in steps
-define(SAMPLE_S,     20).             % one point of the cloud every 20 s
-define(BAND_K,       0.3).            % 'settled' = within 0.3 K of the setpoint
-define(NOISE_K,      0.02).           % sensor noise, one sigma
-define(TAU_S,        300.0).          % the plant
-define(RATE_K_PER_S, 0.15).
-define(KP,           0.6).            % the controller
-define(KI,           0.01).

%% Offset of each sensor against the air in the middle of the chamber.
-define(SENSOR_OFFSETS, [{"top", 0.10}, {"middle", 0.00}, {"bottom", -0.10}, {"door", -0.40}]).

%% RETURN: never; the VM halts with 0 after the report of the choice 'Argv'
%%         names and '<hwut-end>'; with 1, naming the choices, else.
main(Argv) ->
    case Argv of
        ["heat" | _] -> run(20.0, 40.0);
        ["cool" | _] -> run(40.0, 20.0);
        _            -> io:format("choices: heat, cool~n"), halt(1)
    end,
    io:format("<hwut-end>~n").

%% RETURN: string, the configuration as loaded, YAML, without a final newline.
config_text() ->
    lists:flatten(io_lib:format(
        "chamber:~n"
        "  plant:~n"
        "    time_constant_s: ~b~n"
        "    heater_rate_K_per_s: ~s~n"
        "  controller:~n"
        "    kind: PI~n"
        "    kp: ~s~n"
        "    ki: ~s~n"
        "    output: [-1.0, 1.0]~n"
        "  sensors: [top, middle, bottom, door]",
        [round(?TAU_S)] ++ [float_to_list(X, [short]) || X <- [?RATE_K_PER_S, ?KP, ?KI]])).

%% RETURN: float, a sample of the sensor noise.
noise() -> ?NOISE_K * rand:normal().

%% RETURN: [{T_s, Measured_C}], one sample per simulation step, T_s an
%%         integer, of the chamber driven from 'Start' to 'Setpoint' by the
%%         PI controller of 'config_text()', with sensor noise.
step_response(Start, Setpoint) ->
    step_response(0, Start, 0.0, Setpoint, []).

%% RETURN: as 'step_response/2', from step 'T' at temperature 'Temp' and the
%%         controller's 'Integral', 'Samples' so far (reversed).
step_response(T, _Temp, _Integral, _Setpoint, Samples) when T > ?DURATION_S ->
    lists:reverse(Samples);
step_response(T, Temp, Integral, Setpoint, Samples) ->
    Ambient  = 20.0,
    Measured = Temp + noise(),
    Error    = Setpoint - Measured,
    Output0  = ?KP * Error + ?KI * Integral,
    %% anti-windup: integrate only while unsaturated
    Integral1 = if Output0 > -1.0, Output0 < 1.0 -> Integral + Error * ?DT_S;
                   true                          -> Integral
                end,
    Output   = max(-1.0, min(1.0, Output0)),
    Temp1    = Temp + ?DT_S * ((Ambient - Temp) / ?TAU_S + ?RATE_K_PER_S * Output),
    step_response(T + 1, Temp1, Integral1, Setpoint, [{T, Measured} | Samples]).

%% RETURN: float, how far in K the chamber went past 'Setpoint' in the
%%         direction of travel from 'Start'; 0.0 where it never did.
overshoot_k(Samples, Start, Setpoint) ->
    Sign = if Setpoint > Start -> 1.0; true -> -1.0 end,
    max(0.0, lists:max([Sign * (Temp - Setpoint) || {_, Temp} <- Samples])).

%% RETURN: integer, the time in s after which every sample stays within
%%         BAND_K of 'Setpoint' (the step after the last one outside).
settle_s(Samples, Setpoint) ->
    case [T || {T, Temp} <- Samples, abs(Temp - Setpoint) > ?BAND_K] of
        []      -> 0;
        Outside -> lists:last(Outside) + round(?DT_S)
    end.

%% RETURN: ok; prints the configuration as loaded, byte for byte.
print_config() ->
    io:format("configuration, as loaded (YAML: whitespace is meaning):~n"),
    io:format("##! verbatim~n"),
    io:format("~s~n", [config_text()]),
    io:format("####~n").

%% RETURN: ok; prints one row per sensor, in a random order, with today's
%%         calibration stamp and the reading at the end in K.
print_sensors(Setpoint) ->
    io:format("sensors at the end, in K (the order is the bus's):~n"),
    io:format("    sensor  calibrated           reading_K~n"),
    io:format("##! table key=0 ignore=1 numeric={2:0.0005}~n"),
    Shuffled = [S || {_, S} <- lists:sort([{rand:uniform(), S} || S <- ?SENSOR_OFFSETS])],
    {{Y, Mo, D}, {H, Mi, S}} = calendar:local_time(),
    Stamp = io_lib:format("~4..0b-~2..0b-~2..0bT~2..0b:~2..0b:~2..0b", [Y, Mo, D, H, Mi, S]),
    [io:format("    ~-6s  ~s  ~9.2f~n", [Name, Stamp, Setpoint + Offset + noise() + 273.15])
     || {Name, Offset} <- Shuffled],
    io:format("####~n").

%% RETURN: ok; prints the step response, one point (t_s, T_degC) every
%%         SAMPLE_S, framed with the envelope the requirement allows.
print_cloud(Samples, Start, Setpoint) ->
    {Low, High} = if Setpoint > Start -> {Start, Setpoint + 0.5};
                     true             -> {Setpoint - 0.5, Start}
                  end,
    %% 0.1 K beyond the envelope on either side: the sensor's noise.
    io:format("step response, t in s against T in degC; envelope ~.1f .. ~.1f:~n", [Low, High]),
    io:format("##! point-cloud limit=0.5 constraint={y >= ~.1f and y <= ~.1f}~n",
              [Low - 0.1, High + 0.1]),
    [io:format("    ~5b  ~6.2f~n", [T, Temp]) || {T, Temp} <- Samples, T rem ?SAMPLE_S == 0],
    io:format("####~n").

%% RETURN: ok; prints the step response as stars, for the human eye only:
%%         one row per 40 s, one column per 0.5 K.
print_picture(Samples, Start, Setpoint) ->
    Low = min(Start, Setpoint) - 1.0,
    io:format("the same, as a picture ('|' the setpoint):~n"),
    io:format("##! ignore~n"),
    Put = fun(I, C, Row) -> lists:sublist(Row, I) ++ [C] ++ lists:nthtail(I + 1, Row) end,
    [begin
         Row0 = Put(round((Setpoint - Low) / 0.5), $|, lists:duplicate(46, $\s)),
         Row  = Put(max(0, min(45, round((Temp - Low) / 0.5))), $*, Row0),
         io:format("    ~4b s  ~s~n", [T, string:trim(Row, trailing)])
     end || {T, Temp} <- Samples, T rem 40 == 0],
    io:format("####~n").

%% RETURN: ok; drives the chamber and prints every part of the report.
run(Start, Setpoint) ->
    Samples = step_response(Start, Setpoint),
    io:format("## climate chamber, ~b degC -> ~b degC, one sample per second~n",
              [round(Start), round(Setpoint)]),
    io:format("## '##' lines are for the reader: the comparison skips them.~n"),
    print_config(),
    print_sensors(Setpoint),
    print_cloud(Samples, Start, Setpoint),
    print_picture(Samples, Start, Setpoint),
    io:format("overshoot  ((overshoot: ~.2f K))          law <= 0.5 K~n",
              [overshoot_k(Samples, Start, Setpoint)]),
    io:format("settled    ((settle: ~b s))             law <= 4 min~n", [settle_s(Samples, Setpoint)]),
    {_, Last} = lists:last(Samples),
    Verdict = case abs(Last - Setpoint) =< ?BAND_K of true -> "settled"; false -> "drifting" end,
    io:format("chamber    ((verdict: \"~s\"))~n", [Verdict]).
