// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// Package hwutfsm is A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER
// TEST -- the port of 'python/hwut_fsm.py' (README-hwut_fsm.txt). The states
// it may be in, the events that move it, the states it must never reach. A
// test FIRES the events it observes; every event the model does not allow,
// and every forbidden state entered, is WRITTEN as a line -- so it lands in
// the GOOD file and the comparison judges it.
//
//	m, err := hwutfsm.FromString(`
//	    initial: idle
//	    forbidden: crashed
//	    idle    ---( request )---> waiting ---( grant )---> busy
//	    busy    ---( release )---> idle
//	    :       ---( fault )--->   crashed
//	`)
//	m.Fire("request", 1)   // true
//	m.Fire("release", 2)   // BREACH line 2: 'release' in 'waiting' -- allowed: grant
//	m.Report()             // what was visited, what never was
//
// The same model text, the same words, the same sorted reports as Python.
//
// PYTHON'S KEYWORDS ARE OPTIONS: 'hwutfsm.DFA(false)', 'hwutfsm.Name("p")',
// 'hwutfsm.Write(f)', 'hwutfsm.States(...)'. What Python RAISES (FsmError) is
// returned as an error of type *FsmError, its text Python's.
//
// 'where' (a breach's place) is any: an int names a line ('line 3'), a
// string stands as written, nil names no place. A STATE "" in 'Disallow',
// 'Allow' and 'Disallowed' is Python's None: every state -- no state is
// named "" ('A', 'state A' are the names a model knows). A START "" in
// 'PathTo' and 'StateReachable' is the initial state, "now" the present.
// _____________________________________________________________________________
package hwutfsm

import (
	"fmt"
	"regexp"
	"sort"
	"strings"

	"hwut/test_writing_support/go/pytext"
)

// FsmError is a model that cannot be meant -- named with its line where read
// from text; or a word the model never names, given to a method.
type FsmError struct {
	Message string
}

// Error
//
// RETURN: string, the error's text -- Python's FsmError text.
func (self *FsmError) Error() string { return self.Message }

// fsmError
//
// RETURN: *FsmError, its message 'format' filled with 'argument'.
func fsmError(format string, argument ...any) *FsmError {
	return &FsmError{Message: fmt.Sprintf(format, argument...)}
}

// Transition is one (state, event, state) triple of a model.
type Transition struct {
	Source, Event, Target string
}

// TraceEntry is one transition fired: where, from, by, to.
type TraceEntry struct {
	Where  any
	Source string
	Event  string
	Target string
}

// options are Python's keywords of 'Machine' and 'from_string'.
type options struct {
	dfaF   bool
	name   string
	write  func(line string)
	states []string
}

// Option sets one of Python's keywords.
type Option func(*options)

// DFA
//
// RETURN: Option, 'DFA=value': true (the default) one state, two
// transitions for one (state, event) refused; false a SET of states.
func DFA(value bool) Option { return func(o *options) { o.dfaF = value } }

// Name
//
// RETURN: Option, 'name=value': the machine's name in its report ("fsm").
func Name(value string) Option { return func(o *options) { o.name = value } }

// Write
//
// RETURN: Option, 'write=value': every breach and report line goes through
// it (default: printed with a newline on stdout).
func Write(value func(line string)) Option { return func(o *options) { o.write = value } }

// States
//
// RETURN: Option, 'states=value': states no transition touches (yet).
func States(value ...string) Option { return func(o *options) { o.states = value } }

// edgeKey is a (state, event) pair.
type edgeKey struct{ state, event string }

// maskKey is a mask's scope: 'everyF' -- Python's None -- or one state.
type maskKey struct {
	everyF bool
	state  string
	event  string
}

// Machine is a state machine, its current state(s), and what was seen of it.
type Machine struct {
	Name           string
	DfaF           bool
	write          func(line string)
	edgeDb         map[edgeKey]map[string]bool
	Initial        string
	modelForbidden map[string]bool
	final          map[string]bool
	StateList      []string // sorted, the forbidden among them
	EventList      []string // sorted

	maskDb    map[maskKey]any // -> since
	forbidDb  map[string]any  // state -> since
	permitDb  map[string]any  // model-forbidden state -> since
	current   map[string]bool
	visitDb   map[string]int
	takenDb   map[Transition]int
	traceList []TraceEntry
	BreachN   int
}

