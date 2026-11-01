// @hwut {
//     title   = "Demo: a door's state machine, watched by a pype"
//     build   { framework = "make", executable = "%.exe"
//               caps { memory_mb = 2048  file_size_mb = 256  disk_mb = 1024 } }
//     pype    = "door.pype"
//     choices {
//         kept   { features = ["demo-passes-on-every-run", "fsm-law-kept"] }
//         broken { features = ["demo-passes-on-every-run", "fsm-law-broken"] }
//     }
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
// may do.
//
// The application prints its log as it happens: noise, and a line 'door:
// <event>' for each thing the door does. It prints no '<hwut-end>': the
// header names 'door.pype', which stands between it and the comparison and
// closes the stream at '<eof>'.
//
// 'door.pype' parses the log and fires every event into a state machine
// ('hwut_fsm' -- the pype's own, Python's: a pype script is Python):
//
//     closed ---( open )---> open ---( close )---> closed
//     closed ---( lock )---> locked ---( unlock )---> closed
//     open   ---( slam )---> jammed          # forbidden
//
// kept     the door does what the model allows; the report shows which
//          transitions were taken and which not, and 'ended in closed'.
// broken   the controller locks an open door, slams it into a jam and
//          tries to unlock it: each surprise is ONE 'BREACH' line in the
//          output, the jam included, and the end outside the final states
//          is one more. The GOOD file holds them and a run that stops
//          breaching -- or breaches differently -- shows up as a difference.
//
// Both choices pass on every run: what they print does not depend on time.
// _____________________________________________________________________________
import hwut_runner::*;

function automatic int main(string choice);
    // RETURN: 0, the log of the door for 'choice' printed, if 'choice' is
    //         'kept' or 'broken'; 1, else -- the choices named.
    string story[$] = {};
    case (choice)
        "kept":   begin story.push_back("open"); story.push_back("close"); story.push_back("lock");
                        story.push_back("unlock"); story.push_back("open"); story.push_back("close"); end
        "broken": begin story.push_back("open"); story.push_back("lock"); story.push_back("slam");
                        story.push_back("unlock"); end
        default: begin
            $display("error: a choice is required: broken, kept");
            return 1;
        end
    endcase
    $display("controller 2.1 up");
    foreach (story[i]) begin
        $display("tick %0d: sensors read", i + 1);
        $display("door: %s", story[i]);
    end
    $display("controller down");
    return 0;
endfunction

module door;
    initial exit_(main(hwut_sv_argc() == 2 ? hwut_sv_argv(1) : ""));
endmodule
