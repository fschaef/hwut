#! /usr/bin/env python3
# @hwut {
#     title    = "Mars Polar Lander (1999): a transient at leg deployment, latched, cuts the engine 40 m above the ground"
#     choices {
#         mpl-1999          { features = ["descent-strip", "premature-cutoff-named"]
#                             tolerance { constraints = ["stopped == 1", "cutoff > 0.5 m"] } }
#         cleared-at-enable { features = ["descent-strip", "cutoff-at-touchdown"]
#                             tolerance { constraints = ["stopped == 1", "cutoff <= 0.5 m"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  a lander's descent, reading by reading where something changes:
         altitude, the three touchdown sensors, the latched indications,
         the descent engine -- and the altitude at which the engine stops

HISTORY  Mars Polar Lander was lost on 3 December 1999 during its descent.
The failure review board named as the probable cause a spurious touchdown
signal: deploying the landing legs, at about 1500 m, could make the
Hall-effect touchdown sensors read high for a moment. The software
recorded that reading as a touchdown indication and kept it; when
touchdown sensing was enabled at about 40 m, the kept indication stopped
the descent engine at once, and the lander fell the rest of the way. The
transient was known as a property of the sensors; the software
requirement to ignore it was not carried into the code.

REQUIREMENT  The descent engine is stopped only by a touchdown indication
             -- two consecutive high readings of a leg -- that occurs
             after touchdown sensing is enabled.

THE UNIT  '../flight.py': the touchdown logic as flown (indications latched
from the start) and as fixed (latches cleared when sensing is enabled).

THE MODEL  A descent profile of the model's own, not the mission's: 40 m/s
from 1600 m to 40 m, then 2.4 m/s to the ground; sensors read every 0.1 s.
At leg deployment (1500 m) leg 2 reads high for two readings -- just long
enough to count as an indication. On the ground all three legs read high,
for three readings.

WHAT THE TEST PRINTS  The descent strip in '##! verbatim': one row per
reading at which an event happens or a sensor, a latch or the engine
changes -- time, altitude, sensors (1 = high), latches, engine. Then the
altitude at which the engine stopped and, where that is above the ground,
the speed of the fall on Mars (g = 3.71 m/s^2).

CHOICES
    mpl-1999           the leg-deployment transient is latched at 1500 m
                       and stops the engine when sensing is enabled, 40 m
                       up.
    cleared-at-enable  the latch is cleared at 40 m; the engine stops on
                       the real touchdown, at 0 m.

HOW TO READ THE GOOD  All is exact: the profile is given, not drawn.
'((stopped: 1))' says the engine stopped at all (law == 1 for both: an
engine that never stops is no fix). '((cutoff: X m))' is the altitude at which the engine stopped; law
'cutoff > 0.5 m' for the logic as flown -- its GOOD is the accepted
violation report -- and 'cutoff <= 0.5 m' for the fixed one.
______________________________________________________________________________
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import flight                                                    # noqa: E402

DT, G_MARS = 0.1, 3.71
CHOICE_DB = {"mpl-1999": flight.Lander1999, "cleared-at-enable": flight.LanderCleared}


def profile():
    """
    RETURN: list of (t in s, altitude in m), one per reading: 40 m/s down
            to 40 m, then 2.4 m/s down to the ground; three at 0 m.
    """
    sample_list, t, altitude = [], 0.0, 1600.0
    while altitude > 0.0:
        sample_list.append((round(t, 1), round(altitude, 2)))
        altitude -= (40.0 if altitude > 40.0 else 2.4) * DT
        t += DT
    for _ in range(3):                          # standing on the ground
        sample_list.append((round(t, 1), 0.0))
        t += DT
    return sample_list


def main(choice):
    """RETURN: int, 0 once the strip and the cutoff are printed."""
    lander = CHOICE_DB[choice]()
    print("touchdown logic: %s" % choice)
    print("##! verbatim")
    print("  t (s)   alt (m)   sensors  latches  engine   event")
    deployed_at = enabled_at = landed_at = None
    transient_left, cutoff, last_state = 0, None, None
    for t, altitude in profile():
        event = []
        if deployed_at is None and altitude <= 1500.0:
            deployed_at, transient_left = t, 2
            event.append("legs deployed")
        if enabled_at is None and altitude <= 40.0:
            enabled_at = t
            lander.enable_sensing()
            event.append("sensing enabled")
        sensor_list = [altitude <= 0.0, altitude <= 0.0 or transient_left > 0, altitude <= 0.0]
        if transient_left > 0:
            transient_left -= 1
            if transient_left == 1: event.append("leg 2 transient")
        engine_before = lander.engine
        lander.read(sensor_list)
        if engine_before and not lander.engine:
            cutoff = altitude
            event.append("ENGINE CUT")
        if altitude <= 0.0 and landed_at is None:
            landed_at = t
            event.append("on the ground")
        state = (tuple(sensor_list), tuple(lander.latched), lander.engine)
        if event or state != last_state:
            print("%7.1f  %8.1f   %s    %s    %-4s     %s"
                  % (t, altitude, " ".join("1" if s else "0" for s in sensor_list),
                     " ".join("L" if l else "." for l in lander.latched),
                     "on" if lander.engine else "off", ", ".join(event)))
        last_state = state
        if not lander.engine and altitude <= 0.0: break
    print("####")
    stopped = 0 if cutoff is None else 1
    print("engine stopped during the descent ((stopped: %d))   law == 1   %s"
          % (stopped, "kept" if stopped == 1 else "BROKEN"))
    if cutoff is None: return 0
    print("engine stopped at ((cutoff: %.1f m))   law <= 0.5 m   %s"
          % (cutoff, "kept" if cutoff <= 0.5 else "BROKEN"))
    if cutoff > 0.5:
        speed = math.sqrt(2.4 ** 2 + 2 * G_MARS * cutoff)
        print("free fall from %.1f m: %.1f m/s at the ground" % (cutoff, speed))
    return 0


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
