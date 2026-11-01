// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: A DETERMINISTIC EVENT DISPATCHER -- the port of
//          'python/deterministic_timeline.py'. Triggers fire at the ticks
//          their timeline strings mark with a digit; within one tick the
//          LOWER digit fires first, equal digits in registration order:
//
//              Trigger A: "1  12 1"
//              Trigger B: " 1  1 2"
//
//          When the last tick has passed, every trigger is told
//          'on_termination(end_tick)', 'end_tick' being the LONGEST
//          timeline's length. 'stop' leaves early and still announces; a
//          CANCELLED task announces nothing.
//
// A TRIGGER OF ONE'S OWN holds a 'TriggerBase' and implements 'Trigger':
//
//     struct MyTrigger { base: TriggerBase }
//     impl Trigger for MyTrigger {
//         fn base(&self) -> &TriggerBase { &self.base }
//         fn fire(&mut self, t: usize) -> Result<(), TimelineError> { ...; Ok(()) }
//     }
//     let my = shared(MyTrigger { base: TriggerBase::new("1 1 3", "SUB") });
//     let mut d = TriggerDispatcher::new(vec![my.clone()]);
//     d.run()?;
//
// 'fire' not overridden is ABSTRACT: the run ends there with
// 'TimelineError::NotImplemented' -- Python's NotImplementedError.
// 'on_termination' not overridden says nothing.
//
// THE YIELD WITHOUT COROUTINES: a 'Task' is stepped; one 'step' runs up to
// the next yield. 'gather' steps tasks in turn, in the order given -- the
// order 'asyncio.gather' gives them -- until each is done. The dispatcher IS
// a task (its run); a closure 'FnMut() -> Step' is one too. 'TaskHandle'
// carries a task that may be cancelled ('asyncio.create_task').
//______________________________________________________________________________
use std::cell::{Cell, RefCell};
use std::fmt;
use std::rc::Rc;

/// What ends a run otherwise than by its end.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TimelineError {
    /// A trigger says nothing it does: Python's NotImplementedError.
    NotImplemented,
    /// The task carrying the run was cancelled: Python's CancelledError.
    Cancelled,
}

impl fmt::Display for TimelineError {
    /// RETURN: fmt::Result; Python's exception name was written.
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            TimelineError::NotImplemented => write!(f, "NotImplementedError"),
            TimelineError::Cancelled      => write!(f, "CancelledError"),
        }
    }
}

/// What every trigger is given: its timeline and its name.
#[derive(Clone, Debug)]
pub struct TriggerBase {
    pub timeline: String,
    pub name:     String,
}

impl TriggerBase {
    /// RETURN: TriggerBase carrying 'timeline' and 'name'; where 'name' is
    ///         empty, a name the machine chooses ('trigger-<address>').
    pub fn new(timeline: &str, name: &str) -> TriggerBase {
        let mut base = TriggerBase { timeline: timeline.to_string(), name: name.to_string() };
        if name.is_empty() { base.name = format!("trigger-{:p}", &base as *const TriggerBase); }
        base
    }
}

/// A dispatchable event: Python's 'Trigger' base class.
pub trait Trigger {
    /// RETURN: &TriggerBase, the trigger's timeline and name.
    fn base(&self) -> &TriggerBase;

    /// RETURN: &str, the timeline string.
    fn timeline(&self) -> &str { &self.base().timeline }

    /// RETURN: &str, the name.
    fn name(&self) -> &str { &self.base().name }

    /// RETURN: Ok(()), the trigger did what it does at 'pseudo_time', one of
    ///         the ticks its timeline marked with a digit;
    ///         Err(TimelineError::NotImplemented), where it is not overridden
    ///         -- the base refuses rather than guesses.
    fn fire(&mut self, _pseudo_time: usize) -> Result<(), TimelineError> {
        Err(TimelineError::NotImplemented)
    }

