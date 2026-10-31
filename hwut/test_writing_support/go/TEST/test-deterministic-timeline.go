// @hwut {
//     title      = "TriggerDispatcher: schedule, priority, and the end of time"
//     build      { framework = "make", executable = "%.exe"
//                  caps { file_size_mb = 256 } }
//     choices {
//          abstract    { features = ["go-timeline"] }
//          cancel      { features = ["go-timeline"] }
//          edges       { features = ["go-timeline"] }
//          priority    { features = ["go-timeline"] }
//          schedule    { features = ["go-timeline"] }
//          stable      { features = ["go-timeline"] }
//          stop        { features = ["go-timeline"] }
//          termination { features = ["go-timeline"] }
//          yielding    { features = ["go-timeline"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The Go port of 'python/TEST/test-deterministic-timeline.py', choice
//          for choice, held against its GOOD files by '.link'. Where Python
//          awaits, a Go task waits on the package's own event loop.
// _____________________________________________________________________________

package main

import (
	"errors"
	"fmt"
	"os"

	dt "hwut/test_writing_support/go/deterministictimeline"
	"hwut/test_writing_support/go/hwutrunner"
)

func banner(label string) { fmt.Printf("\n--- %s ---\n", label) }

// SpeakingTrigger says what it is asked to do, and when.
type SpeakingTrigger struct {
	*dt.TriggerBase
	silentTerminationF bool
}

func NewSpeakingTrigger(name, timeline string) *SpeakingTrigger {
	fmt.Printf("SETUP: %-7s |%s|\n", name, timeline)
	return &SpeakingTrigger{TriggerBase: dt.NewTriggerBase(timeline, name)}
}

func (self *SpeakingTrigger) Fire(task *dt.Task, pseudoTime int) error {
	fmt.Printf("  [t:%d] %s fires\n", pseudoTime, self.Name())
	return nil
}

func (self *SpeakingTrigger) OnTermination(endTick int) {
	if self.silentTerminationF {
		return
	}
	fmt.Printf("  [end:%d] %s notified\n", endTick, self.Name())
}

// MuteTrigger fires and does NOT override 'OnTermination'.
type MuteTrigger struct{ *dt.TriggerBase }

func NewMuteTrigger(name, timeline string) *MuteTrigger {
	fmt.Printf("SETUP: %-7s |%s|  (no on_termination override)\n", name, timeline)
	return &MuteTrigger{dt.NewTriggerBase(timeline, name)}
}

func (self *MuteTrigger) Fire(task *dt.Task, pseudoTime int) error {
	fmt.Printf("  [t:%d] %s fires\n", pseudoTime, self.Name())
	return nil
}

// dispatch builds a dispatcher over 'triggerList' and runs it to completion.
func dispatch(triggerList ...dt.Trigger) error {
	return dt.Run(dt.NewTriggerDispatcher(triggerList).Run)
}

func runSchedule() {
	banner("staggered: A at 0, B at 2, C at 4")
	dispatch(NewSpeakingTrigger("A", "1    "), NewSpeakingTrigger("B", "  1  "), NewSpeakingTrigger("C", "    1"))
	banner("a SHORT timeline stops contributing; the long one goes on")
	dispatch(NewSpeakingTrigger("SHORT", "11"), NewSpeakingTrigger("LONG", "111111"))
	banner("the SCHEDULE as built -- '[tick] (priority)name'")
	fmt.Println(dt.NewTriggerDispatcher([]dt.Trigger{NewSpeakingTrigger("A", "12"), NewSpeakingTrigger("B", "21")}))
}

func runPriority() {
	banner("digits swap between ticks: B leads at 0, A leads at 1")
	dispatch(NewSpeakingTrigger("A", "21"), NewSpeakingTrigger("B", "12"))
	banner("0 is the strongest digit, 9 the weakest")
	dispatch(NewSpeakingTrigger("WEAK", "9"), NewSpeakingTrigger("STRONG", "0"))
}

func runStable() {
	banner("three triggers, all digit 1 at tick 0")
	dispatch(NewSpeakingTrigger("first", "1"), NewSpeakingTrigger("second", "1"), NewSpeakingTrigger("third", "1"))
	banner("registered BACKWARDS -- the order follows registration, not the name")
	dispatch(NewSpeakingTrigger("third", "1"), NewSpeakingTrigger("second", "1"), NewSpeakingTrigger("first", "1"))
}

func runTermination() {
	banner("end_tick is the LENGTH -- 5 characters, last firing at tick 0")
	dispatch(NewSpeakingTrigger("EARLY", "1    "))
	banner("a trigger that NEVER fires is notified all the same")
	dispatch(NewSpeakingTrigger("FIRES", "1  "), NewSpeakingTrigger("SILENT", "   "))
	banner("the LONGEST timeline sets end_tick for everybody")
	dispatch(NewSpeakingTrigger("SHORT", "1"), NewSpeakingTrigger("LONG", "1      "))
	banner("a trigger that does not override is simply silent at the end")
	dispatch(NewSpeakingTrigger("SPEAKS", "1 "), NewMuteTrigger("MUTE", "1 "))
}

// ProducingTrigger prepares one item per tick, and announces the end.
type ProducingTrigger struct {
	*dt.TriggerBase
	item     string
	hasItem  bool
	finished bool
}

