// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
//          port of 'python/hwut_fsm.py' (README-hwut_fsm.txt), a thin face
//          over '../c/hwut_fsm.c'. The states it may be in, the events that
//          move it, the states it must never reach. A test FIRES the events
//          it observes; every event the model does not allow, and every
//          forbidden state entered, is WRITTEN as a line -- so it lands in the
//          GOOD file and the comparison judges it.
//
//     auto m = hwut::fsm::Machine::from_string(
//         "initial: idle\n"
//         "forbidden: crashed\n"
//         "idle ---( request )---> waiting ---( grant )---> busy\n"
//         "busy ---( release )---> idle\n"
//         ":    ---( fault )--->   crashed\n");
//     m.fire("request", 1);           -- true
//     m.fire("release", 2);           -- false; 'BREACH line 2: ...' written
//     {   auto phase = m.disallowed("release", "busy", "phase");
//         m.fire("release", 20);  }   -- Python's 'with m.disallowed(...)'
//     m.report();
//
// The same model text, the same words, the same sorted reports as Python.
// What Python raises as FsmError is thrown as hwut::FsmError, its what()
// Python's text.
//
// 'where' (a breach's place, hwut::fsm::Where): an int names a line
// ('line 3'), a text stands as written, nothing names no place.
// A state given as std::nullopt is every state (Python's 'state=None').
// 'write' takes one line; every breach and report goes through it -- stdout
// where none is given.
// _____________________________________________________________________________
#ifndef HWUT_FSM_HPP
#define HWUT_FSM_HPP

#include <functional>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/types.h>
namespace hwut { namespace c {       // the C core, out of the global namespace
extern "C" {
#include "../c/hwut_fsm.h"
}
} }

namespace hwut {

class FsmError : public std::invalid_argument {        // Python: FsmError(ValueError)
public:
    explicit FsmError(const std::string& message) : std::invalid_argument(message) {}
};

namespace fsm {

using FsmError = hwut::FsmError;

class Where {
public:
    Where() = default;
    Where(int line) : text_(std::to_string(line)) {}
    Where(const char* text) { if( text ) text_ = text; }
    Where(const std::string& text) : text_(text) {}
    const char* c() const { return text_ ? text_->c_str() : nullptr; }
private:
    std::optional<std::string> text_;
};

using State      = std::optional<std::string>;
using Write      = std::function<void(const std::string& line)>;
using Transition = std::tuple<std::string, std::string, std::string>;   // (state, event, state)

struct TraceEntry {
    std::optional<std::string> where;
    std::string                state, event, target;
};

class Machine {
public:
    class Phase;

    Machine(const std::vector<Transition>& transitions, const std::string& initial,
            const std::vector<std::string>& forbidden = {}, const std::vector<std::string>& final = {},
            bool DFA = true, const std::string& name = "fsm", Write write = nullptr,
            const std::vector<std::string>& states = {});
    static Machine from_string(const std::string& text, bool DFA = true, const std::string& name = "fsm",
                               Write write = nullptr);

    std::string to_string();
    void        reset();
    bool        fire(const std::string& event, const Where& where = Where());

    void        disallow(const std::string& event, const State& state = std::nullopt, const Where& where = Where());
    void        allow(const std::string& event, const State& state = std::nullopt);
    void        forbid(const std::string& state, const Where& where = Where());
    void        permit(const std::string& state, const Where& where = Where());
    Phase       disallowed(const std::string& event, const State& state = std::nullopt, const Where& where = Where());
    Phase       forbidding(const std::string& state, const Where& where = Where());

    std::string              state();
    std::vector<std::string> current();
    bool                     in_state(const std::string& state);
    bool                     can(const std::string& event);
    std::vector<std::string> allowed();
    std::vector<TraceEntry>  trace();
    int                      breach_n();
    const char*              name() const { return machine_->name; }

    std::optional<std::vector<std::string>> path_to(const std::string& state, const State& start = std::nullopt,
                                                    bool masked = true);
    bool                     state_reachable(const std::string& state, const State& start = std::nullopt,
                                             bool masked = true);
    std::vector<std::string> unreachable(bool masked = true);
    std::vector<std::string> dead_ends(bool masked = true);
    std::vector<std::string> forbidden_reachable(bool masked = true);
    int                      check(bool masked = true);
    int                      report();

    c::FsmMachine* c() { return machine_.get(); }

    class Phase {                       // a block during which a mask or a forbidden state stands
    public:
        Phase(Phase&& other) noexcept : leave_(std::move(other.leave_)) { other.leave_ = nullptr; }
        ~Phase() { if( leave_ ) leave_(); }
    private:
        friend class Machine;
        explicit Phase(std::function<void()> leave) : leave_(std::move(leave)) {}
        std::function<void()> leave_;
    };

private:
    struct Free { void operator()(c::FsmMachine* m) const { c::FsmMachine_free(m); } };
    explicit Machine(c::FsmMachine* machine, Write write);
    void attach(Write write);
    void refused_if(int result);

    std::unique_ptr<c::FsmMachine, Free> machine_;
    std::unique_ptr<Write>              write_;         // where 'machine_->write_context' points
};

} // namespace fsm
} // namespace hwut

#endif