    /// RETURN: nothing; the trigger was told the timeline has passed. Does
    ///         nothing where not overridden. NOT a step of a task: the run is
    ///         over, there is nobody to yield to.
    fn on_termination(&mut self, _end_tick: usize) {}
}

/// The base class, instantiated as it stands: 'Trigger("1", "GIVEN")'.
impl Trigger for TriggerBase {
    fn base(&self) -> &TriggerBase { self }
}

/// A trigger as the dispatcher and the test both hold it.
pub type SharedTrigger = Rc<RefCell<dyn Trigger>>;

/// RETURN: Rc<RefCell<T>>, 'trigger' made shareable -- coerced to
///         'SharedTrigger' where it is handed to a dispatcher.
pub fn shared<T: Trigger + 'static>(trigger: T) -> Rc<RefCell<T>> { Rc::new(RefCell::new(trigger)) }

/// What one step of a task did.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Step {
    /// The task yielded; it goes on at the next step.
    Yielded,
    /// The task is done -- Ok, or ended by its error.
    Done(Result<(), TimelineError>),
}

/// A computation that yields: one 'step' runs it to its next yield.
pub trait Task {
    /// RETURN: Step::Yielded where the task yielded and goes on;
    ///         Step::Done(result) where it ended.
    fn step(&mut self) -> Step;
}

impl<F: FnMut() -> Step> Task for F {
    fn step(&mut self) -> Step { self() }
}

/// A task as 'asyncio.create_task' gives it: stepped, cancelled, awaited.
pub struct TaskHandle<'a> {
    task:   &'a mut dyn Task,
    result: Option<Result<(), TimelineError>>,
}

impl<'a> TaskHandle<'a> {
    /// RETURN: TaskHandle carrying 'task', not stepped yet.
    pub fn new(task: &'a mut dyn Task) -> TaskHandle<'a> { TaskHandle { task, result: None } }

    /// RETURN: bool, true where the task yielded and goes on; false where it
    ///         is done or cancelled.
    pub fn step(&mut self) -> bool {
        if self.result.is_some() { return false; }
        match self.task.step() {
            Step::Yielded      => true,
            Step::Done(result) => { self.result = Some(result); false }
        }
    }

    /// RETURN: nothing; the task is abandoned: never stepped again, and what
    ///         it would have done at its end is not done.
    pub fn cancel(&mut self) {
        if self.result.is_none() { self.result = Some(Err(TimelineError::Cancelled)); }
    }

    /// RETURN: Ok(()) once the task is done; Err(TimelineError::Cancelled)
    ///         where it was cancelled; its own error else.
    pub fn await_(&mut self) -> Result<(), TimelineError> {
        while self.step() {}
        self.result.unwrap_or(Ok(()))
    }
}

/// RETURN: Ok(()) once every task is done -- stepped in turn, in the order
///         given, each up to its next yield; the first error of a task (in
///         the order given) else, as 'asyncio.gather' raises it.
pub fn gather(task_list: &mut [&mut dyn Task]) -> Result<(), TimelineError> {
    let mut result: Vec<Option<Result<(), TimelineError>>> = vec![None; task_list.len()];
    loop {
        let mut live_f = false;
        for (i, task) in task_list.iter_mut().enumerate() {
            if result[i].is_some() { continue; }
            live_f = true;
            if let Step::Done(r) = task.step() { result[i] = Some(r); }
        }
        if !live_f { break; }
    }
    result.into_iter().flatten().find(|r| r.is_err()).unwrap_or(Ok(()))
}

/// A handle that asks a dispatcher's run to leave the timeline.
#[derive(Clone)]
pub struct DispatcherStop(Rc<Cell<bool>>);

impl DispatcherStop {
    /// RETURN: nothing; the run leaves at the next firing and still announces.
    pub fn stop(&self) { self.0.set(false); }
}

/// Executes triggers by a timeline calculated in advance.
pub struct TriggerDispatcher {
    trigger_list:    Vec<SharedTrigger>,
    trigger_time_db: Vec<Vec<(u32, usize)>>,      // per tick: (priority, trigger index)
    end_tick:        usize,
    running_f:       Rc<Cell<bool>>,
    tick:            usize,                       // where the run stands
    i:               usize,
    finished_f:      bool,
}

impl TriggerDispatcher {
    /// RETURN: TriggerDispatcher with its schedule built: per tick the
    ///         (priority, trigger) pairs whose timeline carries a digit
    ///         there, the lower digit first, registration order between
    ///         equal digits (a stable sort). As long as the LONGEST timeline.
    pub fn new(triggers: Vec<SharedTrigger>) -> TriggerDispatcher {
        let end_tick = triggers.iter().map(|t| t.borrow().timeline().chars().count()).max().unwrap_or(0);
        let mut db: Vec<Vec<(u32, usize)>> = vec![Vec::new(); end_tick];
        for (k, trigger) in triggers.iter().enumerate() {
            for (t, c) in trigger.borrow().timeline().chars().enumerate() {
                if let Some(priority) = c.to_digit(10) { db[t].push((priority, k)); }
            }
        }
        for tick in db.iter_mut() { tick.sort_by_key(|x| x.0); }
        TriggerDispatcher { trigger_list: triggers, trigger_time_db: db, end_tick,
                            running_f: Rc::new(Cell::new(true)), tick: 0, i: 0, finished_f: false }
    }

