// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
//          port of 'python/hwut_fsm.py' (read '../python/README-hwut_fsm.txt'):
//          the states it may be in, the events that move it, the states it
//          must never reach. A test FIRES the events it observes; every event
//          the model does not allow, and every forbidden state entered, is
//          PRINTED as a line -- so it lands in the GOOD file.
//
//     const { Machine, FsmError } = require(path.join(__dirname, '..', 'hwut_fsm.js'));
//     const m = Machine.from_string(`
//         initial: idle
//         forbidden: crashed
//         idle    ---( request )---> waiting ---( grant )---> busy
//         busy    ---( release )---> idle
//         :       ---( fault )--->   crashed
//     `);
//     m.fire('request', 1);      // true
//     m.fire('release', 2);      // BREACH line 2: 'release' in 'waiting' -- allowed: grant
//     m.report();
//
// PYTHON'S KEYWORDS: a positional argument stands where Python has a keyword
// argument, in Python's order -- 'fire(event, where)', 'disallow(event,
// state, where)', 'path_to(state, start, masked)', 'check(masked)'; the
// options of a model are an object -- 'from_string(text, { DFA, name, write })',
// 'new Machine(transitions, initial, { forbidden, final, DFA, name, write,
// states })'. Python's 'None' is 'null' (or left out).
//
// PYTHON'S 'with': 'm.disallowed(event, state, where).run(block)' and
// 'm.forbidding(state, where).run(block)' -- the mask stands while 'block'
// runs (awaited where it returns a promise) and is lifted whatever way it
// ends.
//
// A raised FsmError is thrown: 'FsmError' extends Error, its message Python's.
//_____________________________________________________________________________
'use strict';

class FsmError extends Error {
    /* RETURN: FsmError, a model that cannot be meant; 'message' as Python's. */
    constructor(message) { super(message); this.name = 'FsmError'; }
}

const ARROW_RE = /-+\s*\(\s*([^()]*?)\s*\)\s*-*>/u;
const NAME_RE  = /^(?:state\s+)?([A-Za-z_][\p{L}\p{N}\p{M}_.\-]*)$/u;   // Python's '\w' is Unicode's
const KEY_RE   = /^(initial|forbidden|final)\s*:\s*(.*)$/;

/* RETURN: -1, 0 or 1 -- 'a' against 'b' as Python compares two values of
 *         one kind: numbers by value, strings by code point, arrays
 *         element by element (the shorter first where one is the other's
 *         head); null before anything else. */
function cmp(a, b) {
    if (Array.isArray(a)) {
        for (let i = 0; i < Math.min(a.length, b.length); i += 1) {
            const c = cmp(a[i], b[i]);
            if (c) return c;
        }
        return a.length - b.length < 0 ? -1 : a.length > b.length ? 1 : 0;
    }
    if (a === b) return 0;
    if (a === null) return -1;
    if (b === null) return 1;
    return a < b ? -1 : 1;
}

/* RETURN: array, the elements of the iterable 'x', sorted by 'cmp'. */
function sorted(x) { return Array.from(x).sort(cmp); }

/* RETURN: string, the key a pair or triple stands under in a Map. */
const key = (...part) => JSON.stringify(part);

/* RETURN: string, the state 'text' names -- 'A' or 'state A' -- if success;
 *         throws FsmError naming line 'number', else. */
function nameOf(text, number) {
    const found = NAME_RE.exec(text.trim());
    if (found === null)
        throw new FsmError(`line ${number}: '${text.trim()}' names no state -- a state is a word ('A', 'state A')`);
    return found[1];
}

/* RETURN: string, ' line 3' for the integer 3, ' <text>' for a text, '' for
 *         null/undefined -- the place a breach line names. */
function whereText(where) {
    if (where === null || where === undefined) return '';
    if (typeof where === 'number') return ` line ${where}`;
    return ` ${where}`;
}

/* RETURN: string, ' since line 9', ' since <text>', or '' for null -- when a
 *         mask or a forbidden state began. */
function sinceText(where) {
    return where === null || where === undefined ? '' : ` since${whereText(where)}`;
}