// sortedKeys
//
// RETURN: []string, the keys of 'set' whose value is true, sorted.
func sortedKeys(set map[string]bool) []string {
	result := make([]string, 0, len(set))
	for key, value := range set {
		if value {
			result = append(result, key)
		}
	}
	sort.Strings(result)
	return result
}

// quotedList
//
// RETURN: string, every name of 'nameList' in single quotes, separated by
// ', '.
func quotedList(nameList []string) string {
	text := make([]string, len(nameList))
	for i, name := range nameList {
		text[i] = "'" + name + "'"
	}
	return strings.Join(text, ", ")
}

// New
//
// RETURN: (*Machine, nil), standing in 'initial', if success;
// (nil, *FsmError), else -- a DFA with two transitions for one (state,
// event); a forbidden or final state no transition names.
//
// 'transitionList' are the (state, event, state) triples; 'forbidden' the
// states the system must never enter, 'final' those it may end in.
func New(transitionList []Transition, initial string, forbidden, final []string, option ...Option) (*Machine, error) {
	o := options{dfaF: true, name: "fsm", write: func(line string) { fmt.Println(line) }}
	for _, set := range option {
		set(&o)
	}
	self := &Machine{Name: o.name, DfaF: o.dfaF, write: o.write, edgeDb: map[edgeKey]map[string]bool{},
		Initial: initial, modelForbidden: map[string]bool{}, final: map[string]bool{}}
	stateSet := map[string]bool{initial: true}
	for _, state := range o.states {
		stateSet[state] = true
	}
	for _, t := range transitionList {
		key := edgeKey{t.Source, t.Event}
		targetSet := self.edgeDb[key]
		if targetSet == nil {
			targetSet = map[string]bool{}
			self.edgeDb[key] = targetSet
		}
		if self.DfaF && len(targetSet) != 0 && !targetSet[t.Target] {
			return nil, fsmError("'%s' --(%s)--> '%s' and '%s': a DFA moves one way per event -- or 'DFA=False'",
				t.Source, t.Event, sortedKeys(targetSet)[0], t.Target)
		}
		targetSet[t.Target] = true
		stateSet[t.Source], stateSet[t.Target] = true, true
	}
	for _, state := range forbidden {
		self.modelForbidden[state] = true
	}
	for _, state := range final {
		self.final[state] = true
	}
	for _, chosen := range []struct {
		label string
		set   map[string]bool
	}{{"forbidden", self.modelForbidden}, {"final", self.final}} {
		var unknown []string
		for _, state := range sortedKeys(chosen.set) {
			if !stateSet[state] {
				unknown = append(unknown, state)
			}
		}
		if len(unknown) != 0 {
			return nil, fsmError("%s state(s) %s: named nowhere else in the model", chosen.label, quotedList(unknown))
		}
	}
	for state := range self.modelForbidden {
		stateSet[state] = true
	}
	self.StateList = sortedKeys(stateSet)
	eventSet := map[string]bool{}
	for key := range self.edgeDb {
		eventSet[key.event] = true
	}
	self.EventList = sortedKeys(eventSet)
	self.Reset()
	return self, nil
}

// ------------------------------------------------------------------- reading

// THE TEXT OF A MODEL (see 'FromString'). Python's '\s' and '\w' are
// Unicode's: so are these.
const space = `[\t\n\x0b\f\r \x{1c}-\x{1f}\x{85}\p{Z}]`

var arrowRe = regexp.MustCompile(`-+` + space + `*\(` + space + `*([^()]*?)` + space + `*\)` + space + `*-*>`)
var nameRe = regexp.MustCompile(`^(?:state` + space + `+)?([A-Za-z_][\p{L}\p{N}_.\-]*)$`)
var keyRe = regexp.MustCompile(`^(initial|forbidden|final)` + space + `*:` + space + `*(.*)$`)

// nameOf
//
// RETURN: (string, nil), the state named by 'text' -- 'A' or 'state A' --
// if success; ("", *FsmError) naming line 'number', else.
func nameOf(text string, number int) (string, error) {
	found := nameRe.FindStringSubmatch(pytext.Strip(text))
	if found == nil {
		return "", fsmError("line %d: '%s' names no state -- a state is a word ('A', 'state A')",
			number, pytext.Strip(text))
	}
	return found[1], nil
}

