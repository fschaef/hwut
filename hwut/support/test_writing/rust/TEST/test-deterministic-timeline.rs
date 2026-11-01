// @hwut {
//     title      = "TriggerDispatcher: schedule, priority, and the end of time"
//     build      { framework = "make", executable = "%.exe" }
//     choices {
//         abstract    { features = ["rust-timeline"] }
//         cancel      { features = ["rust-timeline"] }
//         edges       { features = ["rust-timeline"] }
//         priority    { features = ["rust-timeline"] }
//         schedule    { features = ["rust-timeline"] }
//         stable      { features = ["rust-timeline"] }
//         stop        { features = ["rust-timeline"] }
//         termination { features = ["rust-timeline"] }
//         yielding    { features = ["rust-timeline"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: The Rust port of 'python/TEST/test-deterministic-timeline.py',
//          choice for choice, held against its GOOD files by '.link'. Where
//          Python awaits, Rust steps a task.
//______________________________________________________________________________
use std::cell::RefCell;
use std::rc::Rc;

use hwut::deterministic_timeline::{gather, shared, DispatcherStop, SharedTrigger, Step, TaskHandle,
                                   TimelineError, Trigger, TriggerBase, TriggerDispatcher};
use hwut::hwut_runner::HwutRunner;

fn banner(label: &str) { println!("\n--- {} ---", label); }

/// A trigger that says what it is asked to do, and when.
struct SpeakingTrigger { base: TriggerBase, silent_termination_f: bool, stopper: Option<DispatcherStop> }

impl SpeakingTrigger {
    fn new(name: &str, timeline: &str) -> SharedTrigger {
        println!("SETUP: {:<7} |{}|", name, timeline);
        shared(SpeakingTrigger { base: TriggerBase::new(timeline, name), silent_termination_f: false, stopper: None })
    }
}

impl Trigger for SpeakingTrigger {
    fn base(&self) -> &TriggerBase { &self.base }
    fn fire(&mut self, pseudo_time: usize) -> Result<(), TimelineError> {
        println!("  [t:{}] {} fires", pseudo_time, self.name());
        if let Some(stopper) = &self.stopper {
            println!("  ... asks the dispatcher to stop");
            stopper.stop();
        }
        Ok(())
    }
    fn on_termination(&mut self, end_tick: usize) {
        if self.silent_termination_f { return; }
        println!("  [end:{}] {} notified", end_tick, self.name());
    }
}

/// A trigger that fires and does NOT override 'on_termination'.
struct MuteTrigger { base: TriggerBase }

impl MuteTrigger {
    fn new(name: &str, timeline: &str) -> SharedTrigger {
        println!("SETUP: {:<7} |{}|  (no on_termination override)", name, timeline);
        shared(MuteTrigger { base: TriggerBase::new(timeline, name) })
    }
}

impl Trigger for MuteTrigger {
    fn base(&self) -> &TriggerBase { &self.base }
    fn fire(&mut self, pseudo_time: usize) -> Result<(), TimelineError> {
        println!("  [t:{}] {} fires", pseudo_time, self.name());
        Ok(())
    }
}

fn dispatch(trigger_list: Vec<SharedTrigger>) -> Result<(), TimelineError> {
    TriggerDispatcher::new(trigger_list).run()
}

fn run_schedule() {
    banner("staggered: A at 0, B at 2, C at 4");
    let _ = dispatch(vec![SpeakingTrigger::new("A", "1    "), SpeakingTrigger::new("B", "  1  "),
                          SpeakingTrigger::new("C", "    1")]);
    banner("a SHORT timeline stops contributing; the long one goes on");
    let _ = dispatch(vec![SpeakingTrigger::new("SHORT", "11"), SpeakingTrigger::new("LONG", "111111")]);
    banner("the SCHEDULE as built -- '[tick] (priority)name'");
    println!("{}", TriggerDispatcher::new(vec![SpeakingTrigger::new("A", "12"), SpeakingTrigger::new("B", "21")]));
}

fn run_priority() {
    banner("digits swap between ticks: B leads at 0, A leads at 1");
    let _ = dispatch(vec![SpeakingTrigger::new("A", "21"), SpeakingTrigger::new("B", "12")]);
    banner("0 is the strongest digit, 9 the weakest");
    let _ = dispatch(vec![SpeakingTrigger::new("WEAK", "9"), SpeakingTrigger::new("STRONG", "0")]);
}

fn run_stable() {
    banner("three triggers, all digit 1 at tick 0");
    let _ = dispatch(vec![SpeakingTrigger::new("first", "1"), SpeakingTrigger::new("second", "1"),
                          SpeakingTrigger::new("third", "1")]);
    banner("registered BACKWARDS -- the order follows registration, not the name");
    let _ = dispatch(vec![SpeakingTrigger::new("third", "1"), SpeakingTrigger::new("second", "1"),
                          SpeakingTrigger::new("first", "1")]);
}

