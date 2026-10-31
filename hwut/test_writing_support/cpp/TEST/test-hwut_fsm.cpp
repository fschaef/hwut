/* @hwut {
 *     title      = "hwut_fsm: a state machine as the test's model of the system"
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         syntax    { features = ["cpp-fsm"] }
 *         refused   { features = ["cpp-fsm"] }
 *         dfa       { features = ["cpp-fsm"] }
 *         nfa       { features = ["cpp-fsm"] }
 *         forbidden { features = ["cpp-fsm"] }
 *         model     { features = ["cpp-fsm"] }
 *         report    { features = ["cpp-fsm"] }
 *         masks     { features = ["cpp-fsm"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The C++ port of 'python/TEST/test-hwut_fsm.py', choice for choice,
 *          held against its GOOD files by '.link'. What Python prints of its
 *          own values -- True, None, a tuple -- is printed so here by
 *          'hwut::pytext', since the GOOD file is one; an FsmError is caught
 *          and printed as Python's test prints it.
 * _____________________________________________________________________________
 */
#include <cstdio>
#include <string>
#include <vector>
#include "hwut_runner.hpp"
#include "hwut_pytext.hpp"
#include "hwut_fsm.hpp"

using hwut::fsm::Machine;
using hwut::pytext::repr;
using hwut::pytext::tuple_repr;

static const std::string PROTOCOL =
    "\n"
    "    initial:   idle\n"
    "    forbidden: crashed\n"
    "    final:     idle\n"
    "    idle    ---( request )---> waiting ---( grant )---> busy\n"
    "    busy    ---( release )---> idle\n"
    "    :       ---( fault )--->   crashed       # the state that began line 6\n"
    "    waiting ---( cancel )---> idle\n";

static void banner(const std::string& label) { std::printf("\n--- %s ---\n", label.c_str()); }

static std::string
join(const std::vector<std::string>& list)
/* RETURN: the texts of 'list' joined by ', '.                              */
{
    std::string result;
    for(size_t i = 0; i < list.size(); ++i) result += (i ? ", " : "") + list[i];
    return result;
}

static std::string
path_text(const std::optional<std::vector<std::string>>& path)
/* RETURN: the path as Python prints the tuple 'path_to' returns --
 *         "('request', 'grant')", "('grant',)", "()" -- 'None' where none. */
{ return path ? tuple_repr(*path) : "None"; }

static void say(const hwut::FsmError& error) { std::printf("FsmError: %s\n", error.what()); }

/* ------------------------------------------------------------------ syntax */
static void
run_syntax()
{
    banner("the protocol, written back");
    std::printf("%s\n", Machine::from_string(PROTOCOL).to_string().c_str());
    banner("the author's form: 'state', a chain, ':', blanks around '-->'");
    std::printf("%s\n", Machine::from_string("\n"
        "        state A ---( event )---> state B\n"
        "        :                ---(event2)---> state C ---(event) --> state D\n"
        "        state E          # no transition yet\n").to_string().c_str());
}

static void
run_refused()
{
    static const std::vector<std::string> text_list = {
        "A ---( x )---> B\n: ---( x )---> C",
        "A ---(  )---> B",
        ": ---( x )---> B",
        "A B ---( x )---> C",
        "initial: A, B\nA ---( x )---> B",
        "forbidden: Q\nA ---( x )---> B",
        "# nothing but a comment",
    };
    for(const std::string& text : text_list) {
        std::string label;
        for(char c : text) label += c == '\n' ? std::string(" | ") : std::string(1, c);
        banner(label);
        try                                 { Machine::from_string(text); std::printf("accepted\n"); }
        catch( const hwut::FsmError& error ) { say(error); }
    }
}

/* ------------------------------------------------------------------- runs */
static void
run_dfa()
{
    Machine m = Machine::from_string(PROTOCOL);
    int     line = 1;
    for(const char* event : { "request", "release", "grant", "release", "jump", "request" }) {
        bool moved = m.fire(event, line++);
        std::printf("    %-8s -> %-5s now %-8s allowed: %s\n", event, repr(moved).c_str(),
                    m.state().c_str(), join(m.allowed()).c_str());
    }
    banner("questions where it stands");
    std::printf("can('grant')   %s\n", repr(m.can("grant")).c_str());
    std::printf("can('release') %s\n", repr(m.can("release")).c_str());
    std::printf("in_state('waiting') %s\n", repr(m.in_state("waiting")).c_str());
    std::printf("trace:");
    for(const auto& t : m.trace())
        std::printf(" %s:%s>%s", t.where.value_or("None").c_str(), t.event.c_str(), t.target.c_str());
    std::printf("\n");
}