/* RETURN: array of strings, the lines of 'text' as Python's 'splitlines'. */
function splitLines(text) {
    const line = text.split(/\r\n|[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]/);
    if (line.length && line[line.length - 1] === '') line.pop();
    return line;
}

class Phase {
    /* RETURN: Phase, doing 'enter()' on entry and 'leave()' on exit. */
    constructor(enter, leave) { this._enter = enter; this._leave = leave; }

    /* RETURN: what 'block()' returns -- a promise where it returns one, then
     *         settled after the phase has ended. The phase begins before
     *         'block' and ends after it, whatever way; an exception passes on. */
    run(block) {
        this._enter();
        let result;
        try {
            result = block();
        } catch (error) {
            this._leave();
            throw error;
        }
        if (result && typeof result.then === 'function')
            return Promise.resolve(result).finally(() => this._leave());
        this._leave();
        return result;
    }
}

class Machine {
    /* RETURN: Machine, standing in 'initial', if success; throws FsmError,
     *         else -- a DFA with two transitions for one (state, event); a
     *         forbidden or final state no transition names.
     *
     * 'transitions' is an iterable of [state, event, state] triples;
     * 'states' names states no transition touches (yet). 'write' takes one
     * line; every breach and report goes through it (default console.log). */
    constructor(transitions, initial, { forbidden = [], final = [], DFA = true, name = 'fsm',
                                        write = line => console.log(line), states = [] } = {}) {
        this.name     = name;
        this.dfa_f    = !!DFA;
        this.write    = write;
        this._edge_db = new Map();             // key(state, event) -> { source, event, targets: Set }
        const stateSet = new Set([initial, ...states]);
        for (const [source, event, target] of transitions) {
            const k = key(source, event);
            if (!this._edge_db.has(k)) this._edge_db.set(k, { source, event, targets: new Set() });
            const targetSet = this._edge_db.get(k).targets;
            if (this.dfa_f && targetSet.size && !targetSet.has(target))
                throw new FsmError(`'${source}' --(${event})--> '${sorted(targetSet)[0]}' and '${target}': `
                                   + "a DFA moves one way per event -- or 'DFA=False'");
            targetSet.add(target);
            stateSet.add(source); stateSet.add(target);
        }
        this.initial         = initial;
        this.model_forbidden = new Set(forbidden);
        this.final           = new Set(final);
        for (const [label, chosen] of [['forbidden', this.model_forbidden], ['final', this.final]]) {
            const unknown = sorted([...chosen].filter(s => !stateSet.has(s)));
            if (unknown.length)
                throw new FsmError(`${label} state(s) ${unknown.map(s => `'${s}'`).join(', ')}: `
                                   + 'named nowhere else in the model');
        }
        this.state_tuple = sorted(new Set([...stateSet, ...this.model_forbidden]));
        this.event_tuple = sorted(new Set([...this._edge_db.values()].map(e => e.event)));
        this.reset();
    }

