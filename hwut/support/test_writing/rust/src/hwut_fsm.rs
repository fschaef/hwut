// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
//          port of 'python/hwut_fsm.py' (README-hwut_fsm.txt). The states it
//          may be in, the events that move it, the states it must never
//          reach. A test FIRES the events it observes; every event the model
//          does not allow, and every forbidden state entered, is WRITTEN as a
//          line -- so it lands in the GOOD file and the comparison judges it.
//
//     use hwut::hwut_fsm::{Machine, Where};
//     let mut m = Machine::from_string("
//         initial: idle
//         forbidden: crashed
//         idle    ---( request )---> waiting ---( grant )---> busy
//         busy    ---( release )---> idle
//         :       ---( fault )--->   crashed
//     ", true, "fsm")?;
//     m.fire("request", 1);       // true
//     m.fire("release", 2);       // BREACH line 2: 'release' in 'waiting' -- allowed: grant
//     m.report();                 // what was visited, what never was
//
// The same model text, the same words, the same sorted reports as Python.
// WHAT PYTHON RAISES (FsmError) is returned: 'Err(FsmError)', its message
// Python's text. 'where' -- the place a breach line names -- is a 'Where':
// an integer names a line ('line 3'), a text stands as written,
// 'Where::Nowhere' (Python's None) names no place. Every line goes through
// 'write' -- stdout by default.
//
// THE CONTEXT MANAGERS 'disallowed()' and 'forbidding()' take the block as a
// closure that is handed the machine:
//
//     m.disallowed("release", Some("busy"), "phase", |m| { m.fire("release", 20); })?;
//______________________________________________________________________________
use std::collections::{BTreeMap, BTreeSet, HashMap, VecDeque};
use std::fmt;

/// A model that cannot be meant, or a word the model never names.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FsmError(pub String);

impl fmt::Display for FsmError {
    /// RETURN: fmt::Result; the message, as Python's 'str(FsmError)'.
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { write!(f, "{}", self.0) }
}

impl std::error::Error for FsmError {}

/// The place a breach line names, or since when a mask stands.
#[derive(Clone, Debug, PartialEq, Eq, Default)]
pub enum Where {
    /// Python's None: no place.
    #[default]
    Nowhere,
    /// A line number: ' line 3'.
    Line(i64),
    /// A text, standing as written.
    Text(String),
}

impl From<i64>   for Where { fn from(n: i64) -> Where { Where::Line(n) } }
impl From<i32>   for Where { fn from(n: i32) -> Where { Where::Line(n as i64) } }
impl From<usize> for Where { fn from(n: usize) -> Where { Where::Line(n as i64) } }
impl From<&str>  for Where { fn from(t: &str) -> Where { Where::Text(t.to_string()) } }
impl From<String> for Where { fn from(t: String) -> Where { Where::Text(t) } }
impl From<&Where> for Where { fn from(w: &Where) -> Where { w.clone() } }

impl fmt::Display for Where {
    /// RETURN: fmt::Result; the place as Python's 'str()' writes it: the
    ///         number, the text, or 'None'.
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            Where::Nowhere  => write!(f, "None"),
            Where::Line(n)  => write!(f, "{}", n),
            Where::Text(t)  => write!(f, "{}", t),
        }
    }
}

/// RETURN: String, ' line 3' for a line, ' <text>' for a text, '' for
///         Nowhere -- the place a breach line names.
fn where_text(place: &Where) -> String {
    match place {
        Where::Nowhere => String::new(),
        Where::Line(n) => format!(" line {}", n),
        Where::Text(t) => format!(" {}", t),
    }
}

/// RETURN: String, ' since line 9', ' since <text>', or '' for Nowhere --
///         when a mask or a forbidden state began.
fn since_text(place: &Where) -> String {
    if *place == Where::Nowhere { String::new() } else { format!(" since{}", where_text(place)) }
}

/// RETURN: bool, true where 'c' is a blank as Python's 'str.isspace' says.
fn py_isspace(c: char) -> bool { c.is_whitespace() || ('\x1c'..='\x1f').contains(&c) }

/// RETURN: &str, 'text' without blanks at both ends -- Python's 'strip()'.
fn py_strip(text: &str) -> &str { text.trim_matches(py_isspace) }