static void
run_nfa()
{
    Machine m = Machine::from_string("\n"
        "        A ---( x )---> B ---( y )---> D\n"
        "        : ---( x )---> C ---( y )---> E\n"
        "        C ---( z )---> F\n", /* DFA */ false);
    for(std::string event : { "x", "z", "y" }) {
        m.fire(event, "t=" + event);
        std::printf("    after %s: %s\n", event.c_str(), join(m.current()).c_str());
    }
    banner("'state' asked of a set");
    m.reset();
    m.fire("x");
    try                                 { std::printf("%s\n", m.state().c_str()); }
    catch( const hwut::FsmError& error ) { say(error); }
}

static void
run_forbidden()
{
    Machine m = Machine::from_string(PROTOCOL);
    int     line = 1;
    for(const char* event : { "request", "grant", "fault" }) {
        bool moved = m.fire(event, line++);
        std::printf("    %-8s -> %s\n", event, repr(moved).c_str());
    }
    std::printf("now in %s -- breaches: %d\n", m.state().c_str(), m.breach_n());
}

/* ------------------------------------------------------- the model alone */
static void
run_model()
{
    Machine m = Machine::from_string(PROTOCOL + "\n    state limbo\n    limbo ---( kick )---> idle\n");
    { int n = m.check(); std::printf("check: %d\n", n); }
    banner("path_to");
    for(const char* goal : { "busy", "crashed", "limbo", "idle" })
        std::printf("    %-8s %s\n", goal, path_text(m.path_to(goal)).c_str());
    m.fire("request");
    std::printf("    busy from now: %s\n", path_text(m.path_to("busy", "now")).c_str());
    std::printf("    state_reachable('idle', start='now'): %s\n", repr(m.state_reachable("idle", "now")).c_str());
}

static void
run_report()
{
    Machine m = Machine::from_string(PROTOCOL, true, "protocol");
    for(const char* event : { "request", "grant", "release", "request", "grant" }) m.fire(event);
    int breach_n = m.report();
    std::printf("report returns %d\n", breach_n);
}

/* ------------------------------------------------------------------ masks */
static void
run_masks()
{
    Machine m = Machine::from_string(PROTOCOL);

    banner("'grant' disallowed in every state, since line 2");
    m.disallow("grant", std::nullopt, 2);
    m.fire("request", 3);
    std::printf("    allowed now: %s -- can('grant'): ", join(m.allowed()).c_str());
    std::printf("%s\n", repr(m.can("grant")).c_str());
    m.fire("grant", 4);
    std::printf("    path_to('busy'):               %s\n", path_text(m.path_to("busy")).c_str());
    std::printf("    path_to('busy', masked=False): %s\n", path_text(m.path_to("busy", std::nullopt, false)).c_str());
    { int n = m.check();      std::printf("    check(): %d\n", n); }
    { int n = m.check(false); std::printf("    check(masked=False): %d\n", n); }

    banner("allowed again; 'busy' forbidden while standing in it");
    m.allow("grant");
    m.fire("grant", 6);
    m.forbid("busy", 7);
    m.fire("release", 8);
    m.fire("request", 9);
    m.fire("grant", 10);

    banner("permitted: 'busy', and the model's own 'crashed'");
    m.permit("busy", 11);
    m.permit("crashed", 12);
    bool fault = m.fire("fault", 13);
    std::printf("    fault -> %s -- now in %s\n", repr(fault).c_str(), m.state().c_str());

    banner("a phase: 'release' disallowed in 'busy' for a block");
    m.reset();
    m.fire("request"); m.fire("grant");
    {
        auto phase = m.disallowed("release", "busy", "phase");
        m.fire("release", 20);
    }
    m.fire("release", 21);
    m.disallow("cancel", std::nullopt, 22);
    m.report();

    banner("refused: a word the model never names");
    try { m.disallow("jump");         } catch( const hwut::FsmError& error ) { say(error); }
    try { m.forbid("limbo");          } catch( const hwut::FsmError& error ) { say(error); }
    try { m.allow("grant", "nowhere"); } catch( const hwut::FsmError& error ) { say(error); }
}

int
main(int argc, char** argv)
{
    hwut::HwutRunner runner(argc, argv, "hwut_fsm: a state machine as the test's model of the system", {
        { "syntax", run_syntax }, { "refused", run_refused }, { "dfa", run_dfa }, { "nfa", run_nfa },
        { "forbidden", run_forbidden }, { "model", run_model }, { "report", run_report },
        { "masks", run_masks },
    });
    return runner.run();
}
