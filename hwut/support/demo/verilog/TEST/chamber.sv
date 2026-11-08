// @hwut {
//     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
//     build     { framework = "make", target = "%.exe"
//                 caps { memory_mb = 2048  file_size_mb = 256  disk_mb = 1024 } }
//     tolerance { constraints = ["overshoot <= 0.5 K",
//                                "settle <= 4 min",
//                                "verdict == 'settled'"] }
//     choices {
//         heat { features = ["region-verbatim", "region-table", "region-point-cloud",
//                            "region-ignore", "laws-in-units", "string-binding",
//                            "test-level-tolerance", "annotation-lines"] }
//         cool { features = ["region-verbatim", "region-table", "region-point-cloud",
//                            "region-ignore", "laws-in-units", "string-binding",
//                            "test-level-tolerance", "annotation-lines"] }
//     }
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// SUBJECT  a climate chamber driven from one temperature to another by a PI
//          controller: its configuration, its sensors at the end, its step
//          response, and the three numbers its requirement names.
// REQUIREMENT  The chamber reaches the setpoint within 4 minutes, overshoots
//              it by no more than 0.5 K, and reports itself 'settled'.
//
// Every run is seeded anew: the sensors are noisy, the four sensor rows come
// out in a different order, the calibration stamps are today's (UTC: the
// simulation reads the time of the world from '/proc'). Both choices pass on
// every run anyway; each part of the output says how:
//
// '##' lines     notes for the reader. The comparison skips them on both
//                sides, anywhere -- even inside a region.
//
// verbatim       '##! verbatim' ... '####': the configuration as loaded. It
//                is YAML, where indentation is meaning, so nothing is
//                tolerated: no whitespace folding, no numeric band.
//
// table          '##! table key=0 ignore=1 numeric={2:0.0005}': one row per
//                sensor, matched by its NAME (column 0) whatever the order;
//                column 1, the calibration stamp, is not compared; column 2,
//                the reading in K, within 0.05 %.
//
// point-cloud    '##! point-cloud limit=0.5 constraint={...}': the step
//                response as points (t, T). Every point lies within 0.5 of a
//                point of the GOOD file ('limit'), AND every point keeps the
//                envelope stated in the region ('constraint') -- the GOOD's
//                points, too, so a GOOD that breaks its envelope is refused.
//
// ignore         '##! ignore': a picture for the human eye. One noisy sample
//                moves a star; the picture's presence is compared, its
//                contents are not.
//
// units          '((settle: 150 s))' is a quantity; the law says 'settle <=
//                4 min' and the comparison converts. A temperature
//                DIFFERENCE is printed in K, never in degC (an offset unit).
//
// string law     '((verdict: "settled"))' binds a string; 'verdict ==
//                'settled'' judges it.
//
// test-level     the three laws stand ONCE, in the header's own 'tolerance',
// tolerance      and hold for both choices.
//
// CHOICES  heat  20 degC -> 40 degC.
//          cool  40 degC -> 20 degC.
// _____________________________________________________________________________
import hwut_runner::*;
import hwut_pytext::*;
import deterministic_random::*;

localparam real DT_S         = 1.0;      // simulation step
localparam real DURATION_S   = 400.0;    // simulated time
localparam int  SAMPLE_S     = 20;       // one point of the cloud every 20 s
localparam real BAND_K       = 0.3;      // 'settled' = within 0.3 K of the setpoint
localparam real NOISE_K      = 0.02;     // sensor noise, one sigma
localparam real TAU_S        = 300.0;    // the plant
localparam real RATE_K_PER_S = 0.15;
localparam real KP           = 0.6;      // the controller
localparam real KI           = 0.01;