func (self *ProducingTrigger) Fire(task *dt.Task, pseudoTime int) error {
	self.item, self.hasItem = fmt.Sprintf("item@%d", pseudoTime), true
	fmt.Printf("  [t:%d] %s prepared %s\n", pseudoTime, self.Name(), self.item)
	return nil
}

func (self *ProducingTrigger) OnTermination(endTick int) {
	self.finished = true
	fmt.Printf("  [end:%d] %s announced end-of-stream\n", endTick, self.Name())
}

func runYielding() {
	banner("producer fires at every tick; consumer waits between them")
	consume := func(producer *ProducingTrigger) func(*dt.Task) error {
		return func(task *dt.Task) error {
			taken := 0
			for {
				for !producer.hasItem {
					if producer.finished {
						fmt.Printf("  consumer saw end-of-stream after %d item(s)\n", taken)
						return nil
					}
					if err := task.Sleep0(); err != nil {
						return err
					}
				}
				taken++
				fmt.Printf("        consumer took %s\n", producer.item)
				producer.hasItem = false
			}
		}
	}
	dt.Run(func(task *dt.Task) error {
		fmt.Printf("SETUP: %-7s |%s|\n", "PROD", "111")
		producer := &ProducingTrigger{TriggerBase: dt.NewTriggerBase("111", "PROD")}
		return task.Gather(dt.NewTriggerDispatcher([]dt.Trigger{producer}).Run, consume(producer))
	})
	fmt.Println()
	fmt.Println("Each item was taken BEFORE the next tick prepared one: the run yields.")
}

// StoppingTrigger fires once, then asks the run to leave.
type StoppingTrigger struct {
	*SpeakingTrigger
	dispatcher *dt.TriggerDispatcher
}

func (self *StoppingTrigger) Fire(task *dt.Task, pseudoTime int) error {
	self.SpeakingTrigger.Fire(task, pseudoTime)
	fmt.Println("  ... asks the dispatcher to stop")
	self.dispatcher.Stop()
	return nil
}

func runStop() {
	banner("stop() after the first tick -- ticks 1.. are not walked, the announcement still comes")
	stopper := &StoppingTrigger{SpeakingTrigger: NewSpeakingTrigger("STOPPER", "1111")}
	bystander := NewSpeakingTrigger("OTHER", "1111")
	dispatcher := dt.NewTriggerDispatcher([]dt.Trigger{stopper, bystander})
	stopper.dispatcher = dispatcher
	dt.Run(dispatcher.Run)
	fmt.Println()
	fmt.Println("end_tick is still the timeline's length, not the tick the run stopped at.")
}

func runCancel() {
	banner("cancel() the task carrying run() -- no announcement follows")
	dt.Run(func(main *dt.Task) error {
		dispatcher := dt.NewTriggerDispatcher([]dt.Trigger{NewSpeakingTrigger("A", "1111111111")})
		task := main.CreateTask(dispatcher.Run)
		main.Sleep0()
		task.Cancel()
		if err := main.Await(task); errors.Is(err, dt.ErrCancelled) {
			fmt.Println("  run() was cancelled")
		}
		return nil
	})
	fmt.Println()
	fmt.Println("No '[end:..]' line above: the triggers were abandoned, not ended.")
}

func runEdges() {
	banner("an EMPTY timeline -- end_tick 0")
	dispatch(NewSpeakingTrigger("EMPTY", ""))
	banner("a timeline of BLANKS -- no digit, so nothing fires")
	dispatch(NewSpeakingTrigger("BLANK", "    "))
	banner("NO TRIGGERS at all -- nothing to announce, and no failure")
	dispatch()
	fmt.Println("  (dispatcher ran; nothing was scheduled)")
	banner("a timeline of blanks beside one that fires")
	dispatch(NewSpeakingTrigger("BLANK", "   "), NewSpeakingTrigger("FIRES", " 1 "))
}

// BareTrigger overrides nothing.
type BareTrigger struct{ *dt.TriggerBase }

func runAbstract() {
	banner("the BASE 'fire' is abstract -- it refuses")
	if err := dispatch(&BareTrigger{dt.NewTriggerBase("1", "BARE")}); errors.Is(err, dt.ErrNotImplemented) {
		fmt.Println("  NotImplementedError -- as owed: a trigger must say what it does")
	}
	banner("the BASE 'on_termination' is optional -- it is silent")
	bare := &BareTrigger{dt.NewTriggerBase("", "BARE")}
	bare.OnTermination(0)
	fmt.Println("  returned quietly; nothing raised, nothing printed")
	banner("a NAME given is the name kept")
	fmt.Println("  name:", dt.NewTriggerBase("1", "GIVEN").Name())
}

func main() {
	os.Exit(hwutrunner.New(os.Args, "TriggerDispatcher: schedule, priority, and the end of time", map[string]func(){
		"schedule":    runSchedule,
		"priority":    runPriority,
		"stable":      runStable,
		"termination": runTermination,
		"yielding":    runYielding,
		"stop":        runStop,
		"cancel":      runCancel,
		"edges":       runEdges,
		"abstract":    runAbstract,
	}).Run())
}
