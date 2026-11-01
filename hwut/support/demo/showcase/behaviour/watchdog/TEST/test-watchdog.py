#! /usr/bin/env python3
# @hwut {
#     title    = "Windowed watchdog: reset exactly when the task stops kicking, or kicks too soon"
#     features = ["reset-on-silence"]
#     choices {
#         healthy     { features = ["no-reset-while-kicked"]
#                       tolerance { constraints = ["deviations == 0", "silence <= 300 ms"] } }
#         slow-but-ok { features = ["no-reset-while-kicked"]
#                       tolerance { constraints = ["deviations == 0", "silence <= 300 ms"] } }
#         stalled     { tolerance { constraints = ["deviations == 0", "silence <= 300 ms"] } }
#         early-kick  { features = ["window"]
#                       tolerance { constraints = ["deviations == 0", "silence <= 300 ms"] } }
#         u8-stalled  { features = ["missed-reset-named"]
#                       tolerance { constraints = ["deviations > 0", "silence > 300 ms"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the kick/count/reset timeline of the watchdog under one kick
         schedule, and the reset it performed against the one specified
REQUIREMENT  The watchdog resets the MCU at the very millisecond the task
             has not kicked for the timeout (300 ms), and never while the
             task kicks in time. With a window (60 ms), a kick sooner than
             the window after the previous kick resets too.

The unit is C ('../wdt.c'), driven by '../sim.c' on a simulated 1 ms clock:
the timer interrupt ticks, the task kicks at the times the scenario lists.
Simulated time makes the picture exact and the test instant -- a real-time
version of this would take a second per choice and could only bound the
reset time, never pin it.

The TIMELINE, one column per 10 ms:
    kick    'K' where the task kicked
    count   time since the last kick, in tenths of the timeout: 0..9, and
            '!' past the timeout -- a sawtooth that must never show '!'
            without an 'R' right there
    reset   'R' where the watchdog reset the MCU
The GOOD states the scale of the count row under the picture. Under it,
the reset the SPECIFICATION predicts (computed here from the kick times, by
the rule above) against the reset the unit performed, and their difference
bound as '((deviations: N))' (0 or 1). Last, the longest time the MCU ran
without a kick (up to the reset, or to the end) as a QUANTITY,
'((silence: 300 ms))': the purpose of a watchdog in its own unit -- no
kick for 300 ms, and the MCU runs no further.

healthy      kicks every 100 ms: the count saws 0..3, no reset.
slow-but-ok  gaps up to 290 ms: the count reaches 9, no reset.
stalled      the task hangs after 400 ms: reset at exactly 700 ms.
early-kick   window 60 ms, a kick 30 ms after the previous: reset at once.
u8-stalled   the BROKEN FIXTURE '../wdt_u8.c' (8-bit counter) under
             'stalled': the count wraps at 255 ms and never reaches 300.
             The GOOD file shows '!!!' in the count row with no 'R', and
             the '!!' line naming the missed reset.

HWUT CONCEPTS  The timeline stands in '##! verbatim' (columns are time).
Deterministic by construction (simulated clock): no tolerance at all. The
constraint bindings carry the verdict into hwut's own judgment:
'deviations == 0' and 'silence <= 300 ms' for the lawful choices (the
comparison converts: a 'silence' printed as '0.301 s' breaks it, a bare
number breaks it too), 'deviations > 0' and 'silence > 300 ms' for
u8-stalled,
so 'hwut.accept' refuses a re-recording in which the unit leaves the
specification, and a u8 fixture that no longer shows the missed reset. A
reviewer checks that every '!' run ends in an 'R' and reads the last lines:
predicted against performed.
______________________________________________________________________________
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
TIMEOUT, END, COLUMN_MS = 300, 1000, 10

CHOICE_DB = {   # unit, window, kick times
    "healthy":     ("wdt.c",    0,  list(range(100, 1001, 100))),
    "slow-but-ok": ("wdt.c",    0,  [100, 300, 590, 880]),
    "stalled":     ("wdt.c",    0,  [100, 200, 300, 400]),
    "early-kick":  ("wdt.c",    60, [100, 200, 230, 330]),
    "u8-stalled":  ("wdt_u8.c", 0,  [100, 200, 300, 400]),
}


