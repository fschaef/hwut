-- @hwut {
--     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
--     build     { framework = "make", target = "%.exe" }
--     tolerance { constraints = ["overshoot <= 0.5 K",
--                                "settle <= 4 min",
--                                "verdict == 'settled'"] }
--     choices {
--         heat { features = ["region-verbatim", "region-table", "region-point-cloud",
--                            "region-ignore", "laws-in-units", "string-binding",
--                            "test-level-tolerance", "annotation-lines"] }
--         cool { features = ["region-verbatim", "region-table", "region-point-cloud",
--                            "region-ignore", "laws-in-units", "string-binding",
--                            "test-level-tolerance", "annotation-lines"] }
--     }
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
-- SUBJECT  a climate chamber driven from one temperature to another by a PI
--          controller: its configuration, its sensors at the end, its step
--          response, and the three numbers its requirement names.
-- REQUIREMENT  The chamber reaches the setpoint within 4 minutes, overshoots
--              it by no more than 0.5 K, and reports itself 'settled'.
--
-- Every run is seeded by the clock: the sensors are noisy, the four sensor
-- rows come out in a different order, the calibration stamps are today's.
-- Both choices pass on every run anyway; how each part of the output does
-- -- '##' notes, '##! verbatim', '##! table', '##! point-cloud', '##!
-- ignore', a law in units, a string law, the header's one 'tolerance' for
-- both choices -- the Python demonstration says ('../../python/TEST/
-- chamber.py'): it is the comparison's, not the language's.
--
-- CHOICES  heat  20 degC -> 40 degC.
--          cool  40 degC -> 20 degC.
-- _____________________________________________________________________________
library ieee;
use ieee.math_real.all;
use std.textio.all;
use work.hwut_vhpi.all;
use work.hwut_pytext.all;
use work.demo_vhpi.all;

entity chamber is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := ""; HERE : string := ".");
end entity;

architecture test of chamber is
    constant DT_S         : real    := 1.0;      -- simulation step
    constant DURATION_S   : natural := 400;      -- simulated time
    constant SAMPLE_S     : natural := 20;       -- one point of the cloud every 20 s
    constant BAND_K       : real    := 0.3;      -- 'settled' = within 0.3 K of the setpoint
    constant NOISE_K      : real    := 0.02;     -- sensor noise, one sigma
    constant TAU_S        : real    := 300.0;    -- the plant
    constant RATE_K_PER_S : real    := 0.15;
    constant KP           : real    := 0.6;      -- the controller
    constant KI           : real    := 0.01;

    constant CONFIG_TEXT : str_list :=
        "chamber:" & LF &
        "  plant:" & LF &
        "    time_constant_s: 300" & LF &
        "    heater_rate_K_per_s: 0.15" & LF &
        "  controller:" & LF &
        "    kind: PI" & LF &
        "    kp: 0.6" & LF &
        "    ki: 0.01" & LF &
        "    output: [-1.0, 1.0]" & LF &
        "  sensors: [top, middle, bottom, door]" & LF;

    --  Each sensor and its offset against the air in the middle of the chamber.
    constant SENSOR_NAME : str_list := "top" & LF & "middle" & LF & "bottom" & LF & "door" & LF;
    type real_vector is array (natural range <>) of real;
    constant SENSOR_OFFSET : real_vector(0 to 3) := (0.10, 0.00, -0.10, -0.40);

    subtype Samples is real_vector(0 to DURATION_S);   -- the measurement at t = index s

    shared variable rng : ClockRandom;

    impure function step_response(start_C : real; setpoint_C : real) return Samples is
        -- RETURN: Samples, the measured temperature at every simulation step
        --         of the chamber driven from 'start_C' to 'setpoint_C' by the
        --         PI controller of CONFIG_TEXT, with sensor noise.
        constant ambient : real := 20.0;
        variable temp     : real := start_C;
        variable integral : real := 0.0;
        variable measured, error, output : real;
        variable sample   : Samples;
    begin
        for t in 0 to DURATION_S loop
            measured  := temp + rng.gauss(0.0, NOISE_K);
            sample(t) := measured;
            error     := setpoint_C - measured;
            output    := KP * error + KI * integral;
            if -1.0 < output and output < 1.0 then          -- anti-windup: integrate
                integral := integral + error * DT_S;        -- only while unsaturated
            end if;
            output := maximum(-1.0, minimum(1.0, output));
            temp   := temp + DT_S * ((ambient - temp) / TAU_S + RATE_K_PER_S * output);
        end loop;
        return sample;
    end function;

    function overshoot_K(sample : Samples; start_C : real; setpoint_C : real) return real is
        -- RETURN: real, how far in K the chamber went past 'setpoint_C' in the
        --         direction of travel from 'start_C'; 0.0 where it never did.
        variable sign : real := 1.0;
        variable over : real := 0.0;
    begin
        if setpoint_C < start_C then sign := -1.0; end if;
        for t in sample'range loop over := maximum(over, sign * (sample(t) - setpoint_C)); end loop;
        return over;
    end function;

    function settle_s(sample : Samples; setpoint_C : real) return real is
        -- RETURN: real, the time in s after which every sample stays within
        --         BAND_K of 'setpoint_C' (the step after the last one outside).
        variable last : real := -1.0;
    begin
        for t in sample'range loop
            if abs(sample(t) - setpoint_C) > BAND_K then last := real(t); end if;
        end loop;
        if last < 0.0 then return 0.0; end if;
        return last + DT_S;
    end function;

    procedure print_config is
        -- RETURN: nothing; prints the configuration as loaded, byte for byte.
    begin
        print("configuration, as loaded (YAML: whitespace is meaning):");
        print("##! verbatim");
        for i in 0 to item_n(CONFIG_TEXT) - 1 loop print(item(CONFIG_TEXT, i)); end loop;
        print("####");
    end procedure;

    procedure print_sensors(setpoint_C : real) is
        -- RETURN: nothing; prints one row per sensor, in a random order, with
        --         today's calibration stamp and the reading at the end in K.
        constant order : integer_vector(0 to 3) := rng.permutation(4);
        constant now   : string := stamp;
        variable reading : real;
    begin
        print("sensors at the end, in K (the order is the bus's):");
        print("    sensor  calibrated           reading_K");
        print("##! table key=0 ignore=1 numeric={2:0.0005}");
        for i in order'range loop
            reading := setpoint_C + SENSOR_OFFSET(order(i)) + rng.gauss(0.0, NOISE_K) + 273.15;
            print("    " & ljust(item(SENSOR_NAME, order(i)), 6) & "  " & now & "  " & to_string(reading, "%9.2f"));
        end loop;
        print("####");
    end procedure;

    procedure print_cloud(sample : Samples; start_C : real; setpoint_C : real) is
        -- RETURN: nothing; prints the step response, one point (t_s, T_degC)
        --         every SAMPLE_S, framed with the envelope the requirement
        --         allows.
        variable low  : real := minimum(start_C, setpoint_C);
        variable high : real := maximum(start_C, setpoint_C);
    begin
        if setpoint_C > start_C then high := high + 0.5;
        else                         low  := low  - 0.5;
        end if;
        --  0.1 K beyond the envelope on either side: the sensor's noise.
        print("step response, t in s against T in degC; envelope " & to_string(low, "%.1f")
              & " .. " & to_string(high, "%.1f") & ":");
        print("##! point-cloud limit=0.5 constraint={y >= " & to_string(low - 0.1, "%.1f")
              & " and y <= " & to_string(high + 0.1, "%.1f") & "}");
        for t in sample'range loop
            if t mod SAMPLE_S = 0 then
                print("    " & to_string(real(t), "%5.0f") & "  " & to_string(sample(t), "%6.2f"));
            end if;
        end loop;
        print("####");
    end procedure;

    procedure print_picture(sample : Samples; start_C : real; setpoint_C : real) is
        -- RETURN: nothing; prints the step response as stars, for the human
        --         eye only: one row per 40 s, one column per 0.5 K.
        constant low : real := minimum(start_C, setpoint_C) - 1.0;
        variable row : string(1 to 46);
        variable n   : natural;
    begin
        print("the same, as a picture ('|' the setpoint):");
        print("##! ignore");
        for t in sample'range loop
            if t mod 40 = 0 then
                row := (others => ' ');
                row(1 + integer(round((setpoint_C - low) / 0.5))) := '|';
                row(1 + maximum(0, minimum(45, integer(round((sample(t) - low) / 0.5))))) := '*';
                n := row'length;
                while n > 0 and row(n) = ' ' loop n := n - 1; end loop;
                print("    " & to_string(real(t), "%4.0f") & " s  " & row(1 to n));
            end if;
        end loop;
        print("####");
    end procedure;

    procedure run(start_C : real; setpoint_C : real) is
        -- RETURN: nothing; drives the chamber and prints every part of the
        --         report.
        constant sample : Samples := step_response(start_C, setpoint_C);
        variable verdict : line := new string'("drifting");
    begin
        print("## climate chamber, " & to_string(start_C, "%.0f") & " degC -> " & to_string(setpoint_C, "%.0f")
              & " degC, one sample per second");
        print("## '##' lines are for the reader: the comparison skips them.");
        print_config;
        print_sensors(setpoint_C);
        print_cloud(sample, start_C, setpoint_C);
        print_picture(sample, start_C, setpoint_C);
        print("overshoot  ((overshoot: " & to_string(overshoot_K(sample, start_C, setpoint_C), "%.2f")
              & " K))          law <= 0.5 K");
        print("settled    ((settle: " & to_string(settle_s(sample, setpoint_C), "%.0f")
              & " s))             law <= 4 min");
        if abs(sample(DURATION_S) - setpoint_C) <= BAND_K then verdict := new string'("settled"); end if;
        print("chamber    ((verdict: """ & verdict.all & """))");
    end procedure;
begin
    main : process
        constant choice : string := HWUT_ARGV1;
    begin
        rng.init;
        if    choice = "heat" then run(20.0, 40.0);
        elsif choice = "cool" then run(40.0, 20.0);
        else
            print("choices: heat, cool");
            process_exit(1);
        end if;
        print("<hwut-end>");
        wait;
    end process;
end architecture;