fn run_termination() {
    banner("end_tick is the LENGTH -- 5 characters, last firing at tick 0");
    let _ = dispatch(vec![SpeakingTrigger::new("EARLY", "1    ")]);
    banner("a trigger that NEVER fires is notified all the same");
    let _ = dispatch(vec![SpeakingTrigger::new("FIRES", "1  "), SpeakingTrigger::new("SILENT", "   ")]);
    banner("the LONGEST timeline sets end_tick for everybody");
    let _ = dispatch(vec![SpeakingTrigger::new("SHORT", "1"), SpeakingTrigger::new("LONG", "1      ")]);
    banner("a trigger that does not override is simply silent at the end");
    let _ = dispatch(vec![SpeakingTrigger::new("SPEAKS", "1 "), MuteTrigger::new("MUTE", "1 ")]);
}

/// Prepares one item per tick; announces end-of-stream at the end.
struct ProducingTrigger { base: TriggerBase, item: Option<String>, finished: bool }

impl Trigger for ProducingTrigger {
    fn base(&self) -> &TriggerBase { &self.base }
    fn fire(&mut self, pseudo_time: usize) -> Result<(), TimelineError> {
        self.item = Some(format!("item@{}", pseudo_time));
        println!("  [t:{}] {} prepared {}", pseudo_time, self.name(), self.item.as_ref().unwrap());
        Ok(())
    }
    fn on_termination(&mut self, end_tick: usize) {
        self.finished = true;
        println!("  [end:{}] {} announced end-of-stream", end_tick, self.name());
    }
}

fn run_yielding() {
    banner("producer fires at every tick; consumer waits between them");
    println!("SETUP: {:<7} |{}|", "PROD", "111");
    let producer: Rc<RefCell<ProducingTrigger>> =
        shared(ProducingTrigger { base: TriggerBase::new("111", "PROD"), item: None, finished: false });
    let mut dispatcher = TriggerDispatcher::new(vec![producer.clone()]);
    //  THE CONSUMER: one step takes what stands, then waits (yields) --
    //  until the end is announced.
    let mut taken = 0;
    let mut consume = || -> Step {
        let mut p = producer.borrow_mut();
        loop {
            match p.item.take() {
                Some(item) => { taken += 1; println!("        consumer took {}", item); }
                None if p.finished => {
                    println!("  consumer saw end-of-stream after {} item(s)", taken);
                    return Step::Done(Ok(()));
                }
                None => return Step::Yielded,
            }
        }
    };
    let _ = gather(&mut [&mut dispatcher, &mut consume]);
    println!();
    println!("Each item was taken BEFORE the next tick prepared one: the run yields.");
}

fn run_stop() {
    banner("stop() after the first tick -- ticks 1.. are not walked, the announcement still comes");
    println!("SETUP: {:<7} |{}|", "STOPPER", "1111");
    let stopper = shared(SpeakingTrigger { base: TriggerBase::new("1111", "STOPPER"),
                                           silent_termination_f: false, stopper: None });
    let bystander = SpeakingTrigger::new("OTHER", "1111");
    let mut dispatcher = TriggerDispatcher::new(vec![stopper.clone(), bystander]);
    stopper.borrow_mut().stopper = Some(dispatcher.stopper());
    let _ = dispatcher.run();
    println!();
    println!("end_tick is still the timeline's length, not the tick the run stopped at.");
}

fn run_cancel() {
    banner("cancel() the task carrying run() -- no announcement follows");
    let mut dispatcher = TriggerDispatcher::new(vec![SpeakingTrigger::new("A", "1111111111")]);
    let mut task = TaskHandle::new(&mut dispatcher);
    task.step();                                           // one tick passes
    task.cancel();
    if task.await_() == Err(TimelineError::Cancelled) { println!("  run() was cancelled"); }
    println!();
    println!("No '[end:..]' line above: the triggers were abandoned, not ended.");
}

fn run_edges() {
    banner("an EMPTY timeline -- end_tick 0");
    let _ = dispatch(vec![SpeakingTrigger::new("EMPTY", "")]);
    banner("a timeline of BLANKS -- no digit, so nothing fires");
    let _ = dispatch(vec![SpeakingTrigger::new("BLANK", "    ")]);
    banner("NO TRIGGERS at all -- nothing to announce, and no failure");
    let _ = dispatch(vec![]);
    println!("  (dispatcher ran; nothing was scheduled)");
    banner("a timeline of blanks beside one that fires");
    let _ = dispatch(vec![SpeakingTrigger::new("BLANK", "   "), SpeakingTrigger::new("FIRES", " 1 ")]);
}

fn run_abstract() {
    banner("the BASE 'fire' is abstract -- it refuses");
    if dispatch(vec![shared(TriggerBase::new("1", "BARE"))]) == Err(TimelineError::NotImplemented) {
        println!("  NotImplementedError -- as owed: a trigger must say what it does");
    }
    banner("the BASE 'on_termination' is optional -- it is silent");
    let mut bare = TriggerBase::new("", "BARE");
    bare.on_termination(0);
    println!("  returned quietly; nothing raised, nothing printed");
    banner("a NAME given is the name kept");
    println!("  name: {}", TriggerBase::new("1", "GIVEN").name());
}

fn main() {
    HwutRunner::new(std::env::args().collect(), "TriggerDispatcher: schedule, priority, and the end of time", vec![
        ("schedule",    run_schedule),
        ("priority",    run_priority),
        ("stable",      run_stable),
        ("termination", run_termination),
        ("yielding",    run_yielding),
        ("stop",        run_stop),
        ("cancel",      run_cancel),
        ("edges",       run_edges),
        ("abstract",    run_abstract),
    ]).exit();
}
