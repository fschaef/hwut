#! /usr/bin/env python3
#
# @hwut {
#     title   = "Demo: a door's state machine, watched by a pype"
#     pype    = "door.pype"
#     choices {
#         kept   { features = ["demo-passes-on-every-run", "fsm-law-kept"] }
#         broken { features = ["demo-passes-on-every-run", "fsm-law-broken"] }
#     }
# }
#
"""
______________________________________________________________________________
A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
may do.

The application prints its log as it happens: noise, and a line 'door:
<event>' for each thing the door does. It prints no '<hwut-end>': the
header names 'door.pype', which stands between it and the comparison and
closes the stream at '<eof>'.

'door.pype' parses the log and fires every event into a state machine
('hwut_fsm', test_writing_support/python):

    closed ---( open )---> open ---( close )---> closed
    closed ---( lock )---> locked ---( unlock )---> closed
    open   ---( slam )---> jammed          # forbidden

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
"""
import sys

STORY_DB = {
    "kept":   ["open", "close", "lock", "unlock", "open", "close"],
    "broken": ["open", "lock", "slam", "unlock"],
}


def main(choice):
    """RETURN: int, 0 -- the log of the door for 'choice', printed."""
    print("controller 2.1 up")
    for number, event in enumerate(STORY_DB[choice], start=1):
        print("tick %d: sensors read" % number)
        print("door: %s" % event)
    print("controller down")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in STORY_DB:
        print("error: a choice is required: %s" % ", ".join(sorted(STORY_DB)))
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