/// RETURN: Vec<&str>, 'text' cut into lines as Python's 'splitlines()' cuts.
pub(crate) fn py_splitlines(text: &str) -> Vec<&str> {
    let mut result = Vec::new();
    let mut begin  = 0;
    let mut iter   = text.char_indices().peekable();
    while let Some((i, c)) = iter.next() {
        let end_f = matches!(c, '\n' | '\r' | '\x0b' | '\x0c' | '\x1c' | '\x1d' | '\x1e'
                                | '\u{85}' | '\u{2028}' | '\u{2029}');
        if !end_f { continue; }
        result.push(&text[begin..i]);
        let mut next = i + c.len_utf8();
        if c == '\r' {
            if let Some((_, '\n')) = iter.peek() { iter.next(); next += 1; }
        }
        begin = next;
    }
    if begin < text.len() { result.push(&text[begin..]); }
    result
}

/// RETURN: bool, 'text' is a name: '[A-Za-z_][\w.\-]*'.
fn is_name(text: &str) -> bool {
    let mut chars = text.chars();
    match chars.next() {
        Some(c) if c.is_ascii_alphabetic() || c == '_' => {}
        _ => return false,
    }
    chars.all(|c| c.is_alphanumeric() || c == '_' || c == '.' || c == '-')
}

/// RETURN: Ok(String), the state named by 'text' -- 'A' or 'state A';
///         Err(FsmError) naming line 'number', else.
fn name_of(text: &str, number: usize) -> Result<String, FsmError> {
    let t = py_strip(text);
    if is_name(t) { return Ok(t.to_string()); }
    if let Some(rest) = t.strip_prefix("state") {
        if rest.starts_with(py_isspace) {
            let rest = rest.trim_start_matches(py_isspace);
            if is_name(rest) { return Ok(rest.to_string()); }
        }
    }
    Err(FsmError(format!("line {}: '{}' names no state -- a state is a word ('A', 'state A')", number, t)))
}

/// RETURN: Some((end, event)) where an arrow '-+\s*\(\s*event\s*\)\s*-*>'
///         begins at byte 'p' of 'line' -- 'end' after it, 'event' its
///         stripped text; None else.
fn arrow_at(line: &str, p: usize) -> Option<(usize, String)> {
    let b = line.as_bytes();
    let mut q = p;
    if q >= b.len() || b[q] != b'-' { return None; }
    while q < b.len() && b[q] == b'-' { q += 1; }
    q = skip_blank(line, q);
    if q >= b.len() || b[q] != b'(' { return None; }
    let open = q + 1;
    let mut close = open;
    while close < b.len() && b[close] != b')' {
        if b[close] == b'(' { return None; }
        close += 1;
    }
    if close >= b.len() { return None; }
    q = skip_blank(line, close + 1);
    while q < b.len() && b[q] == b'-' { q += 1; }
    if q >= b.len() || b[q] != b'>' { return None; }
    Some((q + 1, py_strip(&line[open..close]).to_string()))
}

/// RETURN: usize, the byte index of the first character at or after 'i'
///         that is no blank.
fn skip_blank(line: &str, i: usize) -> usize {
    match line[i..].char_indices().find(|(_, c)| !py_isspace(*c)) {
        Some((k, _)) => i + k,
        None         => line.len(),
    }
}

type Edge = (String, String, String);

/// A state machine, its current state(s), and what was seen of it.
pub struct Machine {
    pub name:            String,
    pub dfa_f:           bool,
    /// Takes one line; every breach and report goes through it.
    pub write:           Box<dyn FnMut(&str)>,
    pub initial:         String,
    pub model_forbidden: BTreeSet<String>,
    pub final_:          BTreeSet<String>,
    pub state_tuple:     Vec<String>,
    pub event_tuple:     Vec<String>,
    pub breach_n:        usize,
    edge_db:     BTreeMap<(String, String), BTreeSet<String>>,
    mask_db:     HashMap<(Option<String>, String), Where>,
    forbid_db:   BTreeMap<String, Where>,
    permit_db:   BTreeMap<String, Where>,
    current:     BTreeSet<String>,
    visit_db:    HashMap<String, usize>,
    taken_db:    BTreeMap<Edge, usize>,
    trace_list:  Vec<(Where, String, String, String)>,
}

