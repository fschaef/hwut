#! /usr/bin/env bash
#
# @hwut {
#     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
#     tolerance { constraints = ["overshoot <= 0.5 K",
#                                "settle <= 4 min",
#                                "verdict == 'settled'"] }
#     choices {
#         heat { features = ["region-verbatim", "region-table", "region-point-cloud",
#                            "region-ignore", "laws-in-units", "string-binding",
#                            "test-level-tolerance", "annotation-lines"] }
#         cool { features = ["region-verbatim", "region-table", "region-point-cloud",
#                            "region-ignore", "laws-in-units", "string-binding",
#                            "test-level-tolerance", "annotation-lines"] }
#     }
# }
#
#______________________________________________________________________________
# SUBJECT  a climate chamber driven from one temperature to another by a PI
#          controller: its configuration, its sensors at the end, its step
#          response, and the three numbers its requirement names.
# REQUIREMENT  The chamber reaches the setpoint within 4 minutes, overshoots
#              it by no more than 0.5 K, and reports itself 'settled'.
#
# 'chamber.py' of the Python demonstration, in bash: what each part of the
# output shows -- '##' notes, '##! verbatim', '##! table', '##! point-cloud',
# '##! ignore', units, a string law, a test-level tolerance -- is said there.
# BASH HAS NO FLOAT: the plant, the controller and the noise are simulated
# in awk (POSIX), seeded per run; bash prints the configuration and the
# calibration stamp.
#
# CHOICES  heat  20 degC -> 40 degC.
#          cool  40 degC -> 20 degC.
#______________________________________________________________________________

CONFIG_TEXT='chamber:
  plant:
    time_constant_s: 300
    heater_rate_K_per_s: 0.15
  controller:
    kind: PI
    kp: 0.6
    ki: 0.01
    output: [-1.0, 1.0]
  sensors: [top, middle, bottom, door]'

print_config() {
    #  RETURN: 0; prints the configuration as loaded, byte for byte.
    echo "configuration, as loaded (YAML: whitespace is meaning):"
    echo "##! verbatim"
    echo "$CONFIG_TEXT"
    echo "####"
}

simulated() {
    #  RETURN: 0; prints, from the chamber driven from '$1' to '$2' degC
    #          with noise seeded by '$3': the sensor rows (stamped '$4'),
    #          the step response as a point cloud, its picture, and the
    #          three bound numbers.
    awk -v start="$1" -v setpoint="$2" -v seed="$3" -v stamp="$4" '
        function gauss(sigma) {
            return sigma * sqrt(-2 * log(1 - rand())) * cos(6.283185307179586 * rand())
        }
        function clip(x) { return x < -1 ? -1 : (x > 1 ? 1 : x) }
        function round(x) { return int(x + (x < 0 ? -0.5 : 0.5)) }
        BEGIN {
            srand(seed)
            DT = 1; DURATION = 400; SAMPLE = 20; BAND = 0.3; NOISE = 0.02
            TAU = 300; RATE = 0.15; KP = 0.6; KI = 0.01
            # THE STEP RESPONSE: one sample per simulation step.
            temp = start; integral = 0; n = 0
            for (t = 0; t <= DURATION; t += DT) {
                measured = temp + gauss(NOISE)
                ts[n] = t; ms[n] = measured; ++n
                error = setpoint - measured
                output = KP * error + KI * integral
                if (output > -1 && output < 1) integral += error * DT   # anti-windup
                temp += DT * ((20 - temp) / TAU + RATE * clip(output))
            }
            # THE SENSORS, in the order of the bus (a shuffle).
            split("top middle bottom door", name, " ")
            offset["top"] = 0.10; offset["middle"] = 0; offset["bottom"] = -0.10; offset["door"] = -0.40
            for (i = 4; i > 1; --i) { j = 1 + int(rand() * i); x = name[i]; name[i] = name[j]; name[j] = x }
            print "sensors at the end, in K (the order is the bus'"'"'s):"
            print "    sensor  calibrated           reading_K"
            print "##! table key=0 ignore=1 numeric={2:0.0005}"
            for (i = 1; i <= 4; ++i)
                printf "    %-6s  %s  %9.2f\n", name[i], stamp, setpoint + offset[name[i]] + gauss(NOISE) + 273.15
            print "####"
            # THE CLOUD, framed with the envelope the requirement allows.
            low = start < setpoint ? start : setpoint; high = start < setpoint ? setpoint : start
            if (setpoint > start) high += 0.5; else low -= 0.5
            printf "step response, t in s against T in degC; envelope %.1f .. %.1f:\n", low, high
            printf "##! point-cloud limit=0.5 constraint={y >= %.1f and y <= %.1f}\n", low - 0.1, high + 0.1
            for (i = 0; i < n; ++i) if (ts[i] % SAMPLE == 0) printf "    %5.0f  %6.2f\n", ts[i], ms[i]
            print "####"
            # THE PICTURE, for the human eye: a row per 40 s, a column per 0.5 K.
            low = (start < setpoint ? start : setpoint) - 1
            print "the same, as a picture ('"'"'|'"'"' the setpoint):"
            print "##! ignore"
            for (i = 0; i < n; ++i) {
                if (ts[i] % 40 != 0) continue
                for (c = 0; c < 46; ++c) row[c] = " "
                row[round((setpoint - low) / 0.5)] = "|"
                c = round((ms[i] - low) / 0.5); row[c < 0 ? 0 : (c > 45 ? 45 : c)] = "*"
                line = ""; for (c = 0; c < 46; ++c) line = line row[c]
                sub(/ +$/, "", line)
                printf "    %4.0f s  %s\n", ts[i], line
            }
            print "####"
            # THE THREE NUMBERS of the requirement.
            sign = setpoint > start ? 1 : -1; over = 0; last_out = -1
            for (i = 0; i < n; ++i) {
                d = sign * (ms[i] - setpoint); if (d > over) over = d
                d = ms[i] - setpoint; if (d < 0) d = -d
                if (d > BAND) last_out = ts[i]
            }
            settle = last_out < 0 ? 0 : last_out + DT
            d = ms[n - 1] - setpoint; if (d < 0) d = -d
            printf "overshoot  ((overshoot: %.2f K))          law <= 0.5 K\n", over
            printf "settled    ((settle: %.0f s))             law <= 4 min\n", settle
            printf "chamber    ((verdict: \"%s\"))\n", d <= BAND ? "settled" : "drifting"
        }'
}

run() {
    #  RETURN: 0; drives the chamber from '$1' to '$2' degC and prints every
    #          part of the report.
    local stamp
    printf -v stamp '%(%Y-%m-%dT%H:%M:%S)T' -1
    echo "## climate chamber, $1 degC -> $2 degC, one sample per second"
    echo "## '##' lines are for the reader: the comparison skips them."
    print_config
    simulated "$1" "$2" "$SRANDOM" "$stamp"
}

case ${1-} in
    heat) run 20 40 ;;
    cool) run 40 20 ;;
    *)    echo "choices: heat, cool"; exit 1 ;;
esac
echo "<hwut-end>"