// arrowSplit
//
// RETURN: []string, 'line' split at every arrow, each arrow's event kept
// between the pieces -- [state, event, state, event, state ...], as
// Python's 're.split' with a group gives it.
func arrowSplit(line string) []string {
	var result []string
	begin := 0
	for _, at := range arrowRe.FindAllStringSubmatchIndex(line, -1) {
		result = append(result, line[begin:at[0]], line[at[2]:at[3]])
		begin = at[1]
	}
	return append(result, line[begin:])
}

// FromString
//
// RETURN: (*Machine, nil), the model the text states, if success;
// (nil, *FsmError) naming the line, else.
//
// One statement per line; '#' starts a comment:
//
//	initial: A              where the machine starts; default: the first
//	                        state the text names
//	forbidden: X, Y         states the system must never enter
//	final: A, B             states it may end in
//	state A                 a state, transitions or not
//	A ---( ev )---> B ---( ev2 )---> C
//	                        transitions, chained
//	:  ---( ev )---> D      ':' is the state that began the line above
func FromString(text string, option ...Option) (*Machine, error) {
	o := options{dfaF: true}
	for _, set := range option {
		set(&o)
	}
	type lineOfEntry struct {
		target string
		number int
	}
	var tripleList []Transition
	var headOnlyList []string
	declared := map[string][]string{}
	lineOf := map[edgeKey]lineOfEntry{}
	first, previousHead := "", ""
	firstF, previousF := false, false
	for i, raw := range pytext.SplitLines(text) {
		number := i + 1
		line := pytext.Strip(strings.SplitN(raw, "#", 2)[0])
		if line == "" {
			continue
		}
		if key := keyRe.FindStringSubmatch(line); key != nil {
			word, rest := key[1], key[2]
			var nameList []string
			for _, part := range strings.Split(rest, ",") {
				if pytext.Strip(part) == "" {
					continue
				}
				name, err := nameOf(part, number)
				if err != nil {
					return nil, err
				}
				nameList = append(nameList, name)
			}
			if word == "initial" && len(nameList) != 1 {
				return nil, fsmError("line %d: 'initial:' names one state", number)
			}
			declared[word] = append(declared[word], nameList...)
			continue
		}
		partList := arrowSplit(line)
		if len(partList) == 1 {
			head, err := nameOf(line, number)
			if err != nil {
				return nil, err
			}
			if !firstF {
				first, firstF = head, true
			}
			headOnlyList = append(headOnlyList, head)
			previousHead, previousF = head, true
			continue
		}
		for i := 1; i < len(partList); i += 2 {
			if pytext.Strip(partList[i]) == "" {
				return nil, fsmError("line %d: an arrow names no event -- '---( event )--->'", number)
			}
		}
		var head string
		if headText := pytext.Strip(partList[0]); headText == ":" {
			if !previousF {
				return nil, fsmError("line %d: ':' stands for the state of the line above, and none stands there", number)
			}
			head = previousHead
		} else {
			var err error
			if head, err = nameOf(headText, number); err != nil {
				return nil, err
			}
		}
		if !firstF {
			first, firstF = head, true
		}
		previousHead, previousF = head, true
		source := head
		for i := 1; i < len(partList); i += 2 {
			target, err := nameOf(partList[i+1], number)
			if err != nil {
				return nil, err
			}
			event := pytext.Strip(partList[i])
			key := edgeKey{source, event}
			//  THE DFA'S CONFLICT NAMED WHERE IT STANDS: both lines.
			if seen, found := lineOf[key]; o.dfaF && found && seen.target != target {
				return nil, fsmError("line %d: '%s' --(%s)--> '%s', and line %d: --> '%s' -- a DFA moves one way per event, or 'DFA=False'",
					number, source, event, target, seen.number, seen.target)
			}
			if _, found := lineOf[key]; !found {
				lineOf[key] = lineOfEntry{target, number}
			}
			tripleList = append(tripleList, Transition{source, event, target})
			source = target
		}
	}
	initialList, initialF := declared["initial"]
	if !firstF && !initialF {
		return nil, fsmError("the model names no state")
	}
	initial := first
	if len(initialList) != 0 {
		initial = initialList[0]
	}
	return New(tripleList, initial, declared["forbidden"], declared["final"], append(option, States(headOnlyList...))...)
}