impl Machine {
    /// RETURN: Ok(Machine), standing in 'initial';
    ///         Err(FsmError) -- a DFA with two transitions for one (state,
    ///         event); a forbidden or final state no other part names.
    ///
    /// 'transitions' are (state, event, state) triples; 'states' names
    /// states no transition touches (yet). Lines are written to stdout;
    /// 'write' may be replaced.
    pub fn new(transitions: &[(&str, &str, &str)], initial: &str, forbidden: &[&str],
               final_: &[&str], dfa_f: bool, name: &str, states: &[&str]) -> Result<Machine, FsmError> {
        let mut edge_db: BTreeMap<(String, String), BTreeSet<String>> = BTreeMap::new();
        let mut state_set: BTreeSet<String> = states.iter().map(|s| s.to_string()).collect();
        state_set.insert(initial.to_string());
        for (source, event, target) in transitions {
            let target_set = edge_db.entry((source.to_string(), event.to_string())).or_default();
            if dfa_f && !target_set.is_empty() && !target_set.contains(*target) {
                return Err(FsmError(format!(
                    "'{}' --({})--> '{}' and '{}': a DFA moves one way per event -- or 'DFA=False'",
                    source, event, target_set.iter().next().unwrap(), target)));
            }
            target_set.insert(target.to_string());
            state_set.insert(source.to_string());
            state_set.insert(target.to_string());
        }
        let model_forbidden: BTreeSet<String> = forbidden.iter().map(|s| s.to_string()).collect();
        let final_set: BTreeSet<String>       = final_.iter().map(|s| s.to_string()).collect();
        for (label, chosen) in [("forbidden", &model_forbidden), ("final", &final_set)] {
            let unknown: Vec<String> = chosen.difference(&state_set).map(|s| format!("'{}'", s)).collect();
            if !unknown.is_empty() {
                return Err(FsmError(format!("{} state(s) {}: named nowhere else in the model",
                                            label, unknown.join(", "))));
            }
        }
        let state_tuple: Vec<String> = state_set.union(&model_forbidden).cloned().collect();
        let event_tuple: Vec<String> = edge_db.keys().map(|(_, e)| e.clone())
                                              .collect::<BTreeSet<_>>().into_iter().collect();
        let mut machine = Machine {
            name: name.to_string(), dfa_f, write: Box::new(|line: &str| println!("{}", line)),
            initial: initial.to_string(), model_forbidden, final_: final_set, state_tuple,
            event_tuple, breach_n: 0, edge_db, mask_db: HashMap::new(), forbid_db: BTreeMap::new(),
            permit_db: BTreeMap::new(), current: BTreeSet::new(), visit_db: HashMap::new(),
            taken_db: BTreeMap::new(), trace_list: Vec::new(),
        };
        machine.reset();
        Ok(machine)
    }