class Chamber;
    DeterministicStream rng;
    real   sample_t[$];
    real   sample_temp[$];
    string sensor_name[$];
    real   sensor_offset[$];        // against the air in the middle

    function new();
        // RETURN: a chamber whose noise is seeded by 64 bits of
        //         '/dev/urandom'.
        longint seed = 0;
        int     fd;
        fd = $fopen("/dev/urandom", "rb");
        if (fd != 0) begin void'($fread(seed, fd)); $fclose(fd); end
        seed = (seed ^ (seed >> 31)) & 'h7FFFFFFF;
        rng = new(seed == 0 ? 1 : seed);
        sensor_name.push_back("top");    sensor_offset.push_back(+0.10);
        sensor_name.push_back("middle"); sensor_offset.push_back( 0.00);
        sensor_name.push_back("bottom"); sensor_offset.push_back(-0.10);
        sensor_name.push_back("door");   sensor_offset.push_back(-0.40);
    endfunction

    function string config_text();
        // RETURN: the configuration, YAML, as loaded -- its lines '\n'-joined.
        return {"chamber:\n",
                "  plant:\n",
                $sformatf("    time_constant_s: %.0f\n", TAU_S),
                "    heater_rate_K_per_s: ", float_repr(RATE_K_PER_S), "\n",
                "  controller:\n",
                "    kind: PI\n",
                "    kp: ", float_repr(KP), "\n",
                "    ki: ", float_repr(KI), "\n",
                "    output: [-1.0, 1.0]\n",
                "  sensors: [top, middle, bottom, door]"};
    endfunction

    function void step_response(real start_C, real setpoint_C);
        // RETURN: nothing; 'sample_t'/'sample_temp' hold one sample (t_s,
        //         measured_C) per simulation step of the chamber driven from
        //         'start_C' to 'setpoint_C' by the PI controller, with sensor
        //         noise drawn.
        real ambient = 20.0, temp = start_C, integral = 0.0, t = 0.0;
        real measured, error, output_;
        sample_t = {};
        sample_temp = {};
        while (t <= DURATION_S) begin
            measured = temp + rng.gauss(0.0, NOISE_K);
            sample_t.push_back(t);
            sample_temp.push_back(measured);
            error   = setpoint_C - measured;
            output_ = KP * error + KI * integral;
            if (output_ > -1.0 && output_ < 1.0)        // anti-windup: integrate
                integral += error * DT_S;               // only while unsaturated
            if (output_ > 1.0)  output_ = 1.0;
            if (output_ < -1.0) output_ = -1.0;
            temp += DT_S * ((ambient - temp) / TAU_S + RATE_K_PER_S * output_);
            t    += DT_S;
        end
    endfunction

    function real overshoot_K(real start_C, real setpoint_C);
        // RETURN: how far in K the chamber went past 'setpoint_C' in the
        //         direction of travel from 'start_C'; 0.0 where it never did.
        real sign_ = setpoint_C > start_C ? 1.0 : -1.0;
        real over  = 0.0;
        foreach (sample_temp[i]) if (sign_ * (sample_temp[i] - setpoint_C) > over)
            over = sign_ * (sample_temp[i] - setpoint_C);
        return over;
    endfunction

    function real settle_s(real setpoint_C);
        // RETURN: the time in s after which every sample stays within BAND_K
        //         of 'setpoint_C' (the step after the last one outside); 0.0
        //         where none is outside.
        real last = -1.0;
        foreach (sample_temp[i]) begin
            real d = sample_temp[i] - setpoint_C;
            if (d > BAND_K || -d > BAND_K) last = sample_t[i];
        end
        return last < 0.0 ? 0.0 : last + DT_S;
    endfunction

    function string stamp();
        // RETURN: now, UTC, as 'YYYY-MM-DDTHH:MM:SS' -- the boot time of
        //         '/proc/stat' plus the uptime of '/proc/uptime'; the epoch
        //         where they cannot be read.
        longint epoch = 0, day, second, era, doe, yoe, doy, mp, y, m, d;
        real    uptime = 0.0;
        string  line;
        int     fd, got;
        fd = $fopen("/proc/stat", "r");
        //  '$fgets' stands as a statement of its own: as the condition of a
        //  'while' Verilator 5.020 dropped it here (RATIONALE DEMO-VERILOG-3).
        if (fd != 0) begin
            forever begin
                got = $fgets(line, fd);
                if (got == 0) break;
                if (line.len() > 6 && line.substr(0, 5) == "btime ") epoch = line.substr(6, line.len() - 1).atoi();
            end
            $fclose(fd);
        end
        fd = $fopen("/proc/uptime", "r");
        if (fd != 0) begin
            got = $fgets(line, fd);
            if (got != 0) uptime = line.atoreal();
            $fclose(fd);
        end
        epoch += longint'($floor(uptime));
        day    = epoch / 86400;
        second = epoch % 86400;
        //  The civil date of a day since 1970-01-01 (H. Hinnant's algorithm).
        day += 719468;
        era  = day / 146097;
        doe  = day - era * 146097;
        yoe  = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
        y    = yoe + era * 400;
        doy  = doe - (365 * yoe + yoe / 4 - yoe / 100);
        mp   = (5 * doy + 2) / 153;
        d    = doy - (153 * mp + 2) / 5 + 1;
        m    = mp < 10 ? mp + 3 : mp - 9;
        if (m <= 2) y += 1;
        return $sformatf("%04d-%02d-%02dT%02d:%02d:%02d", y, m, d,
                         second / 3600, (second / 60) % 60, second % 60);
    endfunction

    function void print_config();
        // RETURN: nothing; the configuration as loaded was printed, byte for
        //         byte.
        $display("configuration, as loaded (YAML: whitespace is meaning):");
        $display("##! verbatim");
        $display("%s", config_text());
        $display("####");
    endfunction

    function void print_sensors(real setpoint_C);
        // RETURN: nothing; one row per sensor was printed, in a drawn order,
        //         with today's calibration stamp and the reading at the end
        //         in K.
        int    order[$] = {};
        string now;
        now = stamp();
        $display("sensors at the end, in K (the order is the bus's):");
        $display("    sensor  calibrated           reading_K");
        $display("##! table key=0 ignore=1 numeric={2:0.0005}");
        rng.sample_indices(sensor_name.size(), sensor_name.size(), order);
        foreach (order[k]) begin
            int  i = order[k];
            real reading = setpoint_C + sensor_offset[i] + rng.gauss(0.0, NOISE_K) + 273.15;
            $display("    %s  %s  %9.2f", padded(sensor_name[i], 6), now, reading);
        end
        $display("####");
    endfunction

    function void print_cloud(real start_C, real setpoint_C);
        // RETURN: nothing; the step response was printed, one point (t_s,
        //         T_degC) every SAMPLE_S, framed with the envelope the
        //         requirement allows.
        real low  = start_C < setpoint_C ? start_C : setpoint_C;
        real high = start_C < setpoint_C ? setpoint_C : start_C;
        if (setpoint_C > start_C) high += 0.5;
        else                      low  -= 0.5;
        //  0.1 K beyond the envelope on either side: the sensor's noise.
        $display("step response, t in s against T in degC; envelope %.1f .. %.1f:", low, high);
        $display("##! point-cloud limit=0.5 constraint={y >= %.1f and y <= %.1f}", low - 0.1, high + 0.1);
        foreach (sample_t[i]) if (longint'(sample_t[i]) % SAMPLE_S == 0)
            $display("    %5.0f  %6.2f", sample_t[i], sample_temp[i]);
        $display("####");
    endfunction

    function void print_picture(real start_C, real setpoint_C);
        // RETURN: nothing; the step response was printed as stars, for the
        //         human eye only: one row per 40 s, one column per 0.5 K.
        real low = (start_C < setpoint_C ? start_C : setpoint_C) - 1.0;
        $display("the same, as a picture ('|' the setpoint):");
        $display("##! ignore");
        foreach (sample_t[i]) if (longint'(sample_t[i]) % 40 == 0) begin
            string row = "";
            int    bar  = int'($floor((setpoint_C - low) / 0.5 + 0.5));
            int    star = int'($floor((sample_temp[i] - low) / 0.5 + 0.5));
            int    end_ = bar > star ? bar : star;
            if (star < 0)  star = 0;
            if (star > 45) star = 45;
            end_ = bar > star ? bar : star;
            for (int c = 0; c <= end_; c++)
                row = {row, c == star ? string'("*") : c == bar ? string'("|") : string'(" ")};
            $display("    %4.0f s  %s", sample_t[i], row);
        end
        $display("####");
    endfunction

    function void run(real start_C, real setpoint_C);
        // RETURN: nothing; the chamber was driven and every part of the report
        //         printed.
        real   over, settle, last;
        string verdict;
        step_response(start_C, setpoint_C);
        $display("## climate chamber, %.0f degC -> %.0f degC, one sample per second", start_C, setpoint_C);
        $display("## '##' lines are for the reader: the comparison skips them.");
        print_config();
        print_sensors(setpoint_C);
        print_cloud(start_C, setpoint_C);
        print_picture(start_C, setpoint_C);
        over   = overshoot_K(start_C, setpoint_C);
        settle = settle_s(setpoint_C);
        $display("overshoot  ((overshoot: %.2f K))          law <= 0.5 K", over);
        $display("settled    ((settle: %.0f s))             law <= 4 min", settle);
        last    = sample_temp[sample_temp.size() - 1] - setpoint_C;
        verdict = (last <= BAND_K && -last <= BAND_K) ? "settled" : "drifting";
        $display("chamber    ((verdict: \"%s\"))", verdict);
    endfunction
endclass

module chamber;
    initial begin
        Chamber c = new();
        string  choice = hwut_sv_argc() > 1 ? hwut_sv_argv(1) : "";
        case (choice)
            "heat":  c.run(20.0, 40.0);
            "cool":  c.run(40.0, 20.0);
            default: begin
                $display("choices: heat, cool");
                exit_(1);
            end
        endcase
        $display("<hwut-end>");
        exit_(0);
    end
endmodule