// ToString
//
// RETURN: string, the model in the text 'FromString' reads, one transition
// per line, sorted -- what a book page or a GOOD file can show of it.
func (self *Machine) ToString() string {
	lineList := []string{"initial: " + self.Initial}
	if len(self.modelForbidden) != 0 {
		lineList = append(lineList, "forbidden: "+strings.Join(sortedKeys(self.modelForbidden), ", "))
	}
	if len(self.final) != 0 {
		lineList = append(lineList, "final: "+strings.Join(sortedKeys(self.final), ", "))
	}
	named := map[string]bool{self.Initial: true}
	for _, edge := range self.edgeList() {
		lineList = append(lineList, fmt.Sprintf("%s ---( %s )---> %s", edge.Source, edge.Event, edge.Target))
		named[edge.Source], named[edge.Target] = true, true
	}
	for _, state := range self.StateList {
		if !named[state] && !self.modelForbidden[state] {
			lineList = append(lineList, "state "+state)
		}
	}
	return strings.Join(lineList, "\n")
}

// edgeList
//
// RETURN: []Transition, every transition of the model, sorted by source,
// event, target.
func (self *Machine) edgeList() []Transition {
	var result []Transition
	for key, targetSet := range self.edgeDb {
		for target := range targetSet {
			result = append(result, Transition{key.state, key.event, target})
		}
	}
	sort.Slice(result, func(i, j int) bool { return transitionLess(result[i], result[j]) })
	return result
}

// transitionLess
//
// RETURN: bool, true where 'a' sorts before 'b' -- by source, event, target.
func transitionLess(a, b Transition) bool {
	if a.Source != b.Source {
		return a.Source < b.Source
	}
	if a.Event != b.Event {
		return a.Event < b.Event
	}
	return a.Target < b.Target
}

// ------------------------------------------------------------------- running

// whereText
//
// RETURN: string, ' line 3' for the int 3, ' <text>' for any other value,
// "" for nil -- the place a breach line names.
func whereText(where any) string {
	switch w := where.(type) {
	case nil:
		return ""
	case int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64:
		return fmt.Sprintf(" line %d", w)
	}
	return fmt.Sprintf(" %v", where)
}

// sinceText
//
// RETURN: string, ' since line 9' for the int 9, ' since <text>' for any
// other value, "" for nil -- when a mask or a forbidden state began.
func sinceText(where any) string {
	if where == nil {
		return ""
	}
	return " since" + whereText(where)
}

// Reset
//
// RETURN: nothing; the machine stands in its initial state again, under the
// model as written: what was seen is forgotten, and so is every mask and
// every state forbidden or permitted since.
func (self *Machine) Reset() {
	self.maskDb = map[maskKey]any{}
	self.forbidDb = map[string]any{}
	for state := range self.modelForbidden {
		self.forbidDb[state] = nil
	}
	self.permitDb = map[string]any{}
	self.current = map[string]bool{self.Initial: true}
	self.visitDb = map[string]int{self.Initial: 1}
	self.takenDb = map[Transition]int{}
	self.traceList = nil
	self.BreachN = 0
}

