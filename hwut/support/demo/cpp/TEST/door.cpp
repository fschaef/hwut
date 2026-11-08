/* @hwut {
 *     title   = "Demo: a door's state machine, watched by a pype"
 *     build   { framework = "make", target = "%.exe" }
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
 * 'door.pype' parses the log and fires every event into a state machine:
 *
 *     closed ---( open )---> open ---( close )---> closed
 *     closed ---( lock )---> locked ---( unlock )---> closed
 *     open   ---( slam )---> jammed          # forbidden
 *
 * THE MODEL LIVES IN THE PYPE, and a pype's actions are Python: 'door.pype'
 * is the Python demonstration's, unchanged, its machine Python's 'hwut_fsm'.
 * The C++ 'hwut::fsm::Machine' says the same words (its own tests hold it
 * against the same GOOD files); a C++ test that keeps its model in-process
 * uses it. Here the application is C++, the law is the pype's
 * (RATIONALE DEMO-CPP-3).
 *
 * kept     the door does what the model allows; the report shows which
 *          transitions were taken and which not, and 'ended in closed'.
 * broken   the controller locks an open door, slams it into a jam and tries
 *          to unlock it: each surprise is ONE 'BREACH' line, the end outside
 *          the final states one more. The GOOD file holds them.
 * _____________________________________________________________________________
 */
#include <cstdio>
#include <map>
#include <string>
#include <vector>

static const std::map<std::string, std::vector<std::string>> STORY = {
    { "kept",   { "open", "close", "lock", "unlock", "open", "close" } },
    { "broken", { "open", "lock", "slam", "unlock" } },
};

int main(int argc, char** argv)
/* RETURN: 0, the log of the door for the choice 'argv[1]' printed;
 *         1, where no known choice is named (the choices are printed).   */
{
    auto it = argc == 2 ? STORY.find(argv[1]) : STORY.end();
    if( it == STORY.end() ) {
        std::printf("error: a choice is required: broken, kept\n");
        return 1;
    }
    std::printf("controller 2.1 up\n");
    int number = 0;
    for(const std::string& event : it->second) {
        std::printf("tick %d: sensors read\n", ++number);
        std::printf("door: %s\n", event.c_str());
    }
    std::printf("controller down\n");
    return 0;
}