def run_unit(unit, window, kick_list):
    with tempfile.TemporaryDirectory() as build:
        exe = os.path.join(build, "sim")
        subprocess.check_call(["gcc", "-Wall", "-Werror", "-I", UNIT, "-o", exe,
                               os.path.join(UNIT, "sim.c"), os.path.join(UNIT, unit)])
        out = subprocess.run([exe, str(TIMEOUT), str(window), str(END)], capture_output=True,
                             text=True, check=True, input=" ".join(map(str, kick_list))).stdout
    return [line.split() for line in out.splitlines()]


def predict(window, kick_list):
    """THE SPECIFICATION. RETURN: (reset time or None, reason)."""
    last = 0
    for t in kick_list:
        if last + TIMEOUT <= t:
            return last + TIMEOUT, "timeout"
        if window and t - last < window:
            return t, "early-kick"
        last = t
    return (last + TIMEOUT, "timeout") if last + TIMEOUT <= END else (None, "")


def main(choice):
    unit, window, kick_list = CHOICE_DB[choice]
    event_list = run_unit(unit, window, kick_list)
    kicked = [int(e[1]) for e in event_list if e[0] == "KICK"]
    reset = [(int(e[1]), e[2]) for e in event_list if e[0] == "RESET"]
    stop = reset[0][0] if reset else END

    ruler, kick_row, count_row, reset_row = "", "", "", ""
    last = 0
    for col in range(END // COLUMN_MS + 1):
        t = col * COLUMN_MS
        if col % 10 == 0:
            ruler += str(t).ljust(10)
        here = [k for k in kicked if t - COLUMN_MS < k <= t]
        if here:
            last = here[-1]
        if t > stop:
            kick_row += " "; count_row += " "; reset_row += " "
            continue
        kick_row += "K" if here else "."
        elapsed = t - last
        count_row += "!" if elapsed >= TIMEOUT else str(elapsed * 10 // TIMEOUT)
        reset_row += "R" if reset and reset[0][0] // COLUMN_MS == col else "."

    print("unit:     %s, timeout %d ms, window %s" % (unit, TIMEOUT, "%d ms (a kick sooner than %d ms after the previous one resets)" % (window, window) if window else "off"))
    print("kicks at: %s ms" % " ".join(map(str, kick_list)))
    print()
    print("##! verbatim")
    shown = len(kick_row.rstrip())
    print("ms      %s" % ruler[:shown].rstrip())
    print("kick    %s" % kick_row.rstrip())
    print("count   %s" % count_row.rstrip())
    print("reset   %s" % reset_row.rstrip())
    print("####")
    print("(one column per %d ms; K a kick, R the reset; count: time since the last kick in tenths of the" % COLUMN_MS)
    print(" %d ms timeout, 0 = under %d ms ... 9 = under %d ms, '!' = timeout reached)"
          % (TIMEOUT, TIMEOUT // 10, TIMEOUT))
    print()
    expect_t, expect_why = predict(window, kick_list)
    why = expect_why
    if expect_why == "early-kick":
        prev = max(k for k in kick_list if k < expect_t)
        why = "early-kick: %d - %d = %d ms < %d ms" % (expect_t, prev, expect_t - prev, window)
    elif expect_why == "timeout":
        why = "timeout: no kick since %d ms" % (expect_t - TIMEOUT)
    print("specification: %s" % ("reset at %d ms (%s)" % (expect_t, why) if expect_t else "no reset"))
    print("watchdog:      %s" % ("reset at %d ms (%s)" % reset[0] if reset else "no reset"))
    deviation_n = 0
    if (expect_t, expect_why) == (reset[0] if reset else (None, "")):
        print("verdict:       as specified")
    elif expect_t and not reset:
        print("verdict:       !! MISSED RESET: no kick for %d ms, the MCU runs on" % (END - kicked[-1]))
        deviation_n = 1
    else:
        print("verdict:       !! the watchdog differs from the specification")
        deviation_n = 1
    print("deviations:    ((deviations: %d))   law == 0   %s" % (deviation_n, "kept" if not deviation_n else "BROKEN"))
    marks = [0] + [k for k in kick_list if k < stop] + [stop]
    silence = max(b - a for a, b in zip(marks, marks[1:]))
    print("longest time without a kick: ((silence: %d ms))   law <= %d ms   %s"
          % (silence, TIMEOUT, "kept" if silence <= TIMEOUT else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