    // ------------------------------------------------------------- reading
    /// RETURN: Ok(Machine), the model the text states;
    ///         Err(FsmError) naming the line, else.
    ///
    /// One statement per line; '#' starts a comment:
    ///     initial: A              where the machine starts; default: the
    ///                             first state the text names
    ///     forbidden: X, Y         states the system must never enter
    ///     final: A, B             states it may end in
    ///     state A                 a state, transitions or not
    ///     A ---( ev )---> B ---( ev2 )---> C     transitions, chained
    ///     :  ---( ev )---> D      ':' is the state that began the line above
    pub fn from_string(text: &str, dfa_f: bool, name: &str) -> Result<Machine, FsmError> {
        let mut triple_list: Vec<(String, Option<String>, Option<String>)> = Vec::new();
        let mut declared: HashMap<&str, Vec<String>> = HashMap::new();
        let mut line_of: HashMap<(String, String), (String, usize)> = HashMap::new();
        let mut first: Option<String> = None;
        let mut previous_head: Option<String> = None;
        for (i, raw) in py_splitlines(text).into_iter().enumerate() {
            let number = i + 1;
            let line = py_strip(raw.split('#').next().unwrap_or(""));
            if line.is_empty() { continue; }
            //  KEY: 'initial:', 'forbidden:', 'final:'
            let mut key: Option<(&str, &str)> = None;
            for word in ["initial", "forbidden", "final"] {
                if let Some(rest) = line.strip_prefix(word) {
                    let rest = rest.trim_start_matches(py_isspace);
                    if let Some(rest) = rest.strip_prefix(':') { key = Some((word, rest)); break; }
                }
            }
            if let Some((word, rest)) = key {
                let mut name_list = Vec::new();
                for part in rest.split(',') {
                    if py_strip(part).is_empty() { continue; }
                    name_list.push(name_of(part, number)?);
                }
                if word == "initial" && name_list.len() != 1 {
                    return Err(FsmError(format!("line {}: 'initial:' names one state", number)));
                }
                declared.entry(word).or_default().extend(name_list);
                continue;
            }
            //  THE PARTS: [state, event, state, event, state ...]
            let mut part_list: Vec<String> = Vec::new();
            let (mut at, mut start) = (0, 0);
            while at < line.len() {
                if let Some((end, event)) = arrow_at(line, at) {
                    part_list.push(line[start..at].to_string());
                    part_list.push(event);
                    at = end; start = end;
                } else {
                    at += line[at..].chars().next().map_or(1, |c| c.len_utf8());
                }
            }
            part_list.push(line[start..].to_string());
            if part_list.len() == 1 {
                let head = name_of(line, number)?;
                if first.is_none() { first = Some(head.clone()); }
                triple_list.push((head.clone(), None, None));
                previous_head = Some(head);
                continue;
            }
            if (1..part_list.len()).step_by(2).any(|i| py_strip(&part_list[i]).is_empty()) {
                return Err(FsmError(format!("line {}: an arrow names no event -- '---( event )--->'", number)));
            }
            let head_text = py_strip(&part_list[0]);
            let head = if head_text == ":" {
                match &previous_head {
                    Some(h) => h.clone(),
                    None => return Err(FsmError(format!(
                        "line {}: ':' stands for the state of the line above, and none stands there", number))),
                }
            } else {
                name_of(head_text, number)?
            };
            if first.is_none() { first = Some(head.clone()); }
            previous_head = Some(head.clone());
            let mut source = head;
            for i in (1..part_list.len()).step_by(2) {
                let target = name_of(&part_list[i + 1], number)?;
                let event  = py_strip(&part_list[i]).to_string();
                //  THE DFA'S CONFLICT NAMED WHERE IT STANDS: both lines.
                if let Some((first_target, first_line)) = line_of.get(&(source.clone(), event.clone())) {
                    if dfa_f && *first_target != target {
                        return Err(FsmError(format!(
                            "line {}: '{}' --({})--> '{}', and line {}: --> '{}' -- a DFA moves one way per event, or 'DFA=False'",
                            number, source, event, target, first_line, first_target)));
                    }
                }
                line_of.entry((source.clone(), event.clone())).or_insert((target.clone(), number));
                triple_list.push((source.clone(), Some(event), Some(target.clone())));
                source = target;
            }
        }
        if first.is_none() && !declared.contains_key("initial") {
            return Err(FsmError("the model names no state".to_string()));
        }
        let initial = match declared.get("initial") {
            Some(list) if !list.is_empty() => list[0].clone(),
            _ => first.unwrap(),
        };
        let transitions: Vec<(&str, &str, &str)> = triple_list.iter()
            .filter_map(|(s, e, t)| Some((s.as_str(), e.as_deref()?, t.as_deref()?))).collect();
        let alone: BTreeSet<&str> = triple_list.iter().filter(|t| t.1.is_none()).map(|t| t.0.as_str()).collect();
        let alone: Vec<&str> = alone.into_iter().collect();
        let empty = Vec::new();
        let forbidden: Vec<&str> = declared.get("forbidden").unwrap_or(&empty).iter().map(|s| s.as_str()).collect();
        let final_: Vec<&str>    = declared.get("final").unwrap_or(&empty).iter().map(|s| s.as_str()).collect();
        Machine::new(&transitions, &initial, &forbidden, &final_, dfa_f, name, &alone)
    }

    /// RETURN: String, the model in the text 'from_string' reads, one
    ///         transition per line, sorted.
    pub fn to_string(&self) -> String {
        let mut line_list = vec![format!("initial: {}", self.initial)];
        if !self.model_forbidden.is_empty() {
            line_list.push(format!("forbidden: {}", join(self.model_forbidden.iter())));
        }
        if !self.final_.is_empty() { line_list.push(format!("final: {}", join(self.final_.iter()))); }
        let mut named: BTreeSet<&String> = BTreeSet::new();
        named.insert(&self.initial);
        for ((source, event), target_set) in &self.edge_db {
            for target in target_set {
                line_list.push(format!("{} ---( {} )---> {}", source, event, target));
                named.insert(source);
                named.insert(target);
            }
        }
        for s in &self.state_tuple {
            if !named.contains(s) && !self.model_forbidden.contains(s) { line_list.push(format!("state {}", s)); }
        }
        line_list.join("\n")
    }

