#! /usr/bin/env python3
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
"""
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
______________________________________________________________________________
"""
import random
import sys
import time

DT_S         = 1.0                 # simulation step
DURATION_S   = 400                 # simulated time
SAMPLE_S     = 20                  # one point of the cloud every 20 s
BAND_K       = 0.3                 # 'settled' = within 0.3 K of the setpoint
NOISE_K      = 0.02                # sensor noise, one sigma
TAU_S, RATE_K_PER_S = 300.0, 0.15  # the plant
KP, KI       = 0.6, 0.01           # the controller

CONFIG_TEXT = """\
chamber:
  plant:
    time_constant_s: %.0f
    heater_rate_K_per_s: %s
  controller:
    kind: PI
    kp: %s
    ki: %s
    output: [-1.0, 1.0]
  sensors: [top, middle, bottom, door]""" % (TAU_S, RATE_K_PER_S, KP, KI)

#  Offset of each sensor against the air in the middle of the chamber.
SENSOR_OFFSET_DB = {"top": +0.10, "middle": 0.00, "bottom": -0.10, "door": -0.40}


def step_response(start_C, setpoint_C, rng):
    """
    RETURN: list of (t_s, measured_C), one sample per simulation step, of the
            chamber driven from 'start_C' to 'setpoint_C' by the PI
            controller of CONFIG_TEXT, with sensor noise drawn from 'rng'.
    """
    tau, rate, kp, ki = TAU_S, RATE_K_PER_S, KP, KI
    ambient  = 20.0
    temp     = start_C
    integral = 0.0
    sample_list = []
    t = 0.0
    while t <= DURATION_S:
        measured = temp + rng.gauss(0.0, NOISE_K)
        sample_list.append((t, measured))
        error = setpoint_C - measured
        output = kp * error + ki * integral
        if -1.0 < output < 1.0:                     # anti-windup: integrate
            integral += error * DT_S                # only while unsaturated
        output = max(-1.0, min(1.0, output))
        temp += DT_S * ((ambient - temp) / tau + rate * output)
        t += DT_S
    return sample_list


def overshoot_K(sample_list, start_C, setpoint_C):
    """
    RETURN: float, how far in K the chamber went past 'setpoint_C' in the
            direction of travel from 'start_C'; 0.0 where it never did.
    """
    sign = 1.0 if setpoint_C > start_C else -1.0
    return max(0.0, max(sign * (temp - setpoint_C) for _, temp in sample_list))


def settle_s(sample_list, setpoint_C):
    """
    RETURN: float, the time in s after which every sample stays within
            BAND_K of 'setpoint_C' (the step after the last one outside).
    """
    outside = [t for t, temp in sample_list if abs(temp - setpoint_C) > BAND_K]
    return outside[-1] + DT_S if outside else 0.0


def print_config():
    """RETURN: None. Prints the configuration as loaded, byte for byte."""
    print("configuration, as loaded (YAML: whitespace is meaning):")
    print("##! verbatim")
    print(CONFIG_TEXT)
    print("####")


def print_sensors(setpoint_C, rng):
    """
    RETURN: None. Prints one row per sensor, in a random order, with
            today's calibration stamp and the reading at the end in K.
    """
    print("sensors at the end, in K (the order is the bus's):")
    print("    sensor  calibrated           reading_K")
    print("##! table key=0 ignore=1 numeric={2:0.0005}")
    name_list = list(SENSOR_OFFSET_DB)
    rng.shuffle(name_list)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    for name in name_list:
        reading = setpoint_C + SENSOR_OFFSET_DB[name] + rng.gauss(0.0, NOISE_K) + 273.15
        print("    %-6s  %s  %9.2f" % (name, stamp, reading))
    print("####")


def print_cloud(sample_list, start_C, setpoint_C):
    """
    RETURN: None. Prints the step response, one point (t_s, T_degC) every
            SAMPLE_S, framed with the envelope the requirement allows.
    """
    low, high = sorted((start_C, setpoint_C))
    if setpoint_C > start_C: high += 0.5
    else:                    low  -= 0.5
    #  0.1 K beyond the envelope on either side: the sensor's noise.
    print("step response, t in s against T in degC; envelope %.1f .. %.1f:" % (low, high))
    print("##! point-cloud limit=0.5 constraint={y >= %.1f and y <= %.1f}" % (low - 0.1, high + 0.1))
    for t, temp in sample_list:
        if t % SAMPLE_S == 0:
            print("    %5.0f  %6.2f" % (t, temp))
    print("####")


def print_picture(sample_list, start_C, setpoint_C):
    """
    RETURN: None. Prints the step response as stars, for the human eye only:
            one row per 40 s, one column per 0.5 K.
    """
    low = min(start_C, setpoint_C) - 1.0
    print("the same, as a picture ('|' the setpoint):")
    print("##! ignore")
    for t, temp in sample_list:
        if t % 40 == 0:
            row = [" "] * 46
            row[int(round((setpoint_C - low) / 0.5))] = "|"
            row[max(0, min(45, int(round((temp - low) / 0.5))))] = "*"
            print("    %4.0f s  %s" % (t, "".join(row).rstrip()))
    print("####")


def run(start_C, setpoint_C):
    """RETURN: None. Drives the chamber and prints every part of the report."""
    rng = random.Random(time.time_ns())
    sample_list = step_response(start_C, setpoint_C, rng)
    print("## climate chamber, %.0f degC -> %.0f degC, one sample per second" % (start_C, setpoint_C))
    print("## '##' lines are for the reader: the comparison skips them.")
    print_config()
    print_sensors(setpoint_C, rng)
    print_cloud(sample_list, start_C, setpoint_C)
    print_picture(sample_list, start_C, setpoint_C)
    over   = overshoot_K(sample_list, start_C, setpoint_C)
    settle = settle_s(sample_list, setpoint_C)
    print("overshoot  ((overshoot: %.2f K))          law <= 0.5 K" % over)
    print("settled    ((settle: %.0f s))             law <= 4 min" % settle)
    verdict = "settled" if abs(sample_list[-1][1] - setpoint_C) <= BAND_K else "drifting"
    print("chamber    ((verdict: \"%s\"))" % verdict)


CHOICE_DB = {"heat": (20.0, 40.0),
             "cool": (40.0, 20.0)}

choice = sys.argv[1] if len(sys.argv) > 1 else ""
if choice not in CHOICE_DB:
    print("choices: %s" % ", ".join(CHOICE_DB))
    sys.exit(1)
run(*CHOICE_DB[choice])
print("<hwut-end>")
