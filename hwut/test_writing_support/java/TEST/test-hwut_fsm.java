/* @hwut {
 *     title      = "hwut_fsm: a state machine as the test's model of the system"
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         syntax    { features = ["java-fsm"] }
 *         refused   { features = ["java-fsm"] }
 *         dfa       { features = ["java-fsm"] }
 *         nfa       { features = ["java-fsm"] }
 *         forbidden { features = ["java-fsm"] }
 *         model     { features = ["java-fsm"] }
 *         report    { features = ["java-fsm"] }
 *         masks     { features = ["java-fsm"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The Java port of 'python/TEST/test-hwut_fsm.py', choice for choice,
 *          held against its GOOD files by '.link'.
 * _____________________________________________________________________________
 */
import hwut.FsmError;
import hwut.FsmMachine;
import hwut.HwutRunner;
import hwut.PyText;

import java.util.ArrayList;
import java.util.List;

final class TestHwutFsm {
    //  THE PROTOCOL OF EVERY CHOICE: a request is waited on, granted, released;
    //  a fault while busy crashes it -- which must never happen.
    static final String PROTOCOL = "\n"
        + "    initial:   idle\n"
        + "    forbidden: crashed\n"
        + "    final:     idle\n"
        + "    idle    ---( request )---> waiting ---( grant )---> busy\n"
        + "    busy    ---( release )---> idle\n"
        + "    :       ---( fault )--->   crashed       # the state that began line 6\n"
        + "    waiting ---( cancel )---> idle\n";

    /** RETURN: nothing; the section heading is printed. */
    static void banner(String label) {
        System.out.println();
        System.out.println("--- " + label + " ---");
    }

    /** RETURN: String, a path as Python prints the tuple, 'None' for null. */
    static String path(List<String> eventList) { return eventList == null ? "None" : PyText.tupleRepr(eventList); }

    /** RETURN: nothing; models read from text and written back. */
    static void runSyntax() {
        banner("the protocol, written back");
        System.out.println(FsmMachine.fromString(PROTOCOL));
        banner("the author's form: 'state', a chain, ':', blanks around '-->'");
        System.out.println(FsmMachine.fromString("\n"
            + "        state A ---( event )---> state B\n"
            + "        :                ---(event2)---> state C ---(event) --> state D\n"
            + "        state E          # no transition yet\n"
            + "    "));
    }

    /** RETURN: nothing; each model that cannot be meant, and why. */
    static void runRefused() {
        for (String text : new String[] { "A ---( x )---> B\n: ---( x )---> C",
                                          "A ---(  )---> B",
                                          ": ---( x )---> B",
                                          "A B ---( x )---> C",
                                          "initial: A, B\nA ---( x )---> B",
                                          "forbidden: Q\nA ---( x )---> B",
                                          "# nothing but a comment" }) {
            banner(text.replace("\n", " | "));
            try {
                FsmMachine.fromString(text);
                System.out.println("accepted");
            } catch (FsmError error) {
                System.out.println("FsmError: " + error.getMessage());
            }
        }
    }

    /** RETURN: nothing; events fired, one machine. */
    static void runDfa() {
        FsmMachine m = FsmMachine.fromString(PROTOCOL);
        String[] eventList = { "request", "release", "grant", "release", "jump", "request" };
        for (int number = 1; number <= eventList.length; ++number) {
            String  event = eventList[number - 1];
            boolean moved = m.fire(event, number);
            System.out.println("    " + PyText.ljust(event, 8) + " -> " + PyText.ljust(PyText.bool(moved), 5)
                               + " now " + PyText.ljust(m.state(), 8) + " allowed: " + String.join(", ", m.allowed()));
        }
        banner("questions where it stands");
        System.out.println("can('grant')   " + PyText.bool(m.can("grant")));
        System.out.println("can('release') " + PyText.bool(m.can("release")));
        System.out.println("in_state('waiting') " + PyText.bool(m.inState("waiting")));
        List<String> step = new ArrayList<>();
        for (FsmMachine.Step s : m.trace()) step.add(PyText.str(s.where()) + ":" + s.event() + ">" + s.target());
        System.out.println("trace: " + String.join(" ", step));
    }

    /** RETURN: nothing; DFA false: several states at once. */
    static void runNfa() {
        FsmMachine m = FsmMachine.fromString("\n"
            + "        A ---( x )---> B ---( y )---> D\n"
            + "        : ---( x )---> C ---( y )---> E\n"
            + "        C ---( z )---> F\n"
            + "    ", false, "fsm", null);
        for (String event : new String[] { "x", "z", "y" }) {
            m.fire(event, "t=" + event);
            System.out.println("    after " + event + ": " + String.join(", ", m.current()));
        }
        banner("'state' asked of a set");
        m.reset(); m.fire("x");
        try {
            System.out.println(m.state());
        } catch (FsmError error) {
            System.out.println("FsmError: " + error.getMessage());
        }
    }