    // ------------------------------------------------------------- running
    /// RETURN: nothing; the machine stands in its initial state again, under
    ///         the model as written: what was seen is forgotten, and so is
    ///         every mask and every state forbidden or permitted since.
    pub fn reset(&mut self) {
        self.mask_db.clear();
        self.forbid_db  = self.model_forbidden.iter().map(|s| (s.clone(), Where::Nowhere)).collect();
        self.permit_db.clear();
        self.current    = [self.initial.clone()].into_iter().collect();
        self.visit_db   = [(self.initial.clone(), 1)].into_iter().collect();
        self.taken_db.clear();
        self.trace_list.clear();
        self.breach_n   = 0;
    }

    /// RETURN: nothing; 'line' went through 'write'.
    fn say(&mut self, line: &str) { (self.write)(line); }

    /// RETURN: bool, true where 'event' moved the machine and entered no
    ///         forbidden state; false where it was not allowed where the
    ///         machine stands -- a BREACH line is written and the machine
    ///         stays -- or where it entered a forbidden state, which is
    ///         written too.
    pub fn fire(&mut self, event: &str, place: impl Into<Where>) -> bool {
        let place: Where = place.into();
        let mut moved: BTreeSet<String> = BTreeSet::new();
        let mut masked: Vec<String> = Vec::new();
        for state in self.current.clone() {
            let key = (state.clone(), event.to_string());
            if self.masked_f(&state, event) {
                if self.edge_db.contains_key(&key) { masked.push(state); }
                continue;
            }
            if let Some(target_set) = self.edge_db.get(&key) {
                for target in target_set.clone() {
                    moved.insert(target.clone());
                    *self.taken_db.entry((state.clone(), event.to_string(), target.clone())).or_insert(0) += 1;
                    self.trace_list.push((place.clone(), state.clone(), event.to_string(), target));
                }
            }
        }
        if moved.is_empty() {
            self.breach_n += 1;
            let allowed = self.allowed();
            let mut hint = if allowed.is_empty() { "no event leaves it".to_string() }
                           else { format!("allowed: {}", allowed.join(", ")) };
            if !self.event_tuple.iter().any(|e| e == event) {
                hint = "an event the model never names".to_string();
            } else if !masked.is_empty() {
                let since = self.mask_db.get(&(Some(masked[0].clone()), event.to_string()))
                    .or_else(|| self.mask_db.get(&(None, event.to_string())))
                    .cloned().unwrap_or_default();
                hint = format!("disallowed{}", since_text(&since));
            }
            let line = format!("BREACH{}: '{}' in {} -- {}", where_text(&place), event, self.here(), hint);
            self.say(&line);
            return false;
        }
        for state in &moved { *self.visit_db.entry(state.clone()).or_insert(0) += 1; }
        self.current = moved;
        let entered: Vec<String> = self.current.iter().filter(|s| self.forbid_db.contains_key(*s)).cloned().collect();
        for state in &entered {
            self.breach_n += 1;
            let since = self.forbid_db[state].clone();
            let why = if self.model_forbidden.contains(state) && since == Where::Nowhere {
                "a forbidden state".to_string()
            } else {
                format!("forbidden{}", since_text(&since))
            };
            let line = format!("BREACH{}: '{}' entered by '{}' -- {}", where_text(&place), state, event, why);
            self.say(&line);
        }
        entered.is_empty()
    }

    // --------------------------------------------------- the law, changing
    /// RETURN: BTreeSet<String>, the states forbidden NOW -- the model's,
    ///         less those permitted, with those forbidden since.
    pub fn forbidden(&self) -> BTreeSet<String> { self.forbid_db.keys().cloned().collect() }

    /// RETURN: bool, true where 'event' is disallowed in 'state' now -- in
    ///         every state, or in that one.
    fn masked_f(&self, state: &str, event: &str) -> bool {
        self.mask_db.contains_key(&(None, event.to_string()))
            || self.mask_db.contains_key(&(Some(state.to_string()), event.to_string()))
    }

    /// RETURN: Ok(()) where 'event' and 'state' are named by the model;
    ///         Err(FsmError) naming what is not -- a mask over a word the
    ///         model never names would guard nothing.
    fn known(&self, event: Option<&str>, state: Option<&str>) -> Result<(), FsmError> {
        if let Some(event) = event {
            if !self.event_tuple.iter().any(|e| e == event) {
                return Err(FsmError(format!("'{}': an event the model never names -- events: {}",
                                            event, self.event_tuple.join(", "))));
            }
        }
        if let Some(state) = state {
            if !self.state_tuple.iter().any(|s| s == state) {
                return Err(FsmError(format!("'{}': a state the model never names -- states: {}",
                                            state, self.state_tuple.join(", "))));
            }
        }
        Ok(())
    }

