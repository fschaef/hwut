// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// Package deterministictimeline is A DETERMINISTIC EVENT DISPATCHER -- the
// port of 'python/deterministic_timeline.py'. Triggers fire at the ticks
// their timeline strings mark with a digit; within one tick the LOWER digit
// fires first, equal digits in registration order:
//
//	Trigger A: "1  12 1"
//	Trigger B: " 1  1 2"
//
// When the last tick has passed, every trigger is told
// 'OnTermination(endTick)', 'endTick' being the LONGEST timeline's length.
// 'Stop' leaves early and still announces; a CANCELLED task announces
// nothing.
//
// A TRIGGER OF ONE'S OWN embeds TriggerBase and overrides 'Fire' (and, at
// will, 'OnTermination'):
//
//	type MyTrigger struct{ *deterministictimeline.TriggerBase }
//	func (self *MyTrigger) Fire(task *deterministictimeline.Task, t int) error { ...; return nil }
//
//	d := deterministictimeline.NewTriggerDispatcher([]deterministictimeline.Trigger{
//	    &MyTrigger{deterministictimeline.NewTriggerBase("1 1 3", "SUB")}})
//	deterministictimeline.Run(d.Run)                  -- asyncio.run(d.run())
//
// TriggerBase's own 'Fire' is ABSTRACT: it returns ErrNotImplemented --
// Python's NotImplementedError -- and the run ends there with it.
//
// THE EVENT LOOP OF ASYNCIO, IN GO: a Task is a function run on a goroutine
// of its own, but ONE TASK RUNS AT A TIME and the order is asyncio's -- a
// FIFO of ready tasks; 'Sleep0' puts the task at the queue's end ('await
// asyncio.sleep(0)'), 'Await' waits for another task, 'Gather' starts tasks
// in the order given and waits for all, 'Cancel' makes the cancelled task's
// next wait return ErrCancelled (Python's CancelledError). The interleaving
// is therefore the one Python's is, run for run.
// _____________________________________________________________________________
package deterministictimeline

import (
	"errors"
	"fmt"
	"sort"
	"strings"
)

// ErrNotImplemented is what an abstract 'Fire' returns -- NotImplementedError.
var ErrNotImplemented = errors.New("NotImplementedError")

// ErrCancelled is what a cancelled task's wait returns -- CancelledError.
var ErrCancelled = errors.New("CancelledError")

// ------------------------------------------------------------------ the loop

// Loop is the event loop: the ready queue and the hand-over of control.
type Loop struct {
	ready []*Task
	back  chan struct{} // a task hands control back to the loop
}

// Task is one coroutine of the loop.
type Task struct {
	loop           *Loop
	function       func(*Task) error
	wake           chan struct{}
	startedF       bool
	doneF          bool
	cancelRequestF bool
	cancelledF     bool
	err            error
	waiterList     []*Task
}

// Run
//
// RETURN: error, what 'main' returned once it and nothing else ran to its
// end -- 'asyncio.run(main())': 'main' is the first task of a new loop, and
// the loop runs until it is done.
func Run(main func(*Task) error) error {
	loop := &Loop{back: make(chan struct{})}
	task := loop.newTask(main)
	for !task.doneF && len(loop.ready) != 0 {
		next := loop.ready[0]
		loop.ready = loop.ready[1:]
		next.wake <- struct{}{}
		<-loop.back
	}
	return task.err
}

// newTask
//
// RETURN: *Task, of 'function', ready -- at the end of the ready queue.
func (self *Loop) newTask(function func(*Task) error) *Task {
	task := &Task{loop: self, function: function, wake: make(chan struct{})}
	self.ready = append(self.ready, task)
	go task.body()
	return task
}