// Fire
//
// RETURN: bool, true where 'event' moved the machine and entered no
// forbidden state; false where it was not allowed where the machine stands
// -- a BREACH line is written and the machine stays -- or where it entered a
// forbidden state, which is written too. 'where' is the place the breach
// line names.
func (self *Machine) Fire(event string, where any) bool {
	moved := map[string]bool{}
	var masked []string
	for _, state := range sortedKeys(self.current) {
		key := edgeKey{state, event}
		if self.maskedF(state, event) {
			if _, found := self.edgeDb[key]; found {
				masked = append(masked, state)
			}
			continue
		}
		for _, target := range sortedKeys(self.edgeDb[key]) {
			moved[target] = true
			self.takenDb[Transition{state, event, target}]++
			self.traceList = append(self.traceList, TraceEntry{where, state, event, target})
		}
	}
	if len(moved) == 0 {
		self.BreachN++
		hint := "no event leaves it"
		if allowed := self.Allowed(); len(allowed) != 0 {
			hint = "allowed: " + strings.Join(allowed, ", ")
		}
		if !self.knownEventF(event) {
			hint = "an event the model never names"
		} else if len(masked) != 0 {
			since, found := self.maskDb[maskKey{false, masked[0], event}]
			if !found {
				since = self.maskDb[maskKey{true, "", event}]
			}
			hint = "disallowed" + sinceText(since)
		}
		self.write(fmt.Sprintf("BREACH%s: '%s' in %s -- %s", whereText(where), event, self.here(), hint))
		return false
	}
	self.current = moved
	for state := range moved {
		self.visitDb[state]++
	}
	var entered []string
	for _, state := range sortedKeys(moved) {
		if _, found := self.forbidDb[state]; found {
			entered = append(entered, state)
		}
	}
	for _, state := range entered {
		self.BreachN++
		why := "forbidden" + sinceText(self.forbidDb[state])
		if self.modelForbidden[state] && self.forbidDb[state] == nil {
			why = "a forbidden state"
		}
		self.write(fmt.Sprintf("BREACH%s: '%s' entered by '%s' -- %s", whereText(where), state, event, why))
	}
	return len(entered) == 0
}

// --------------------------------------------------------- the law, changing

// Forbidden
//
// RETURN: []string, the states forbidden NOW, sorted -- the model's, less
// those permitted, with those forbidden since.
func (self *Machine) Forbidden() []string {
	result := make([]string, 0, len(self.forbidDb))
	for state := range self.forbidDb {
		result = append(result, state)
	}
	sort.Strings(result)
	return result
}

// maskedF
//
// RETURN: bool, true where 'event' is disallowed in 'state' now -- in every
// state, or in that one.
func (self *Machine) maskedF(state, event string) bool {
	_, every := self.maskDb[maskKey{true, "", event}]
	_, one := self.maskDb[maskKey{false, state, event}]
	return every || one
}

// knownEventF
//
// RETURN: bool, true where the model names 'event'.
func (self *Machine) knownEventF(event string) bool {
	i := sort.SearchStrings(self.EventList, event)
	return i < len(self.EventList) && self.EventList[i] == event
}

// knownStateF
//
// RETURN: bool, true where the model names 'state'.
func (self *Machine) knownStateF(state string) bool {
	i := sort.SearchStrings(self.StateList, state)
	return i < len(self.StateList) && self.StateList[i] == state
}

// known
//
// RETURN: error, nil where 'event' and 'state' are named by the model (an
// empty one is not asked); *FsmError naming what is not, else -- a mask
// over a word the model never names would guard nothing.
func (self *Machine) known(event, state string) error {
	if event != "" && !self.knownEventF(event) {
		return fsmError("'%s': an event the model never names -- events: %s", event, strings.Join(self.EventList, ", "))
	}
	if state != "" && !self.knownStateF(state) {
		return fsmError("'%s': a state the model never names -- states: %s", state, strings.Join(self.StateList, ", "))
	}
	return nil
}

// maskKeyOf
//
// RETURN: maskKey, the scope 'state' names -- every state where "".
func maskKeyOf(state, event string) maskKey {
	return maskKey{state == "", state, event}
}

// Disallow
//
// RETURN: error, nil -- from now on 'event' is a breach, in 'state' alone or
// in every state where "", until 'Allow' lifts it; the breach line says
// 'disallowed since <where>'. *FsmError where the model names no such
// event or state.
func (self *Machine) Disallow(event, state string, where any) error {
	if err := self.known(event, state); err != nil {
		return err
	}
	if _, found := self.maskDb[maskKeyOf(state, event)]; !found {
		self.maskDb[maskKeyOf(state, event)] = where
	}
	return nil
}

// Allow
//
// RETURN: error, nil -- the mask 'Disallow(event, state)' set is lifted; a
// mask set for another scope stays. *FsmError where the model names no
// such event or state.
func (self *Machine) Allow(event, state string) error {
	if err := self.known(event, state); err != nil {
		return err
	}
	delete(self.maskDb, maskKeyOf(state, event))
	return nil
}