    /// RETURN: Ok(()); from now on 'event' is a breach -- in 'state' alone,
    ///         or in every state where None -- until 'allow' lifts it; the
    ///         breach line says 'disallowed since <place>'.
    ///         Err(FsmError) where the model names no such event or state.
    pub fn disallow(&mut self, event: &str, state: Option<&str>, place: impl Into<Where>) -> Result<(), FsmError> {
        self.known(Some(event), state)?;
        self.mask_db.entry((state.map(str::to_string), event.to_string())).or_insert(place.into());
        Ok(())
    }

    /// RETURN: Ok(()); the mask 'disallow(event, state)' set is lifted; a
    ///         mask set for another scope stays.
    ///         Err(FsmError) where the model names no such event or state.
    pub fn allow(&mut self, event: &str, state: Option<&str>, _place: impl Into<Where>) -> Result<(), FsmError> {
        self.known(Some(event), state)?;
        self.mask_db.remove(&(state.map(str::to_string), event.to_string()));
        Ok(())
    }

    /// RETURN: Ok(()); from now on entering 'state' is a breach, until
    ///         'permit'. Where the machine STANDS in it, one BREACH line is
    ///         written at once: the test forbade the present.
    ///         Err(FsmError) where the model names no such state.
    pub fn forbid(&mut self, state: &str, place: impl Into<Where>) -> Result<(), FsmError> {
        self.known(None, Some(state))?;
        if self.forbid_db.contains_key(state) { return Ok(()); }
        let place: Where = place.into();
        self.forbid_db.insert(state.to_string(), place.clone());
        self.permit_db.remove(state);
        if self.current.contains(state) {
            self.breach_n += 1;
            let line = format!("BREACH{}: stands in '{}' -- forbidden{}", where_text(&place), state, since_text(&place));
            self.say(&line);
        }
        Ok(())
    }

    /// RETURN: Ok(()); 'state' is no longer forbidden -- a state of the
    ///         model's own 'forbidden:' too, until 'forbid' again.
    ///         Err(FsmError) where the model names no such state.
    pub fn permit(&mut self, state: &str, place: impl Into<Where>) -> Result<(), FsmError> {
        self.known(None, Some(state))?;
        if self.forbid_db.remove(state).is_some() && self.model_forbidden.contains(state) {
            self.permit_db.insert(state.to_string(), place.into());
        }
        Ok(())
    }

    /// RETURN: Ok(()) once 'block' ran with 'event' disallowed (see
    ///         'disallow') and the event was allowed again on leaving it;
    ///         Err(FsmError) where the model names no such event or state
    ///         (the block does not run).
    pub fn disallowed<F: FnOnce(&mut Machine)>(&mut self, event: &str, state: Option<&str>,
                                                place: impl Into<Where>, block: F) -> Result<(), FsmError> {
        self.disallow(event, state, place)?;
        block(self);
        self.allow(event, state, Where::Nowhere)
    }

    /// RETURN: Ok(()) once 'block' ran with 'state' forbidden (see 'forbid')
    ///         and the state was permitted again on leaving it;
    ///         Err(FsmError) where the model names no such state.
    pub fn forbidding<F: FnOnce(&mut Machine)>(&mut self, state: &str, place: impl Into<Where>,
                                                block: F) -> Result<(), FsmError> {
        self.forbid(state, place)?;
        block(self);
        self.permit(state, Where::Nowhere)
    }

    /// RETURN: String, where the machine stands: "'idle'", or "{'a', 'b'}"
    ///         for a set.
    fn here(&self) -> String {
        if self.current.len() == 1 { return format!("'{}'", self.current.iter().next().unwrap()); }
        format!("{{{}}}", self.current.iter().map(|s| format!("'{}'", s)).collect::<Vec<_>>().join(", "))
    }

    // ------------------------------------------------------------ questions
    /// RETURN: Ok(String), the one state the machine stands in;
    ///         Err(FsmError) where a set of states stands (DFA false): ask
    ///         'current()'.
    pub fn state(&self) -> Result<String, FsmError> {
        if self.current.len() != 1 {
            return Err(FsmError(format!("the machine stands in {}: ask 'current()'", self.here())));
        }
        Ok(self.current.iter().next().unwrap().clone())
    }

    /// RETURN: &BTreeSet<String>, every state the machine stands in.
    pub fn current(&self) -> &BTreeSet<String> { &self.current }

    /// RETURN: bool, true where the machine stands in 'state'.
    pub fn in_state(&self, state: &str) -> bool { self.current.contains(state) }

