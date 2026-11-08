/* @hwut {
 *     title   = "Demo: a door's state machine, watched by a pype"
 *     build   { framework = "make", target = "%.exe" }
 *     pype    = "door.pype"
 *     choices {
 *         kept   { features = ["demo-passes-on-every-run", "fsm-law-kept"] }
 *         broken { features = ["demo-passes-on-every-run", "fsm-law-broken"] }
 *     }
 * }
 * ______________________________________________________________________________
 * A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
 * may do.
 *
 * The application prints its log as it happens: noise, and a line 'door:
 * <event>' for each thing the door does. It prints no '<hwut-end>': the
 * header names 'door.pype', which stands between it and the comparison and
 * closes the stream at '<eof>'.
 *
 * 'door.pype' parses the log and fires every event into a state machine
 * ('hwut_fsm' -- the pype's, in Python, whatever language the door is
 * written in):
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
 * ______________________________________________________________________________
 */
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

final class Door {
    static final Map<String, List<String>> STORY_DB = new TreeMap<>(Map.of(
        "kept",   List.of("open", "close", "lock", "unlock", "open", "close"),
        "broken", List.of("open", "lock", "slam", "unlock")));

    /** RETURN: int, 0 -- the log of the door for 'choice', printed. */
    static int main(String choice) {
        System.out.println("controller 2.1 up");
        int number = 1;
        for (String event : STORY_DB.get(choice)) {
            System.out.println("tick " + number++ + ": sensors read");
            System.out.println("door: " + event);
        }
        System.out.println("controller down");
        return 0;
    }

    public static void main(String[] args) {
        if (args.length != 1 || !STORY_DB.containsKey(args[0])) {
            System.out.println("error: a choice is required: " + String.join(", ", STORY_DB.keySet()));
            System.exit(1);
        }
        System.exit(main(args[0]));
    }
}
