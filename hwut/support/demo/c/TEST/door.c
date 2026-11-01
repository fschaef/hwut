/* @hwut {
 *     title   = "Demo: a door's state machine, watched by a pype"
 *     build   { framework = "make", executable = "%.exe" }
 *     pype    = "door.pype"
 *     choices {
 *         kept   { features = ["demo-passes-on-every-run", "fsm-law-kept"] }
 *         broken { features = ["demo-passes-on-every-run", "fsm-law-broken"] }
 *     }
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
 * may do.
 *
 * The application prints its log as it happens: noise, and a line 'door:
 * <event>' for each thing the door does. It prints no '<hwut-end>': the
 * header names 'door.pype', which stands between it and the comparison and
 * closes the stream at '<eof>'.
 *
 * 'door.pype' parses the log and fires every event into a state machine
 * ('hwut_fsm'). The pype is hwut's face, a Python program whatever language
 * the application is written in: it is the Python demo's, unchanged.
 *
 *     closed ---( open )---> open ---( close )---> closed
 *     closed ---( lock )---> locked ---( unlock )---> closed
 *     open   ---( slam )---> jammed          # forbidden
 *
 * kept     the door does what the model allows; the report shows which
 *          transitions were taken and which not, and 'ended in closed'.
 * broken   the controller locks an open door, slams it into a jam and
 *          tries to unlock it: each surprise is ONE 'BREACH' line in the
 *          output, the jam included, and the end outside the final states
 *          is one more. The GOOD file holds them and a run that stops
 *          breaching -- or breaches differently -- shows up as a difference.
 *
 * Both choices pass on every run: what they print does not depend on time.
 * _____________________________________________________________________________
 */
#include <stdio.h>
#include <string.h>

static const char* const KEPT[]   = { "open", "close", "lock", "unlock", "open", "close", NULL };
static const char* const BROKEN[] = { "open", "lock", "slam", "unlock", NULL };

static int
story(const char* const* event_list)
/* RETURN: int, 0 -- the log of the door for one story, printed. */
{
    int number;
    printf("controller 2.1 up\n");
    for(number = 1; event_list[number - 1]; ++number) {
        printf("tick %d: sensors read\n", number);
        printf("door: %s\n", event_list[number - 1]);
    }
    printf("controller down\n");
    return 0;
}

int
main(int argc, char** argv)
/* RETURN: int, 0 -- the log of the door for the choice, printed;
 *         1, no choice or an unknown one (the choices are named).           */
{
    if( argc == 2 && strcmp(argv[1], "kept")   == 0 ) return story(KEPT);
    if( argc == 2 && strcmp(argv[1], "broken") == 0 ) return story(BROKEN);
    printf("error: a choice is required: broken, kept\n");
    return 1;
}