    /// RETURN: bool, true where 'event' would move the machine now.
    pub fn can(&self, event: &str) -> bool {
        self.current.iter().any(|s| self.edge_db.contains_key(&(s.clone(), event.to_string()))
                                    && !self.masked_f(s, event))
    }

    /// RETURN: Vec<String>, the events that would move the machine now,
    ///         sorted, each once.
    pub fn allowed(&self) -> Vec<String> {
        let found: BTreeSet<&String> = self.edge_db.keys()
            .filter(|(s, e)| self.current.contains(s) && !self.masked_f(s, e))
            .map(|(_, e)| e).collect();
        found.into_iter().cloned().collect()
    }

    /// RETURN: &[(Where, state, event, state)], every transition fired, in
    ///         order.
    pub fn trace(&self) -> &[(Where, String, String, String)] { &self.trace_list }

    // ------------------------------------------------------ the model alone
    /// RETURN: BTreeMap, state -> sorted (event, state) pairs leaving it --
    ///         under the masks where 'masked', as written else.
    fn successor_db(&self, masked: bool) -> BTreeMap<String, Vec<(String, String)>> {
        let mut found: BTreeMap<String, Vec<(String, String)>> = BTreeMap::new();
        for ((source, event), target_set) in &self.edge_db {
            if masked && self.masked_f(source, event) { continue; }
            for target in target_set {
                found.entry(source.clone()).or_default().push((event.clone(), target.clone()));
            }
        }
        for pair_list in found.values_mut() { pair_list.sort(); }
        found
    }

    /// RETURN: Some(events), the shortest sequence of events from 'start' --
    ///         the initial state where None, Some("now") for where the
    ///         machine stands -- into 'state' (empty where 'start' is
    ///         'state'); among equally short paths the first in event order;
    ///         None where 'state' cannot be reached from there. Under the
    ///         masks standing now; 'masked' false asks the model as written.
    pub fn path_to(&self, state: &str, start: Option<&str>, masked: bool) -> Option<Vec<String>> {
        let start_set: BTreeSet<String> = match start {
            Some("now") => self.current.clone(),
            None        => [self.initial.clone()].into_iter().collect(),
            Some(s)     => [s.to_string()].into_iter().collect(),
        };
        if start_set.contains(state) { return Some(Vec::new()); }
        let successor_db = self.successor_db(masked);
        let mut queue: VecDeque<(String, Vec<String>)> = start_set.iter().map(|s| (s.clone(), Vec::new())).collect();
        let mut seen = start_set.clone();
        while let Some((here, path)) = queue.pop_front() {
            for (event, target) in successor_db.get(&here).map(|v| v.as_slice()).unwrap_or(&[]) {
                if seen.contains(target) { continue; }
                let mut longer = path.clone();
                longer.push(event.clone());
                if target == state { return Some(longer); }
                seen.insert(target.clone());
                queue.push_back((target.clone(), longer));
            }
        }
        None
    }

    /// RETURN: bool, true where 'state' can be reached from 'start' (see
    ///         'path_to').
    pub fn state_reachable(&self, state: &str, start: Option<&str>, masked: bool) -> bool {
        self.path_to(state, start, masked).is_some()
    }

    /// RETURN: BTreeSet<String>, the states forbidden now where 'masked',
    ///         the model's own else.
    fn forbidden_of(&self, masked: bool) -> BTreeSet<String> {
        if masked { self.forbidden() } else { self.model_forbidden.clone() }
    }

    /// RETURN: Vec<String>, the states no path from the initial state
    ///         reaches, forbidden ones left out -- sorted.
    pub fn unreachable(&self, masked: bool) -> Vec<String> {
        let forbidden = self.forbidden_of(masked);
        self.state_tuple.iter().filter(|s| !forbidden.contains(*s) && !self.state_reachable(s, None, masked))
            .cloned().collect()
    }

    /// RETURN: Vec<String>, the states no event leaves that are neither
    ///         final nor forbidden -- where a system would hang -- sorted.
    pub fn dead_ends(&self, masked: bool) -> Vec<String> {
        let successor_db = self.successor_db(masked);
        let forbidden = self.forbidden_of(masked);
        self.state_tuple.iter()
            .filter(|s| !successor_db.contains_key(*s) && !self.final_.contains(*s) && !forbidden.contains(*s))
            .cloned().collect()
    }

    /// RETURN: Vec<String>, the forbidden states the model lets the system
    ///         reach from the initial state -- sorted.
    pub fn forbidden_reachable(&self, masked: bool) -> Vec<String> {
        self.forbidden_of(masked).into_iter().filter(|s| self.state_reachable(s, None, masked)).collect()
    }