    /** RETURN: nothing; a forbidden state entered. */
    static void runForbidden() {
        FsmMachine m = FsmMachine.fromString(PROTOCOL);
        String[] eventList = { "request", "grant", "fault" };
        for (int number = 1; number <= eventList.length; ++number) {
            boolean moved = m.fire(eventList[number - 1], number);
            System.out.println("    " + PyText.ljust(eventList[number - 1], 8) + " -> " + PyText.bool(moved));
        }
        System.out.println("now in " + m.state() + " -- breaches: " + m.breachN());
    }

    /** RETURN: nothing; the model alone. */
    static void runModel() {
        FsmMachine m = FsmMachine.fromString(PROTOCOL + "\n    state limbo\n    limbo ---( kick )---> idle\n");
        int found = m.check();
        System.out.println("check: " + found);
        banner("path_to");
        for (String state : new String[] { "busy", "crashed", "limbo", "idle" })
            System.out.println("    " + PyText.ljust(state, 8) + " " + path(m.pathTo(state)));
        m.fire("request");
        System.out.println("    busy from now: " + path(m.pathTo("busy", "now", true)));
        System.out.println("    state_reachable('idle', start='now'): " + PyText.bool(m.stateReachable("idle", "now", true)));
    }

    /** RETURN: nothing; coverage, and an end outside the final states. */
    static void runReport() {
        FsmMachine m = FsmMachine.fromString(PROTOCOL, true, "protocol", null);
        for (String event : new String[] { "request", "grant", "release", "request", "grant" }) m.fire(event);
        int breach = m.report();
        System.out.println("report returns " + breach);
    }

    /** RETURN: nothing; the law changing while the machine runs. */
    static void runMasks() {
        FsmMachine m = FsmMachine.fromString(PROTOCOL);
        banner("'grant' disallowed in every state, since line 2");
        m.disallow("grant", null, 2);
        m.fire("request", 3);
        System.out.println("    allowed now: " + String.join(", ", m.allowed()) + " -- can('grant'): " + PyText.bool(m.can("grant")));
        m.fire("grant", 4);
        System.out.println("    path_to('busy'):               " + path(m.pathTo("busy")));
        System.out.println("    path_to('busy', masked=False): " + path(m.pathTo("busy", null, false)));
        int found = m.check();
        System.out.println("    check(): " + found);
        found = m.check(false);
        System.out.println("    check(masked=False): " + found);
        banner("allowed again; 'busy' forbidden while standing in it");
        m.allow("grant", null, 5);
        m.fire("grant", 6);
        m.forbid("busy", 7);
        m.fire("release", 8);
        m.fire("request", 9);
        m.fire("grant", 10);
        banner("permitted: 'busy', and the model's own 'crashed'");
        m.permit("busy", 11);
        m.permit("crashed", 12);
        boolean moved = m.fire("fault", 13);
        System.out.println("    fault -> " + PyText.bool(moved) + " -- now in " + m.state());
        banner("a phase: 'release' disallowed in 'busy' for a block");
        m.reset();
        m.fire("request"); m.fire("grant");
        try (FsmMachine.Phase phase = m.disallowed("release", "busy", "phase")) {
            m.fire("release", 20);
        }
        m.fire("release", 21);
        m.disallow("cancel", null, 22);
        m.report();
        banner("refused: a word the model never names");
        for (Runnable call : new Runnable[] { () -> m.disallow("jump"), () -> m.forbid("limbo"),
                                              () -> m.allow("grant", "nowhere", null) }) {
            try {
                call.run();
            } catch (FsmError error) {
                System.out.println("FsmError: " + error.getMessage());
            }
        }
    }

    public static void main(String[] args) {
        new HwutRunner(args, "hwut_fsm: a state machine as the test's model of the system")
            .choice("syntax",    TestHwutFsm::runSyntax)
            .choice("refused",   TestHwutFsm::runRefused)
            .choice("dfa",       TestHwutFsm::runDfa)
            .choice("nfa",       TestHwutFsm::runNfa)
            .choice("forbidden", TestHwutFsm::runForbidden)
            .choice("model",     TestHwutFsm::runModel)
            .choice("report",    TestHwutFsm::runReport)
            .choice("masks",     TestHwutFsm::runMasks)
            .run();
    }
}