// body
//
// RETURN: nothing, once the task's function returned -- or, cancelled
// before it began, never ran; its waiters are ready then.
func (self *Task) body() {
	<-self.wake
	self.startedF = true
	if self.cancelRequestF {
		self.err = ErrCancelled
	} else {
		self.err = self.function(self)
	}
	self.cancelledF = errors.Is(self.err, ErrCancelled)
	self.doneF = true
	self.loop.ready = append(self.loop.ready, self.waiterList...)
	self.waiterList = nil
	self.loop.back <- struct{}{}
}

// suspend
//
// RETURN: error, ErrCancelled where the task was cancelled while it waited,
// nil else -- once the loop gave it control again.
func (self *Task) suspend() error {
	self.loop.back <- struct{}{}
	<-self.wake
	if self.cancelRequestF {
		self.cancelRequestF = false
		return ErrCancelled
	}
	return nil
}

// CreateTask
//
// RETURN: *Task, of 'function', scheduled to run after the tasks ready now
// -- 'asyncio.create_task'.
func (self *Task) CreateTask(function func(*Task) error) *Task {
	return self.loop.newTask(function)
}

// Sleep0
//
// RETURN: error, nil once every task ready before this one had its turn --
// 'await asyncio.sleep(0)'; ErrCancelled where the task was cancelled.
func (self *Task) Sleep0() error {
	self.loop.ready = append(self.loop.ready, self)
	return self.suspend()
}

// Await
//
// RETURN: error, what 'other' ended with, once it is done -- its function's
// error, ErrCancelled where it was cancelled; ErrCancelled where THIS task
// was cancelled while it waited.
func (self *Task) Await(other *Task) error {
	if !other.doneF {
		other.waiterList = append(other.waiterList, self)
		if err := self.suspend(); err != nil {
			return err
		}
	}
	return other.err
}

// Gather
//
// RETURN: error, nil once every function ran to its end as a task of its
// own, started in the order given -- 'asyncio.gather'; the first error of
// one of them, in that order, else.
func (self *Task) Gather(functionList ...func(*Task) error) error {
	taskList := make([]*Task, len(functionList))
	for i, function := range functionList {
		taskList[i] = self.CreateTask(function)
	}
	var first error
	for _, task := range taskList {
		if err := self.Await(task); err != nil && first == nil {
			first = err
		}
	}
	return first
}

// Cancel
//
// RETURN: nothing; the task is asked to end: its next wait returns
// ErrCancelled -- one not begun yet never begins. A done task stays done.
func (self *Task) Cancel() {
	if self.doneF {
		return
	}
	self.cancelRequestF = true
	if !self.startedF {
		return // in the ready queue already
	}
	for _, task := range self.loop.ready {
		if task == self {
			return
		}
	}
	self.loop.ready = append(self.loop.ready, self) // woken from its wait
}

// Done
//
// RETURN: bool, true once the task ended -- returned, failed or cancelled.
func (self *Task) Done() bool { return self.doneF }

// Cancelled
//
// RETURN: bool, true where the task ended by a cancellation.
func (self *Task) Cancelled() bool { return self.cancelledF }

// --------------------------------------------------------------- the trigger

// Trigger is what the dispatcher fires: TriggerBase gives the timeline, the
// name and the defaults; a trigger of one's own embeds it and overrides
// 'Fire'.
type Trigger interface {
	Timeline() string
	Name() string
	// Fire is the action at 'pseudoTime', a tick the timeline marked: nil
	// where done, an error ends the run with it.
	Fire(task *Task, pseudoTime int) error
	// OnTermination is the action once the timeline passed. NOT a wait:
	// the run is over, there is nobody to yield to.
	OnTermination(endTick int)
}

// TriggerBase is the base of every trigger -- Python's class 'Trigger'.
type TriggerBase struct {
	timeline string
	name     string
}

// NewTriggerBase
//
// RETURN: *TriggerBase, of 'timeline', named 'name' -- 'trigger-<address>'
// where 'name' is empty.
func NewTriggerBase(timeline, name string) *TriggerBase {
	self := &TriggerBase{timeline: timeline, name: name}
	if name == "" {
		self.name = fmt.Sprintf("trigger-%p", self)
	}
	return self
}

