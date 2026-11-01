// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: A state machine as a test's model -- see 'hwut_fsm.hpp'.
// _____________________________________________________________________________
#include "hwut_fsm.hpp"

#include <cstring>

using namespace hwut::c;

namespace hwut {
namespace fsm {

namespace {

const size_t LIST_MAX = 4096;               // more states or events than any model has

std::vector<const char*>
c_list(const std::vector<std::string>& list)
/* RETURN: the C texts of 'list', in order.                                 */
{
    std::vector<const char*> result;
    for(const auto& s : list) result.push_back(s.c_str());
    return result;
}

std::vector<std::string>
texts(const char** list, size_t n)
/* RETURN: the first 'n' texts of 'list' (at most LIST_MAX), in order.      */
{ return std::vector<std::string>(list, list + (n < LIST_MAX ? n : LIST_MAX)); }

const char* c_state(const State& state) { return state ? state->c_str() : nullptr; }

void
write_through(void* context, const char* line)
/* RETURN: nothing; 'line' went to the machine's 'write' function.          */
{ (*static_cast<Write*>(context))(line); }

} // namespace

Machine::Machine(c::FsmMachine* machine, Write write)
/* RETURN: Machine owning 'machine', writing through 'write' (stdout where
 *         none).                                                           */
    : machine_(machine)
{ attach(std::move(write)); }

void
Machine::attach(Write write)
/* RETURN: nothing; every line the machine writes goes through 'write' -- the
 *         C default (stdout) where 'write' is empty.                       */
{
    if( ! write ) return;
    write_.reset(new Write(std::move(write)));
    machine_->write         = write_through;
    machine_->write_context = write_.get();
}

void
Machine::refused_if(int result)
/* RETURN: nothing where 'result' is 0 or more; throws FsmError with the
 *         machine's error text where it is negative.                      */
{ if( result < 0 ) throw FsmError(machine_->error); }

Machine::Machine(const std::vector<Transition>& transitions, const std::string& initial,
                 const std::vector<std::string>& forbidden, const std::vector<std::string>& final,
                 bool DFA, const std::string& name, Write write, const std::vector<std::string>& states)
/* RETURN: Machine, standing in 'initial'; throws FsmError where the model
 *         cannot be meant -- a DFA with two targets for one (state, event);
 *         a forbidden or final state no transition names.                  */
{
    char                       error[FSM_ERROR_MAX] = "";
    std::vector<FsmTransition> c_transition;
    for(const auto& t : transitions)
        c_transition.push_back({ std::get<0>(t).c_str(), std::get<1>(t).c_str(), std::get<2>(t).c_str() });
    auto c_forbidden = c_list(forbidden), c_final = c_list(final), c_states = c_list(states);
    c::FsmMachine* m = FsmMachine_new(c_transition.data(), c_transition.size(), initial.c_str(),
                                     c_forbidden.data(), c_forbidden.size(), c_final.data(), c_final.size(),
                                     DFA, name.c_str(), c_states.data(), c_states.size(), error, sizeof(error));
    if( ! m ) throw FsmError(error);
    machine_.reset(m);
    attach(std::move(write));
}

Machine
Machine::from_string(const std::string& text, bool DFA, const std::string& name, Write write)
/* RETURN: Machine, the model 'text' states; throws FsmError where it cannot
 *         be meant, naming the line. One statement per line, '#' a comment:
 *         'initial:', 'forbidden:', 'final:', 'state A',
 *         'A ---( ev )---> B ---( ev2 )---> C', ':' for the state that began
 *         the line above.                                                  */
{
    char          error[FSM_ERROR_MAX] = "";
    c::FsmMachine* m = FsmMachine_from_string(text.c_str(), DFA, name.c_str(), error, sizeof(error));
    if( ! m ) throw FsmError(error);
    return Machine(m, std::move(write));
}

std::string
Machine::to_string()
/* RETURN: the model in the text 'from_string' reads, one transition per
 *         line, sorted.                                                    */
{
    for(size_t size = 4096; ; size *= 2) {
        std::string buffer(size, '\0');
        FsmMachine_to_string(machine_.get(), &buffer[0], size);
        size_t n = std::strlen(buffer.c_str());
        if( n + 1 < size ) return buffer.substr(0, n);
    }
}

void
Machine::reset()
/* RETURN: nothing; the machine stands in its initial state again, under the
 *         model as written: what was seen, every mask and every state
 *         forbidden or permitted since are forgotten.                      */
{ FsmMachine_reset(machine_.get()); }

bool
Machine::fire(const std::string& event, const Where& where)
/* RETURN: true, 'event' moved the machine and entered no forbidden state;
 *         false, it was not allowed where the machine stands -- a BREACH
 *         line is written and the machine stays -- or it entered a
 *         forbidden state, which is written too.                          */
{ return FsmMachine_fire(machine_.get(), event.c_str(), where.c()) > 0; }

void
Machine::disallow(const std::string& event, const State& state, const Where& where)
/* RETURN: nothing; from now on 'event' is a breach -- in 'state' alone, in
 *         every state where nullopt -- until 'allow'. Throws FsmError where
 *         the model names no such event or state.                         */
{ refused_if(FsmMachine_disallow(machine_.get(), event.c_str(), c_state(state), where.c())); }

void
Machine::allow(const std::string& event, const State& state)
/* RETURN: nothing; the mask 'disallow(event, state)' set is lifted, a mask
 *         of another scope stays. Throws FsmError where the model names no
 *         such word.                                                       */
{ refused_if(FsmMachine_allow(machine_.get(), event.c_str(), c_state(state))); }

void
Machine::forbid(const std::string& state, const Where& where)
/* RETURN: nothing; entering 'state' is a breach from now on, until 'permit';
 *         where the machine STANDS in it, one BREACH line at once. Throws
 *         FsmError where the model names no such state.                   */
{ refused_if(FsmMachine_forbid(machine_.get(), state.c_str(), where.c())); }

void
Machine::permit(const std::string& state, const Where& where)
/* RETURN: nothing; 'state' is no longer forbidden -- a state of the model's
 *         own 'forbidden:' too, until 'forbid' again. Throws FsmError where
 *         the model names no such state.                                  */
{ refused_if(FsmMachine_permit(machine_.get(), state.c_str(), where.c())); }

Machine::Phase
Machine::disallowed(const std::string& event, const State& state, const Where& where)
/* RETURN: Phase: 'event' disallowed (see 'disallow') while it lives, allowed
 *         again when it ends -- whatever way the block is left. Throws
 *         FsmError where the model names no such word.                    */
{
    disallow(event, state, where);
    c::FsmMachine* m = machine_.get();
    return Phase([m, event, state] { FsmMachine_allow(m, event.c_str(), c_state(state)); });
}

Machine::Phase
Machine::forbidding(const std::string& state, const Where& where)
/* RETURN: Phase: 'state' forbidden (see 'forbid') while it lives, permitted
 *         again when it ends -- whatever way the block is left. Throws
 *         FsmError where the model names no such state.                   */
{
    forbid(state, where);
    c::FsmMachine* m = machine_.get();
    return Phase([m, state] { FsmMachine_permit(m, state.c_str(), nullptr); });
}

std::string
Machine::state()
/* RETURN: the one state the machine stands in; throws FsmError where it
 *         stands in a set (DFA false): ask 'current()'.                    */
{
    const char* one = FsmMachine_state(machine_.get());
    if( ! one ) throw FsmError(machine_->error);
    return one;
}

std::vector<std::string>
Machine::current()
/* RETURN: every state the machine stands in, sorted.                       */
{
    const char* list[LIST_MAX];
    return texts(list, FsmMachine_current(machine_.get(), list, LIST_MAX));
}

bool
Machine::in_state(const std::string& state)
/* RETURN: true where the machine stands in 'state'.                        */
{ return FsmMachine_in_state(machine_.get(), state.c_str()) != 0; }

bool
Machine::can(const std::string& event)
/* RETURN: true where 'event' would move the machine now.                   */
{ return FsmMachine_can(machine_.get(), event.c_str()) != 0; }

std::vector<std::string>
Machine::allowed()
/* RETURN: the events that would move the machine now, sorted.              */
{
    const char* list[LIST_MAX];
    return texts(list, FsmMachine_allowed(machine_.get(), list, LIST_MAX));
}

std::vector<TraceEntry>
Machine::trace()
/* RETURN: every transition fired, in order: (where, state, event, state).  */
{
    const FsmTraceEntry*    entry;
    size_t                  n = FsmMachine_trace(machine_.get(), &entry);
    std::vector<TraceEntry> result;
    for(size_t i = 0; i < n; ++i) {
        TraceEntry e;
        if( entry[i].where ) e.where = entry[i].where;
        e.state = entry[i].state; e.event = entry[i].event; e.target = entry[i].target;
        result.push_back(e);
    }
    return result;
}

int
Machine::breach_n()
/* RETURN: the breaches written so far.                                     */
{ return FsmMachine_breach_n(machine_.get()); }

std::optional<std::vector<std::string>>
Machine::path_to(const std::string& state, const State& start, bool masked)
/* RETURN: the shortest path of events from 'start' -- the initial state
 *         where nullopt, "now" for where the machine stands -- into
 *         'state' (empty where 'start' is 'state'); nullopt where no path
 *         leads there. Among equally short paths the first in sorted order. */
{
    const char* list[LIST_MAX];
    int         n = FsmMachine_path_to(machine_.get(), state.c_str(), c_state(start), masked, list, LIST_MAX);
    if( n < 0 ) return std::nullopt;
    return texts(list, (size_t)n);
}

bool
Machine::state_reachable(const std::string& state, const State& start, bool masked)
/* RETURN: true where 'state' can be reached from 'start' (see 'path_to').  */
{ return FsmMachine_state_reachable(machine_.get(), state.c_str(), c_state(start), masked) != 0; }

std::vector<std::string>
Machine::unreachable(bool masked)
/* RETURN: the states no path from the initial state reaches, forbidden ones
 *         left out, sorted.                                                */
{
    const char* list[LIST_MAX];
    return texts(list, FsmMachine_unreachable(machine_.get(), masked, list, LIST_MAX));
}

std::vector<std::string>
Machine::dead_ends(bool masked)
/* RETURN: the states no event leaves that are neither final nor forbidden,
 *         sorted.                                                          */
{
    const char* list[LIST_MAX];
    return texts(list, FsmMachine_dead_ends(machine_.get(), masked, list, LIST_MAX));
}

std::vector<std::string>
Machine::forbidden_reachable(bool masked)
/* RETURN: the forbidden states the model lets the system reach from the
 *         initial state, sorted.                                           */
{
    const char* list[LIST_MAX];
    return texts(list, FsmMachine_forbidden_reachable(machine_.get(), masked, list, LIST_MAX));
}

int
Machine::check(bool masked)
/* RETURN: the number of findings the MODEL has, each written as one line
 *         'MODEL: ...'; 0 where it has none.                               */
{ return FsmMachine_check(machine_.get(), masked); }

int
Machine::report()
/* RETURN: the breaches seen, counting a non-final end; the coverage report
 *         -- states, transitions, masks -- written before it.             */
{ return FsmMachine_report(machine_.get()); }

} // namespace fsm
} // namespace hwut
