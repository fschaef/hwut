#! /usr/bin/env bash
#
# @hwut {
#     title   = "Demo: a door's state machine, watched by a pype"
#     pype    = "door.pype"
#     choices {
#         kept   { features = ["demo-bash", "demo-bash+cover-fsm-law-kept"] }
#         broken { features = ["demo-bash", "demo-bash+cover-fsm-law-broken"] }
#     }
# }
#
#______________________________________________________________________________
# A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
# may do. 'door.py' of the Python demonstration, in bash.
#
# The application prints its log as it happens: noise, and a line 'door:
# <event>' for each thing the door does. It prints no '<hwut-end>': the
# header names 'door.pype', which stands between it and the comparison and
# closes the stream at '<eof>'.
#
# 'door.pype' parses the log and fires every event into a state machine.
# A pype's actions are Python -- the pype is hwut's face, not a library of
# the test -- so the machine there is Python's 'hwut_fsm'; the bash port's
# 'hwut_fsm.sh' is the same model for a bash test that fires events itself.
#
#     closed ---( open )---> open ---( close )---> closed
#     closed ---( lock )---> locked ---( unlock )---> closed
#     open   ---( slam )---> jammed          # forbidden
#
# kept     the door does what the model allows; the report shows which
#          transitions were taken and which not, and 'ended in closed'.
# broken   the controller locks an open door, slams it into a jam and tries
#          to unlock it: each surprise is ONE 'BREACH' line, and the end
#          outside the final states one more. The GOOD file holds them.
#
# Both choices pass on every run: what they print does not depend on time.
#______________________________________________________________________________
declare -A STORY_MAP=([kept]="open close lock unlock open close"
                      [broken]="open lock slam unlock")

main() {
    #  RETURN: 0; the log of the door for choice '$1', printed.
    local number=0 event
    echo "controller 2.1 up"
    for event in ${STORY_MAP[$1]}; do
        echo "tick $(( ++number )): sensors read"
        echo "door: $event"
    done
    echo "controller down"
}

if (( $# != 1 )) || [[ -z ${STORY_MAP[$1]+x} ]]; then
    echo "error: a choice is required: broken, kept"
    exit 1
fi
main "$1"