// Timeline
//
// RETURN: string, the timeline: a digit at position t fires at tick t.
func (self *TriggerBase) Timeline() string { return self.timeline }

// Name
//
// RETURN: string, the trigger's name.
func (self *TriggerBase) Name() string { return self.name }

// Fire
//
// RETURN: error, ErrNotImplemented always: the base is ABSTRACT -- a
// trigger that does nothing at its tick has no reason to stand in the
// timeline.
func (self *TriggerBase) Fire(task *Task, pseudoTime int) error { return ErrNotImplemented }

// OnTermination
//
// RETURN: nothing; does nothing -- overriding is optional, unlike 'Fire'.
func (self *TriggerBase) OnTermination(endTick int) {}

// ------------------------------------------------------------ the dispatcher

// firing is one scheduled firing: the digit and the trigger.
type firing struct {
	priority int
	trigger  Trigger
}

// TriggerDispatcher executes triggers by their pre-calculated timeline.
type TriggerDispatcher struct {
	runningF      bool
	triggerList   []Trigger
	triggerTimeDb [][]firing // one list per tick
	endTick       int
}

// NewTriggerDispatcher
//
// RETURN: *TriggerDispatcher, its schedule built: per tick the firings due
// there, the lower digit first, registration order between equal digits
// (the sort is stable); as many ticks as the LONGEST timeline has
// characters.
func NewTriggerDispatcher(triggerList []Trigger) *TriggerDispatcher {
	endTick := 0
	for _, trigger := range triggerList {
		endTick = max(endTick, len([]rune(trigger.Timeline())))
	}
	db := make([][]firing, endTick)
	for _, trigger := range triggerList {
		for t, character := range []rune(trigger.Timeline()) {
			if character >= '0' && character <= '9' {
				db[t] = append(db[t], firing{int(character - '0'), trigger})
			}
		}
	}
	for _, tickSequence := range db {
		sort.SliceStable(tickSequence, func(i, j int) bool { return tickSequence[i].priority < tickSequence[j].priority })
	}
	return &TriggerDispatcher{runningF: true, triggerList: triggerList, triggerTimeDb: db, endTick: endTick}
}

// Stop
//
// RETURN: nothing; the run leaves the timeline at the next firing -- and
// still announces termination.
func (self *TriggerDispatcher) Stop() { self.runningF = false }

// Run
//
// RETURN: error, nil once the timeline was stepped tick by tick -- every
// trigger due fired in priority order, the task yielding ('Sleep0') after
// each -- and every trigger was told 'OnTermination(endTick)', also where
// 'Stop' cut the walk short; a trigger's error (ErrNotImplemented) or
// ErrCancelled, else -- and then NOTHING is announced: a cancellation is no
// ending, it is an abandonment.
func (self *TriggerDispatcher) Run(task *Task) error {
	for pseudoTime, tickSequence := range self.triggerTimeDb {
		if !self.runningF {
			break
		}
		for _, f := range tickSequence {
			if !self.runningF {
				break
			}
			if err := f.trigger.Fire(task, pseudoTime); err != nil {
				return err
			}
			if err := task.Sleep0(); err != nil {
				return err
			}
		}
	}
	for _, trigger := range self.triggerList {
		trigger.OnTermination(self.endTick)
	}
	return nil
}

// String
//
// RETURN: string, 'TriggerDispatcher', then the built timeline, one line per
// scheduled firing -- '[tick] (priority)name', in the order of the run.
func (self *TriggerDispatcher) String() string {
	result := []string{"TriggerDispatcher"}
	for pseudoTime, tickSequence := range self.triggerTimeDb {
		for _, f := range tickSequence {
			result = append(result, fmt.Sprintf("[%d] (%d)%s", pseudoTime, f.priority, f.trigger.Name()))
		}
	}
	return strings.Join(result, "\n")
}