// Forbid
//
// RETURN: error, nil -- from now on entering 'state' is a breach, until
// 'Permit'; where the machine STANDS in it, one BREACH line is written at
// once: the test forbade the present. *FsmError where the model names no
// such state.
func (self *Machine) Forbid(state string, where any) error {
	if err := self.known("", state); err != nil {
		return err
	}
	if _, found := self.forbidDb[state]; found {
		return nil
	}
	self.forbidDb[state] = where
	delete(self.permitDb, state)
	if self.current[state] {
		self.BreachN++
		self.write(fmt.Sprintf("BREACH%s: stands in '%s' -- forbidden%s", whereText(where), state, sinceText(where)))
	}
	return nil
}

// Permit
//
// RETURN: error, nil -- 'state' is no longer forbidden, a state of the
// model's own 'forbidden:' too, until 'Forbid' again. *FsmError where the
// model names no such state.
func (self *Machine) Permit(state string, where any) error {
	if err := self.known("", state); err != nil {
		return err
	}
	if _, found := self.forbidDb[state]; found {
		delete(self.forbidDb, state)
		if self.modelForbidden[state] {
			self.permitDb[state] = where
		}
	}
	return nil
}

// Disallowed
//
// RETURN: error, nil once 'block' ran with 'event' disallowed (see
// 'Disallow'), allowed again on leaving it -- whatever way, a panic
// included; *FsmError, and 'block' not run, where the model names no such
// event or state. Python's 'with m.disallowed(...)'.
func (self *Machine) Disallowed(event, state string, where any, block func()) error {
	if err := self.Disallow(event, state, where); err != nil {
		return err
	}
	defer self.Allow(event, state)
	block()
	return nil
}

// Forbidding
//
// RETURN: error, nil once 'block' ran with 'state' forbidden (see
// 'Forbid'), permitted again on leaving it -- whatever way; *FsmError, and
// 'block' not run, where the model names no such state.
func (self *Machine) Forbidding(state string, where any, block func()) error {
	if err := self.Forbid(state, where); err != nil {
		return err
	}
	defer self.Permit(state, nil)
	block()
	return nil
}

// here
//
// RETURN: string, where the machine stands: "'idle'", or "{'a', 'b'}" for a
// set.
func (self *Machine) here() string {
	stateList := sortedKeys(self.current)
	if len(stateList) == 1 {
		return "'" + stateList[0] + "'"
	}
	return "{" + quotedList(stateList) + "}"
}

// ----------------------------------------------------------------- questions

// State
//
// RETURN: (string, nil), the one state the machine stands in, if success;
// ("", *FsmError), else -- a set of states stands (DFA(false)): ask
// 'Current'.
func (self *Machine) State() (string, error) {
	if len(self.current) != 1 {
		return "", fsmError("the machine stands in %s: ask 'current()'", self.here())
	}
	return sortedKeys(self.current)[0], nil
}

// Current
//
// RETURN: []string, every state the machine stands in, sorted.
func (self *Machine) Current() []string { return sortedKeys(self.current) }

// InState
//
// RETURN: bool, true where the machine stands in 'state'.
func (self *Machine) InState(state string) bool { return self.current[state] }

// Can
//
// RETURN: bool, true where 'event' would move the machine now.
func (self *Machine) Can(event string) bool {
	for state := range self.current {
		if _, found := self.edgeDb[edgeKey{state, event}]; found && !self.maskedF(state, event) {
			return true
		}
	}
	return false
}

// Allowed
//
// RETURN: []string, the events that would move the machine now, sorted.
func (self *Machine) Allowed() []string {
	eventSet := map[string]bool{}
	for key := range self.edgeDb {
		if self.current[key.state] && !self.maskedF(key.state, key.event) {
			eventSet[key.event] = true
		}
	}
	return sortedKeys(eventSet)
}

// Trace
//
// RETURN: []TraceEntry, every transition fired, in order.
func (self *Machine) Trace() []TraceEntry { return append([]TraceEntry(nil), self.traceList...) }

// --------------------------------------------------------- the model alone

// eventTarget is one (event, state) pair leaving a state.
type eventTarget struct{ event, target string }