    // ------------------------------------------------------------- reading
    /* RETURN: Machine, the model the text states, if success; throws
     *         FsmError naming the line, else.
     *
     * One statement per line; '#' starts a comment:
     *     initial: A              where the machine starts; default: the
     *                             first state the text names
     *     forbidden: X, Y         states the system must never enter
     *     final: A, B             states it may end in
     *     state A                 a state, transitions or not
     *     A ---( ev )---> B ---( ev2 )---> C     transitions, chained
     *     :  ---( ev )---> D      ':' is the state that began the line above */
    static from_string(text, { DFA = true, name = 'fsm', write = line => console.log(line) } = {}) {
        const tripleList = [], declared = {};
        const lineOf = new Map();               // key(state, event) -> [target, line]
        let first = null, previousHead = null;
        splitLines(text).forEach((raw, index) => {
            const number = index + 1;
            const line   = raw.split('#')[0].trim();
            if (!line) return;
            const keyFound = KEY_RE.exec(line);
            if (keyFound !== null) {
                const [, word, rest] = keyFound;
                const nameList = rest.split(',').filter(p => p.trim()).map(p => nameOf(p, number));
                if (word === 'initial' && nameList.length !== 1)
                    throw new FsmError(`line ${number}: 'initial:' names one state`);
                (declared[word] = declared[word] || []).push(...nameList);
                return;
            }
            const partList = line.split(new RegExp(ARROW_RE.source, 'u'));
            if (partList.length === 1) {
                const head = nameOf(line, number);
                first = first || head;
                tripleList.push([head, null, null]);
                previousHead = head;
                return;
            }
            for (let i = 1; i < partList.length; i += 2)
                if (!partList[i].trim())
                    throw new FsmError(`line ${number}: an arrow names no event -- '---( event )--->'`);
            const headText = partList[0].trim();
            let head;
            if (headText === ':') {
                if (previousHead === null)
                    throw new FsmError(`line ${number}: ':' stands for the state of the line above, and none stands there`);
                head = previousHead;
            } else {
                head = nameOf(headText, number);
            }
            first = first || head; previousHead = head;
            let source = head;
            for (let i = 1; i < partList.length; i += 2) {
                const target = nameOf(partList[i + 1], number);
                const event  = partList[i].trim();
                const k      = key(source, event);
                if (DFA && lineOf.has(k) && lineOf.get(k)[0] !== target)
                    throw new FsmError(`line ${number}: '${source}' --(${event})--> '${target}', and line `
                                       + `${lineOf.get(k)[1]}: --> '${lineOf.get(k)[0]}' -- a DFA moves one way per `
                                       + "event, or 'DFA=False'");
                if (!lineOf.has(k)) lineOf.set(k, [target, number]);
                tripleList.push([source, event, target]);
                source = target;
            }
        });
        if (first === null && !('initial' in declared)) throw new FsmError('the model names no state');
        const initial = ((declared.initial && declared.initial.length) ? declared.initial : [first])[0];
        return new Machine(tripleList.filter(t => t[1] !== null), initial, {
            forbidden: declared.forbidden || [], final: declared.final || [],
            DFA, name, write, states: new Set(tripleList.filter(t => t[1] === null).map(t => t[0])),
        });
    }

    /* RETURN: array of [source, event, target], every transition of the
     *         model, sorted. */
    _all_edges() {
        const all = [];
        for (const { source, event, targets } of this._edge_db.values())
            for (const target of targets) all.push([source, event, target]);
        return all.sort(cmp);
    }

    /* RETURN: string, the model in the text 'from_string' reads, one
     *         transition per line, sorted. */
    to_string() {
        const lineList = [`initial: ${this.initial}`];
        if (this.model_forbidden.size) lineList.push(`forbidden: ${sorted(this.model_forbidden).join(', ')}`);
        if (this.final.size)           lineList.push(`final: ${sorted(this.final).join(', ')}`);
        const named = new Set([this.initial]);
        for (const [source, event, target] of this._all_edges()) {
            lineList.push(`${source} ---( ${event} )---> ${target}`);
            named.add(source); named.add(target);
        }
        for (const s of this.state_tuple)
            if (!named.has(s) && !this.model_forbidden.has(s)) lineList.push(`state ${s}`);
        return lineList.join('\n');
    }

    // ------------------------------------------------------------- running
    /* RETURN: undefined. The machine stands in its initial state again, under
     *         the model as written: what was seen is forgotten, and so is
     *         every mask and every state forbidden or permitted since. */
    reset() {
        this._mask_db    = new Map();           // key(state|null, event) -> { state, event, since }
        this._forbid_db  = new Map([...this.model_forbidden].map(s => [s, null]));  // state -> since
        this._permit_db  = new Map();           // model-forbidden state -> since
        this._current    = new Set([this.initial]);
        this._visit_db   = new Map([[this.initial, 1]]);
        this._taken_db   = new Map();           // key(state, event, state) -> count
        this._trace_list = [];
        this.breach_n    = 0;
    }