    /// RETURN: usize, the length of the longest timeline -- the 'end_tick'
    ///         every trigger is told.
    pub fn end_tick(&self) -> usize { self.end_tick }

    /// RETURN: nothing; the run leaves the timeline at the next firing and
    ///         still announces termination.
    pub fn stop(&self) { self.running_f.set(false); }

    /// RETURN: DispatcherStop, a handle a trigger keeps to call 'stop()' from
    ///         inside the run.
    pub fn stopper(&self) -> DispatcherStop { DispatcherStop(self.running_f.clone()) }

    /// RETURN: Ok(()) once the timeline was walked -- or 'stop()' cut it
    ///         short -- and every trigger was told 'on_termination(end_tick)';
    ///         Err(TimelineError::NotImplemented) where a trigger said nothing
    ///         it does (no announcement follows).
    pub fn run(&mut self) -> Result<(), TimelineError> {
        loop {
            if let Step::Done(result) = self.step() { return result; }
        }
    }
}

impl Task for TriggerDispatcher {
    /// RETURN: Step::Yielded after one firing (the 'sleep(0)'); Step::Done
    ///         once the timeline passed and every trigger was told -- or a
    ///         trigger refused.
    fn step(&mut self) -> Step {
        if self.finished_f { return Step::Done(Ok(())); }
        while self.running_f.get() && self.tick < self.end_tick {
            if self.i < self.trigger_time_db[self.tick].len() {
                let k = self.trigger_time_db[self.tick][self.i].1;
                self.i += 1;
                let trigger = self.trigger_list[k].clone();
                let result  = trigger.borrow_mut().fire(self.tick);
                if let Err(error) = result { self.finished_f = true; return Step::Done(Err(error)); }
                return Step::Yielded;
            }
            self.tick += 1;
            self.i = 0;
        }
        for trigger in &self.trigger_list { trigger.borrow_mut().on_termination(self.end_tick); }
        self.finished_f = true;
        Step::Done(Ok(()))
    }
}

impl fmt::Display for TriggerDispatcher {
    /// RETURN: fmt::Result; 'TriggerDispatcher', then one line per firing,
    ///         '[tick] (priority)name', in the order of the run, were written
    ///         -- Python's 'repr'.
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "TriggerDispatcher")?;
        for (t, tick) in self.trigger_time_db.iter().enumerate() {
            for (priority, k) in tick {
                write!(f, "\n[{}] ({}){}", t, priority, self.trigger_list[*k].borrow().name())?;
            }
        }
        Ok(())
    }
}