// successorDb
//
// RETURN: map, state -> the (event, state) pairs leaving it, sorted --
// under the masks where 'maskedF', as written else.
func (self *Machine) successorDb(maskedF bool) map[string][]eventTarget {
	found := map[string][]eventTarget{}
	for key, targetSet := range self.edgeDb {
		if maskedF && self.maskedF(key.state, key.event) {
			continue
		}
		for target := range targetSet {
			found[key.state] = append(found[key.state], eventTarget{key.event, target})
		}
	}
	for _, pairList := range found {
		sort.Slice(pairList, func(i, j int) bool {
			if pairList[i].event != pairList[j].event {
				return pairList[i].event < pairList[j].event
			}
			return pairList[i].target < pairList[j].target
		})
	}
	return found
}

// PathTo
//
// RETURN: ([]string, true), the shortest sequence of events from 'start' --
// the initial state where "", the present where "now" -- into 'state', if
// one exists (empty where 'start' is 'state'); (nil, false), else: 'state'
// cannot be reached from there. Among equally short paths, the one first in
// event order. Under the masks standing now where 'maskedF', the model as
// written else.
func (self *Machine) PathTo(state, start string, maskedF bool) ([]string, bool) {
	startSet := map[string]bool{}
	switch start {
	case "now":
		for s := range self.current {
			startSet[s] = true
		}
	case "":
		startSet[self.Initial] = true
	default:
		startSet[start] = true
	}
	if startSet[state] {
		return []string{}, true
	}
	successorDb := self.successorDb(maskedF)
	type step struct {
		here string
		path []string
	}
	var queue []step
	for _, s := range sortedKeys(startSet) {
		queue = append(queue, step{s, nil})
	}
	seen := startSet
	for len(queue) != 0 {
		here := queue[0]
		queue = queue[1:]
		for _, pair := range successorDb[here.here] {
			if seen[pair.target] {
				continue
			}
			path := append(append([]string{}, here.path...), pair.event)
			if pair.target == state {
				return path, true
			}
			seen[pair.target] = true
			queue = append(queue, step{pair.target, path})
		}
	}
	return nil, false
}

// StateReachable
//
// RETURN: bool, true where 'state' can be reached from 'start' (see
// 'PathTo').
func (self *Machine) StateReachable(state, start string, maskedF bool) bool {
	_, found := self.PathTo(state, start, maskedF)
	return found
}

// forbiddenOf
//
// RETURN: map, the states forbidden now where 'maskedF', the model's own
// else.
func (self *Machine) forbiddenOf(maskedF bool) map[string]bool {
	if !maskedF {
		return self.modelForbidden
	}
	result := map[string]bool{}
	for state := range self.forbidDb {
		result[state] = true
	}
	return result
}

// Unreachable
//
// RETURN: []string, the states no path from the initial state reaches,
// forbidden ones left out -- sorted; under the masks where 'maskedF'.
func (self *Machine) Unreachable(maskedF bool) []string {
	forbidden := self.forbiddenOf(maskedF)
	var result []string
	for _, state := range self.StateList {
		if !forbidden[state] && !self.StateReachable(state, "", maskedF) {
			result = append(result, state)
		}
	}
	return result
}

// DeadEnds
//
// RETURN: []string, the states no event leaves that are neither final nor
// forbidden -- where a system would hang -- sorted; under the masks where
// 'maskedF' (a mask can make one).
func (self *Machine) DeadEnds(maskedF bool) []string {
	successorDb := self.successorDb(maskedF)
	forbidden := self.forbiddenOf(maskedF)
	var result []string
	for _, state := range self.StateList {
		if _, found := successorDb[state]; !found && !self.final[state] && !forbidden[state] {
			result = append(result, state)
		}
	}
	return result
}

// ForbiddenReachable
//
// RETURN: []string, the forbidden states the model lets the system reach
// from the initial state -- sorted; under the masks and the states
// forbidden now where 'maskedF'.
func (self *Machine) ForbiddenReachable(maskedF bool) []string {
	var result []string
	for _, state := range sortedKeys(self.forbiddenOf(maskedF)) {
		if self.StateReachable(state, "", maskedF) {
			result = append(result, state)
		}
	}
	return result
}