    /// RETURN: usize, how many findings the MODEL has, each written as one
    ///         line 'MODEL: ...'; 0 where it has none -- unreachable states,
    ///         dead ends, forbidden states reachable (with the way there).
    pub fn check(&mut self, masked: bool) -> usize {
        let mut line_list: Vec<String> = self.unreachable(masked).iter()
            .map(|s| format!("MODEL: '{}' cannot be reached", s)).collect();
        line_list.extend(self.dead_ends(masked).iter()
            .map(|s| format!("MODEL: '{}' is a dead end -- no event leaves it", s)));
        line_list.extend(self.forbidden_reachable(masked).iter()
            .map(|s| format!("MODEL: forbidden '{}' is reachable: {}", s,
                             self.path_to(s, None, masked).unwrap_or_default().join(" "))));
        for line in &line_list { self.say(line); }
        line_list.len()
    }

    // -------------------------------------------------------------- the end
    /// RETURN: usize, the breaches seen, counting a non-final end; written
    ///         before it, sorted, what the events covered of the model --
    ///             fsm: 3 of 3 states visited, 3 of 4 transitions taken, 1 breach
    ///               taken      idle ---( request )---> waiting   x2
    ///               not taken  busy ---( fault )---> crashed
    ///               never in   ...
    ///               ended in   'idle'
    ///         and the masks and forbidden states still standing. A machine
    ///         with final states that ends elsewhere adds a BREACH line.
    pub fn report(&mut self) -> usize {
        let all_edge: Vec<Edge> = self.edge_db.iter()
            .flat_map(|((s, e), ts)| ts.iter().map(move |t| (s.clone(), e.clone(), t.clone()))).collect();
        let mut breach_n = self.breach_n;
        let end_f = self.final_.is_empty() || self.current.iter().any(|s| self.final_.contains(s));
        if !end_f { breach_n += 1; }
        //  A FORBIDDEN STATE IS NO GOAL OF COVERAGE: counted out.
        let goal: Vec<&String> = self.state_tuple.iter().filter(|s| !self.model_forbidden.contains(*s)).collect();
        let visited_n = goal.iter().filter(|s| self.visit_db.contains_key(**s)).count();
        let mut line_list = vec![format!("{}: {} of {} states visited, {} of {} transitions taken, {} breach{}",
                                         self.name, visited_n, goal.len(), self.taken_db.len(), all_edge.len(),
                                         breach_n, if breach_n == 1 { "" } else { "es" })];
        for edge in &all_edge {
            let n = self.taken_db.get(edge).copied().unwrap_or(0);
            line_list.push(format!("  {}  {} ---( {} )---> {}{}", if n > 0 { "taken    " } else { "not taken" },
                                   edge.0, edge.1, edge.2, if n > 1 { format!("   x{}", n) } else { String::new() }));
        }
        for state in &self.state_tuple {
            if !self.visit_db.contains_key(state) && !self.model_forbidden.contains(state) {
                line_list.push(format!("  never in   '{}'", state));
            }
        }
        line_list.push(format!("  ended in   {}", self.here()));
        //  A PHASE NEVER LIFTED IS SAID: what still stands at the end.
        let mut mask_list: Vec<(&(Option<String>, String), &Where)> = self.mask_db.iter().collect();
        mask_list.sort_by_key(|((state, event), _)| (event.clone(), state.clone().unwrap_or_default()));
        for ((state, event), since) in mask_list {
            line_list.push(format!("  disallowed '{}' {}{}", event,
                                   match state { None => "in every state".to_string(), Some(s) => format!("in '{}'", s) },
                                   since_text(since)));
        }
        for (state, since) in &self.forbid_db {
            if !self.model_forbidden.contains(state) {
                line_list.push(format!("  forbidden  '{}'{}", state, since_text(since)));
            }
        }
        for (state, since) in &self.permit_db {
            line_list.push(format!("  permitted  '{}'{}", state, since_text(since)));
        }
        if !end_f {
            line_list.push(format!("BREACH: ended in {} -- final: {}", self.here(), join(self.final_.iter())));
        }
        for line in &line_list { self.say(line); }
        breach_n
    }
}

/// RETURN: String, the texts joined by ', '.
fn join<'a>(texts: impl Iterator<Item = &'a String>) -> String {
    texts.map(|s| s.as_str()).collect::<Vec<_>>().join(", ")
}
