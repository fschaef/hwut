// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: A DETERMINISTIC EVENT DISPATCHER -- the port of
//          'python/deterministic_timeline.py', a thin face over
//          '../c/deterministic_timeline.c'. Triggers fire at the ticks their
//          timeline strings mark with a digit; within one tick the LOWER
//          digit fires first, equal digits in registration order. When the
//          last tick has passed, every trigger is told 'on_termination
//          (end_tick)', 'end_tick' being the LONGEST timeline's length.
//          'stop' leaves early and still announces; a CANCELLED task
//          announces nothing.
//
//     struct MyTrigger : hwut::Trigger {
//         MyTrigger() : hwut::Trigger("1 1 3", "SUB") {}
//         void fire(int t) override { ... }
//         void on_termination(int end_tick) override { ... }    -- optional
//     };
//     MyTrigger a, b;
//     hwut::TriggerDispatcher d({ &a, &b });
//     d.run();
//
// The base 'fire' is ABSTRACT: it throws hwut::NotImplementedError -- as
// Python raises NotImplementedError -- and so does 'run' then. Any exception
// a trigger throws leaves 'run' (or 'await', 'gather') as it was thrown.
//
// THE YIELD WITHOUT COROUTINES: a Task is a step function -- 'bool()',
// true while it has more to do; one 'step' runs it up to its next yield.
// 'd.task()' is the run as a task (one firing per step). 'gather' steps
// tasks in turn, in the order given -- the order 'asyncio.gather' gives
// them -- until each is done; 'cancel' abandons one, and 'await' on it
// throws hwut::CancelledError.
//
// A Trigger, a TriggerDispatcher and a Task stay where they were made
// (neither copied nor moved): the C core holds their addresses.
// _____________________________________________________________________________
#ifndef HWUT_DETERMINISTIC_TIMELINE_HPP
#define HWUT_DETERMINISTIC_TIMELINE_HPP

#include <cstdio>
#include <functional>
#include <initializer_list>
#include <stdexcept>
#include <string>
#include <vector>

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/types.h>
namespace hwut { namespace c {       // the C core, out of the global namespace
extern "C" {
#include "../c/deterministic_timeline.h"
}
} }

namespace hwut {

class NotImplementedError : public std::logic_error {
public:
    NotImplementedError() : std::logic_error("NotImplementedError") {}
};

class CancelledError : public std::runtime_error {
public:
    CancelledError() : std::runtime_error("CancelledError") {}
};

class Trigger {
public:
    explicit Trigger(std::string timeline, const std::string& name = "");
    virtual ~Trigger() = default;
    Trigger(const Trigger&)            = delete;
    Trigger& operator=(const Trigger&) = delete;

    virtual void fire(int pseudo_time);
    virtual void on_termination(int end_tick);

    const std::string& timeline() const { return timeline_; }
    std::string        name()     const { return shim_.base.name; }
    c::Trigger*         c()              { return &shim_.base; }

private:
    struct Shim { c::Trigger base; Trigger* owner; };
    static int  shim_fire(c::Trigger* self, int pseudo_time);
    static void shim_on_termination(c::Trigger* self, int end_tick);
    static const c::Trigger_Vtable shim_vtable;

    std::string timeline_;
    Shim        shim_;
};

class TriggerDispatcher;

class Task {
public:
    explicit Task(std::function<bool()> step);
    explicit Task(TriggerDispatcher& dispatcher);
    Task(const Task&)            = delete;
    Task& operator=(const Task&) = delete;

    bool step();
    void cancel();
    void await();
    bool done() const      { return c_.done_f != 0; }
    bool cancelled() const { return c_.cancelled_f != 0; }
    c::Task* c()            { return &c_; }

private:
    static int shim_step(c::Task* self);
    std::function<bool()> step_;
    c::Task                c_;
};

void gather(std::initializer_list<Task*> task_list);

class TriggerDispatcher {
public:
    explicit TriggerDispatcher(const std::vector<Trigger*>& trigger_list);
    ~TriggerDispatcher();
    TriggerDispatcher(const TriggerDispatcher&)            = delete;
    TriggerDispatcher& operator=(const TriggerDispatcher&) = delete;

    void        run();
    Task        task() { return Task(*this); }
    void        stop();
    std::string to_string();                         // Python's '__repr__'
    int         end_tick() const { return c_.end_tick; }
    c::TriggerDispatcher* c()     { return &c_; }

private:
    std::vector<c::Trigger*> c_trigger_list_;
    c::TriggerDispatcher     c_;
};

} // namespace hwut

#endif