// Check
//
// RETURN: int, how many findings the MODEL has, each written as one line
// 'MODEL: ...'; 0 where it has none. Asked of the model alone: states no
// path reaches, dead ends, forbidden states the model allows to be reached
// (each with the shortest way there) -- under the masks where 'maskedF'.
func (self *Machine) Check(maskedF bool) int {
	var lineList []string
	for _, state := range self.Unreachable(maskedF) {
		lineList = append(lineList, fmt.Sprintf("MODEL: '%s' cannot be reached", state))
	}
	for _, state := range self.DeadEnds(maskedF) {
		lineList = append(lineList, fmt.Sprintf("MODEL: '%s' is a dead end -- no event leaves it", state))
	}
	for _, state := range self.ForbiddenReachable(maskedF) {
		path, _ := self.PathTo(state, "", maskedF)
		lineList = append(lineList, fmt.Sprintf("MODEL: forbidden '%s' is reachable: %s", state, strings.Join(path, " ")))
	}
	for _, line := range lineList {
		self.write(line)
	}
	return len(lineList)
}

// ------------------------------------------------------------------ the end

// Report
//
// RETURN: int, the breaches seen, counting a non-final end; written before
// it, sorted, what the events covered of the model -- states counted
// without the forbidden ones:
//
//	fsm: 3 of 3 states visited, 3 of 4 transitions taken, 1 breach
//	  taken      idle ---( request )---> waiting   x2
//	  not taken  busy ---( fault )---> crashed
//	  never in   ...
//	  ended in   'idle'
//
// A machine with final states that ends elsewhere adds a BREACH line.
func (self *Machine) Report() int {
	allEdge := self.edgeList()
	breachN := self.BreachN
	endF := len(self.final) == 0
	for state := range self.current {
		endF = endF || self.final[state]
	}
	if !endF {
		breachN++
	}
	//  A FORBIDDEN STATE IS NO GOAL OF COVERAGE: counted out.
	goalN, visitedN := 0, 0
	for _, state := range self.StateList {
		if self.modelForbidden[state] {
			continue
		}
		goalN++
		if _, found := self.visitDb[state]; found {
			visitedN++
		}
	}
	plural := "es"
	if breachN == 1 {
		plural = ""
	}
	self.write(fmt.Sprintf("%s: %d of %d states visited, %d of %d transitions taken, %d breach%s",
		self.Name, visitedN, goalN, len(self.takenDb), len(allEdge), breachN, plural))
	for _, edge := range allEdge {
		n := self.takenDb[edge]
		label, count := "not taken", ""
		if n != 0 {
			label = "taken    "
		}
		if n > 1 {
			count = fmt.Sprintf("   x%d", n)
		}
		self.write(fmt.Sprintf("  %s  %s ---( %s )---> %s%s", label, edge.Source, edge.Event, edge.Target, count))
	}
	for _, state := range self.StateList {
		if _, found := self.visitDb[state]; !found && !self.modelForbidden[state] {
			self.write(fmt.Sprintf("  never in   '%s'", state))
		}
	}
	self.write("  ended in   " + self.here())
	//  A PHASE NEVER LIFTED IS SAID: what still stands at the end.
	maskList := make([]maskKey, 0, len(self.maskDb))
	for key := range self.maskDb {
		maskList = append(maskList, key)
	}
	sort.Slice(maskList, func(i, j int) bool {
		if maskList[i].event != maskList[j].event {
			return maskList[i].event < maskList[j].event
		}
		return maskList[i].state < maskList[j].state
	})
	for _, key := range maskList {
		scope := "in every state"
		if !key.everyF {
			scope = "in '" + key.state + "'"
		}
		self.write(fmt.Sprintf("  disallowed '%s' %s%s", key.event, scope, sinceText(self.maskDb[key])))
	}
	for _, state := range self.Forbidden() {
		if !self.modelForbidden[state] {
			self.write(fmt.Sprintf("  forbidden  '%s'%s", state, sinceText(self.forbidDb[state])))
		}
	}
	permitList := make([]string, 0, len(self.permitDb))
	for state := range self.permitDb {
		permitList = append(permitList, state)
	}
	sort.Strings(permitList)
	for _, state := range permitList {
		self.write(fmt.Sprintf("  permitted  '%s'%s", state, sinceText(self.permitDb[state])))
	}
	if !endF {
		self.write(fmt.Sprintf("BREACH: ended in %s -- final: %s", self.here(), strings.Join(sortedKeys(self.final), ", ")))
	}
	return breachN
}
