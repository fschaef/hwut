// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The deterministic event dispatcher -- see 'deterministic_timeline.hpp'.
//
// AN EXCEPTION DOES NOT CROSS THE C CORE: the shim catches what a trigger
// throws, keeps it, and ends the C run with an error; the C++ call that
// drove the run ('run', 'await', 'gather') throws it again.
// _____________________________________________________________________________
#include "deterministic_timeline.hpp"

#include <cstdlib>
#include <exception>

using namespace hwut::c;

namespace hwut {

namespace {

std::exception_ptr pending;          // what a trigger threw, not yet rethrown

void
rethrow_pending()
/* RETURN: nothing where no trigger threw; else the exception it threw is
 *         thrown again, and forgotten here.                                */
{
    if( ! pending ) return;
    std::exception_ptr e = pending;
    pending = nullptr;
    std::rethrow_exception(e);
}

} // namespace

/* ------------------------------------------------------------------ Trigger */
const Trigger_Vtable Trigger::shim_vtable = { Trigger::shim_fire, Trigger::shim_on_termination };

Trigger::Trigger(std::string timeline, const std::string& name)
/* RETURN: Trigger carrying 'timeline' and 'name' -- a name chosen by the
 *         machine ('trigger-<address>') where none is given.              */
    : timeline_(std::move(timeline))
{
    shim_.owner = this;
    Trigger_init(&shim_.base, &shim_vtable, timeline_.c_str(), name.c_str());
}

void
Trigger::fire(int)
/* RETURN: never; throws NotImplementedError -- a trigger must say what it
 *         does at its tick.                                                */
{ throw NotImplementedError(); }

void
Trigger::on_termination(int)
/* RETURN: nothing; the base has nothing to wind down.                      */
{}

int
Trigger::shim_fire(c::Trigger* self, int pseudo_time)
/* RETURN: TIMELINE_OK where the trigger's 'fire' returned; an error (the
 *         run ends) where it threw -- the exception kept in 'pending'.    */
{
    try {
        reinterpret_cast<Shim*>(self)->owner->fire(pseudo_time);
        return TIMELINE_OK;
    } catch( ... ) {
        pending = std::current_exception();
        return TIMELINE_NOT_IMPLEMENTED;
    }
}

void
Trigger::shim_on_termination(c::Trigger* self, int end_tick)
/* RETURN: nothing; the trigger's 'on_termination' ran -- what it threw kept
 *         in 'pending' (the first such, where several throw).             */
{
    try {
        reinterpret_cast<Shim*>(self)->owner->on_termination(end_tick);
    } catch( ... ) {
        if( ! pending ) pending = std::current_exception();
    }
}

/* --------------------------------------------------------------------- Task */
Task::Task(std::function<bool()> step)
/* RETURN: Task, not stepped yet; each step calls 'step', which returns true
 *         to yield (more to come) and false once done.                    */
    : step_(std::move(step))
{ Task_init(&c_, shim_step, this); }

Task::Task(TriggerDispatcher& dispatcher)
/* RETURN: Task, the run of 'dispatcher' -- one firing per step.            */
{ TriggerDispatcher_task(dispatcher.c(), &c_); }

int
Task::shim_step(c::Task* self)
/* RETURN: 1, the task's function yielded; 0, it is done -- or it threw,
 *         the exception kept in 'pending'.                                 */
{
    Task* task = static_cast<Task*>(self->context);
    try {
        return task->step_() ? 1 : 0;
    } catch( ... ) {
        pending      = std::current_exception();
        self->error  = TIMELINE_NOT_IMPLEMENTED;
        return 0;
    }
}

bool
Task::step()
/* RETURN: true, the task yielded and goes on; false, it is done or
 *         cancelled. What a trigger or the step threw is thrown on.       */
{
    bool more = Task_step(&c_) != 0;
    rethrow_pending();
    return more;
}

void
Task::cancel()
/* RETURN: nothing; the task is abandoned: never stepped again, and what it
 *         would have done at its end is not done.                          */
{ Task_cancel(&c_); }

void
Task::await()
/* RETURN: nothing, once the task is done; throws CancelledError where it was
 *         cancelled, and on what a trigger or the step threw.             */
{
    int result = Task_await(&c_);
    rethrow_pending();
    if( result == TIMELINE_CANCELLED ) throw CancelledError();
}

void
gather(std::initializer_list<Task*> task_list)
/* RETURN: nothing, once every task is done -- stepped in turn, in the order
 *         given, each up to its next yield; what one threw is thrown on. */
{
    std::vector<c::Task*> c_list;
    for(Task* t : task_list) c_list.push_back(t->c());
    Task_gather(c_list.data(), c_list.size());
    rethrow_pending();
}

/* -------------------------------------------------------- TriggerDispatcher */
TriggerDispatcher::TriggerDispatcher(const std::vector<Trigger*>& trigger_list)
/* RETURN: TriggerDispatcher, its schedule built: per tick the triggers due
 *         there, the lower digit first, registration order between equal
 *         digits.                                                          */
{
    for(Trigger* t : trigger_list) c_trigger_list_.push_back(t->c());
    TriggerDispatcher_init(&c_, c_trigger_list_.data(), c_trigger_list_.size());
}

TriggerDispatcher::~TriggerDispatcher()
/* RETURN: nothing; the schedule's memory is given back.                    */
{ TriggerDispatcher_free(&c_); }

void
TriggerDispatcher::run()
/* RETURN: nothing, once the timeline passed (or 'stop' cut it short) and
 *         every trigger was told 'on_termination(end_tick)'; throws what a
 *         trigger threw -- NotImplementedError for an abstract 'fire'.    */
{
    TriggerDispatcher_run(&c_);
    rethrow_pending();
}

void
TriggerDispatcher::stop()
/* RETURN: nothing; the run leaves at the next firing and still announces.  */
{ TriggerDispatcher_stop(&c_); }

std::string
TriggerDispatcher::to_string()
/* RETURN: 'TriggerDispatcher', then one line per firing, '[tick]
 *         (priority)name', in the order of the run -- Python's '__repr__'. */
{
    char*  text = nullptr;
    size_t size = 0;
    FILE*  out  = open_memstream(&text, &size);
    if( ! out ) return "TriggerDispatcher";
    TriggerDispatcher_print(&c_, out);
    std::fclose(out);
    std::string result(text, size);
    std::free(text);
    return result;
}

} // namespace hwut