    /* RETURN: true, 'event' moved the machine (and entered no forbidden
     *         state); false, it was not allowed where the machine stands -- a
     *         BREACH line is written and the machine stays -- or it entered a
     *         forbidden state, which is written too.
     *
     * 'where' is the place the breach line names: a number is a line number
     * ('line 3'), a text stands as written. */
    fire(event, where = null) {
        const moved = new Set(), masked = [];
        for (const state of sorted(this._current)) {
            const edge = this._edge_db.get(key(state, event));
            if (this._masked_f(state, event)) {
                if (edge) masked.push(state);
                continue;
            }
            for (const target of sorted(edge ? edge.targets : [])) {
                moved.add(target);
                const k = key(state, event, target);
                this._taken_db.set(k, (this._taken_db.get(k) || 0) + 1);
                this._trace_list.push([where, state, event, target]);
            }
        }
        if (moved.size === 0) {
            this.breach_n += 1;
            const allowed = this.allowed();
            let hint = allowed.length ? `allowed: ${allowed.join(', ')}` : 'no event leaves it';
            if (!this.event_tuple.includes(event)) {
                hint = 'an event the model never names';
            } else if (masked.length) {
                const one = this._mask_db.get(key(masked[0], event));
                const all = this._mask_db.get(key(null, event));
                hint = `disallowed${sinceText(one ? one.since : all ? all.since : null)}`;
            }
            this.write(`BREACH${whereText(where)}: '${event}' in ${this._here()} -- ${hint}`);
            return false;
        }
        this._current = moved;
        for (const state of moved) this._visit_db.set(state, (this._visit_db.get(state) || 0) + 1);
        const entered = sorted([...moved].filter(s => this._forbid_db.has(s)));
        for (const state of entered) {
            this.breach_n += 1;
            const since = this._forbid_db.get(state);
            this.write(`BREACH${whereText(where)}: '${state}' entered by '${event}' -- `
                       + (this.model_forbidden.has(state) && since === null
                          ? 'a forbidden state' : `forbidden${sinceText(since)}`));
        }
        return entered.length === 0;
    }

    // --------------------------------------------------- the law, changing
    /* RETURN: Set of strings, the states forbidden NOW -- the model's, less
     *         those permitted, with those forbidden since. */
    get forbidden() { return new Set(this._forbid_db.keys()); }

    /* RETURN: boolean, true if 'event' is disallowed in 'state' now -- in
     *         every state, or in that one. */
    _masked_f(state, event) {
        return this._mask_db.has(key(null, event)) || this._mask_db.has(key(state, event));
    }

    /* RETURN: undefined, if 'event' and 'state' are named by the model (or
     *         null); throws FsmError naming what is not, else. */
    _known(event = null, state = null) {
        if (event !== null && event !== undefined && !this.event_tuple.includes(event))
            throw new FsmError(`'${event}': an event the model never names -- events: ${this.event_tuple.join(', ')}`);
        if (state !== null && state !== undefined && !this.state_tuple.includes(state))
            throw new FsmError(`'${state}': a state the model never names -- states: ${this.state_tuple.join(', ')}`);
    }

    /* RETURN: undefined. From now on 'event' is a breach -- in 'state' alone,
     *         or in every state where null -- until 'allow' lifts it; the
     *         breach line says 'disallowed since <where>'. Throws FsmError
     *         where the model names no such event or state. */
    disallow(event, state = null, where = null) {
        this._known(event, state);
        const k = key(state ?? null, event);
        if (!this._mask_db.has(k)) this._mask_db.set(k, { state: state ?? null, event, since: where ?? null });
    }

    /* RETURN: undefined. The mask 'disallow(event, state)' set is lifted; a
     *         mask set for another scope stays. Throws FsmError where the
     *         model names no such event or state. */
    allow(event, state = null, where = null) {
        this._known(event, state);
        this._mask_db.delete(key(state ?? null, event));
    }

    /* RETURN: undefined. From now on entering 'state' is a breach, until
     *         'permit'. Where the machine STANDS in it, one BREACH line is
     *         written at once. Throws FsmError where the model names no such
     *         state. */
    forbid(state, where = null) {
        this._known(null, state);
        if (this._forbid_db.has(state)) return;
        this._forbid_db.set(state, where ?? null);
        this._permit_db.delete(state);
        if (this._current.has(state)) {
            this.breach_n += 1;
            this.write(`BREACH${whereText(where)}: stands in '${state}' -- forbidden${sinceText(where)}`);
        }
    }

    /* RETURN: undefined. 'state' is no longer forbidden -- a state of the
     *         model's own 'forbidden:' too, until 'forbid' again. Throws
     *         FsmError where the model names no such state. */
    permit(state, where = null) {
        this._known(null, state);
        if (this._forbid_db.delete(state) && this.model_forbidden.has(state))
            this._permit_db.set(state, where ?? null);
    }

    /* RETURN: Phase: 'event' disallowed (see 'disallow') while its 'run(block)'
     *         runs, allowed again on leaving it -- whatever way. */
    disallowed(event, state = null, where = null) {
        return new Phase(() => this.disallow(event, state, where), () => this.allow(event, state));
    }

    /* RETURN: Phase: 'state' forbidden (see 'forbid') while its 'run(block)'
     *         runs, permitted again on leaving it -- whatever way. */
    forbidding(state, where = null) {
        return new Phase(() => this.forbid(state, where), () => this.permit(state));
    }

    /* RETURN: string, where the machine stands: "'idle'", or "{'a', 'b'}". */
    _here() {
        if (this._current.size === 1) return `'${[...this._current][0]}'`;
        return `{${sorted(this._current).map(s => `'${s}'`).join(', ')}}`;
    }

    // ------------------------------------------------------------ questions
    /* RETURN: string, the one state the machine stands in, if success;
     *         throws FsmError, else -- a set of states stands (DFA=False). */
    get state() {
        if (this._current.size !== 1) throw new FsmError(`the machine stands in ${this._here()}: ask 'current()'`);
        return [...this._current][0];
    }

    /* RETURN: Set of strings, every state the machine stands in. */
    current() { return new Set(this._current); }

    /* RETURN: boolean, true if the machine stands in 'state'. */
    in_state(state) { return this._current.has(state); }

    /* RETURN: boolean, true if 'event' would move the machine now. */
    can(event) {
        return [...this._current].some(s => this._edge_db.has(key(s, event)) && !this._masked_f(s, event));
    }

    /* RETURN: array of strings, the events that would move the machine now,
     *         sorted, each once. */
    allowed() {
        const found = new Set();
        for (const { source, event } of this._edge_db.values())
            if (this._current.has(source) && !this._masked_f(source, event)) found.add(event);
        return sorted(found);
    }

    /* RETURN: array of [where, state, event, state], every transition fired,
     *         in order. */
    trace() { return this._trace_list.map(t => [...t]); }

    // ------------------------------------------------------ the model alone
    /* RETURN: Map, state -> sorted array of [event, state] leaving it --
     *         under the masks where 'masked', as written else. */
    _successor_db(masked = true) {
        const found = new Map();
        for (const { source, event, targets } of this._edge_db.values()) {
            if (masked && this._masked_f(source, event)) continue;
            for (const target of targets) {
                if (!found.has(source)) found.set(source, []);
                found.get(source).push([event, target]);
            }
        }
        for (const pairList of found.values()) pairList.sort(cmp);
        return found;
    }

    /* RETURN: array of strings, the shortest sequence of events from 'start'
     *         -- the initial state where null, 'now' for where the machine
     *         stands -- into 'state', if one exists ('[]' where 'start' is
     *         'state'); among equally short ones the first in event order;
     *         null, else: 'state' cannot be reached from there. Under the
     *         masks standing now; 'masked' false asks the model as written. */
    path_to(state, start = null, masked = true) {
        let startSet;
        if (start === 'now')                          startSet = new Set(this._current);
        else if (start === null || start === undefined) startSet = new Set([this.initial]);
        else                                          startSet = new Set([start]);
        if (startSet.has(state)) return [];
        const successorDb = this._successor_db(masked);
        const queue = sorted(startSet).map(s => [s, []]);
        const seen  = new Set(startSet);
        while (queue.length) {
            const [here, path] = queue.shift();
            for (const [event, target] of successorDb.get(here) || []) {
                if (seen.has(target)) continue;
                if (target === state) return [...path, event];
                seen.add(target);
                queue.push([target, [...path, event]]);
            }
        }
        return null;
    }

    /* RETURN: boolean, true if 'state' can be reached from 'start' (see
     *         'path_to'). */
    state_reachable(state, start = null, masked = true) { return this.path_to(state, start, masked) !== null; }

    /* RETURN: Set of strings, the states forbidden now where 'masked', the
     *         model's own else. */
    _forbidden_of(masked) { return masked ? this.forbidden : this.model_forbidden; }

    /* RETURN: array of strings, the states no path from the initial state
     *         reaches, forbidden ones left out -- sorted; under the masks
     *         unless 'masked' is false. */
    unreachable(masked = true) {
        const forbidden = this._forbidden_of(masked);
        return this.state_tuple.filter(s => !forbidden.has(s) && !this.state_reachable(s, null, masked));
    }

    /* RETURN: array of strings, the states no event leaves that are neither
     *         final nor forbidden -- sorted; under the masks unless 'masked'
     *         is false. */
    dead_ends(masked = true) {
        const successorDb = this._successor_db(masked);
        const forbidden   = this._forbidden_of(masked);
        return this.state_tuple.filter(s => !successorDb.has(s) && !this.final.has(s) && !forbidden.has(s));
    }

    /* RETURN: array of strings, the forbidden states the model lets the
     *         system reach from the initial state -- sorted; under the masks
     *         and the states forbidden now unless 'masked' is false. */
    forbidden_reachable(masked = true) {
        return sorted(this._forbidden_of(masked)).filter(s => this.state_reachable(s, null, masked));
    }

    /* RETURN: integer, how many findings the MODEL has, each written as one
     *         line 'MODEL: ...'; 0 where it has none -- unreachable states,
     *         dead ends, reachable forbidden states with the shortest way
     *         there; under the masks unless 'masked' is false. */
    check(masked = true) {
        const lineList = [
            ...this.unreachable(masked).map(s => `MODEL: '${s}' cannot be reached`),
            ...this.dead_ends(masked).map(s => `MODEL: '${s}' is a dead end -- no event leaves it`),
            ...this.forbidden_reachable(masked).map(s => `MODEL: forbidden '${s}' is reachable: `
                                                         + this.path_to(s, null, masked).join(' ')),
        ];
        for (const line of lineList) this.write(line);
        return lineList.length;
    }

    // -------------------------------------------------------------- the end
    /* RETURN: integer, the breaches seen, counting a non-final end; written
     *         before it, sorted, what the events covered of the model --
     *         states counted without the forbidden ones -- every transition
     *         taken or not, states never in, where it ended, the masks still
     *         standing; a BREACH line for an end outside the final states. */
    report() {
        const allEdge = this._all_edges();
        let breachN = this.breach_n;
        const endF = this.final.size === 0 || [...this._current].some(s => this.final.has(s));
        if (!endF) breachN += 1;
        const goal    = this.state_tuple.filter(s => !this.model_forbidden.has(s));
        const visited = goal.filter(s => this._visit_db.has(s));
        this.write(`${this.name}: ${visited.length} of ${goal.length} states visited, `
                   + `${this._taken_db.size} of ${allEdge.length} transitions taken, `
                   + `${breachN} breach${breachN === 1 ? '' : 'es'}`);
        for (const [s, e, t] of allEdge) {
            const n = this._taken_db.get(key(s, e, t));
            const label = n ? 'taken    ' : 'not taken';
            this.write(`  ${label}  ${s} ---( ${e} )---> ${t}${n && n > 1 ? `   x${n}` : ''}`);
        }
        for (const state of this.state_tuple)
            if (!this._visit_db.has(state) && !this.model_forbidden.has(state))
                this.write(`  never in   '${state}'`);
        this.write(`  ended in   ${this._here()}`);
        const maskList = [...this._mask_db.values()].sort((a, b) => cmp([a.event, a.state || ''], [b.event, b.state || '']));
        for (const { state, event, since } of maskList)
            this.write(`  disallowed '${event}' ${state === null ? 'in every state' : `in '${state}'`}${sinceText(since)}`);
        for (const state of sorted([...this._forbid_db.keys()].filter(s => !this.model_forbidden.has(s))))
            this.write(`  forbidden  '${state}'${sinceText(this._forbid_db.get(state))}`);
        for (const state of sorted(this._permit_db.keys()))
            this.write(`  permitted  '${state}'${sinceText(this._permit_db.get(state))}`);
        if (!endF) this.write(`BREACH: ended in ${this._here()} -- final: ${sorted(this.final).join(', ')}`);
        return breachN;
    }
}

module.exports = { Machine, FsmError, Phase };
