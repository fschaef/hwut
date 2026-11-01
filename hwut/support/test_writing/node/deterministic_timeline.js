// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: A DETERMINISTIC EVENT DISPATCHER -- the port of
//          'python/deterministic_timeline.py'. Triggers fire at the ticks their
//          timeline strings mark with a digit; within one tick the LOWER digit
//          fires first, equal digits in registration order:
//
//              Trigger A: "1  12 1"
//              Trigger B: " 1  1 2"
//
//          When the last tick has passed, every trigger is told
//          'on_termination(end_tick)', 'end_tick' being the LONGEST timeline's
//          length. 'stop' leaves early and still announces; a CANCELLED task
//          announces nothing.
//
// USAGE:
//
//     const { Trigger, TriggerDispatcher } = require(path.join(__dirname, '..', 'deterministic_timeline.js'));
//     class MyTrigger extends Trigger {
//         async fire(pseudo_time) { console.log(`[${pseudo_time}] ${this.name} fired`); }
//     }
//     await new TriggerDispatcher([new MyTrigger("1 1 3", "SUB")]).run();
//
// ASYNCIO IN NODE. 'async'/'await' are Python's; the loop is node's. Python's
// 'asyncio.sleep(0)' -- one turn of the loop, every other ready task runs
// first -- is 'sleep0()' here: a 'setImmediate', whose queue is FIFO as
// asyncio's ready queue is. The run awaits each firing, then 'sleep0()', so a
// consumer waiting on a trigger runs between ticks. Tasks are asyncio's:
//
//     const task = create_task(() => dispatcher.run());   // starts at the next turn
//     await sleep0();  task.cancel();
//     try { await task.promise; } catch (e) { if (e instanceof CancelledError) ... }
//     await gather(() => dispatcher.run(), () => consume(producer));
//
// A CANCELLED task is thrown 'CancelledError' at its next 'sleep0()' -- the
// task an await belongs to is found through node's 'AsyncLocalStorage', as
// asyncio finds the current task.
//_____________________________________________________________________________
'use strict';

const { AsyncLocalStorage } = require('async_hooks');

const currentTask = new AsyncLocalStorage();
let   triggerCounter = 0;

class NotImplementedError extends Error {
    /* RETURN: NotImplementedError, named as Python's exception. */
    constructor(message) { super(message || ''); this.name = 'NotImplementedError'; }
}

class CancelledError extends Error {
    /* RETURN: CancelledError, named as asyncio's exception. */
    constructor(message) { super(message || ''); this.name = 'CancelledError'; }
}

/* RETURN: Promise of undefined, resolved at the next turn of the loop --
 *         asyncio's 'sleep(0)': every task ready before it runs first.
 *         Rejected with CancelledError where the task this await belongs to
 *         was cancelled meanwhile. */
function sleep0() {
    const task = currentTask.getStore();
    return new Promise((resolve, reject) => setImmediate(() => {
        if (task && task.cancelled_f) reject(new CancelledError());
        else                          resolve();
    }));
}

class Task {
    /* RETURN: Task over 'fn' (a function returning a promise, or a value); it
     *         starts at the next turn of the loop, as an asyncio task does.
     *         'promise' settles with what 'fn' settles with. */
    constructor(fn) {
        this.cancelled_f = false;
        this.done_f      = false;
        this.promise     = new Promise((resolve, reject) => setImmediate(() => {
            if (this.cancelled_f) { this.done_f = true; reject(new CancelledError()); return; }
            currentTask.run(this, () => Promise.resolve().then(fn))
                       .then(v => { this.done_f = true; resolve(v); },
                             e => { this.done_f = true; reject(e); });
        }));
    }

    /* RETURN: boolean, true where the task was not done yet and is now
     *         marked cancelled (it receives CancelledError at its next
     *         'sleep0()'); false where it was done already. */
    cancel() {
        if (this.done_f) return false;
        this.cancelled_f = true;
        return true;
    }
}

/* RETURN: Task, 'fn' run as an asyncio task (see Task). */
function create_task(fn) { return new Task(fn); }

/* RETURN: Promise of the array of the results, in the order given, once
 *         every one is done -- asyncio's 'gather'. Each argument is a
 *         function (started as a task, in the order given) or a promise
 *         (awaited as it stands). Rejected with the first error. */
function gather(...item) {
    return Promise.all(item.map(x => typeof x === 'function' ? create_task(x).promise : x));
}

class Trigger {
    /* RETURN: Trigger with 'timeline' and 'name' -- a name chosen by the
     *         machine ('trigger-<n>') where none is given. */
    constructor(timeline, name = '') {
        this.timeline = timeline;
        this.name     = name ? name : `trigger-${++triggerCounter}`;
    }

    /* RETURN: never; ABSTRACT -- a trigger that does nothing when its tick
     *         comes has no reason to stand in the timeline: rejects with
     *         NotImplementedError. */
    async fire(pseudo_time) { throw new NotImplementedError(); }

    /* RETURN: undefined. Optional: a trigger with nothing to wind down says
     *         nothing. NOT async: the run is over, nobody is left to yield to. */
    on_termination(end_tick) { }
}

class TriggerDispatcher {
    /* RETURN: TriggerDispatcher over the iterable 'triggers', its schedule
     *         built: one entry per tick (as many as the LONGEST timeline has
     *         characters), the [priority, trigger] pairs due there, lower
     *         digit first, registration order between equal digits (JS's
     *         sort is stable, as Python's). */
    constructor(triggers) {
        this._running_f       = true;
        this._triggers        = Array.from(triggers || []);
        const endTick         = Math.max(0, ...this._triggers.map(t => t.timeline.length));
        this._trigger_time_db = Array.from({ length: endTick }, () => []);
        for (const trigger of this._triggers) {
            [...trigger.timeline].forEach((char, t) => {
                if (/^[0-9]$/.test(char)) this._trigger_time_db[t].push([parseInt(char, 10), trigger]);
            });
        }
        for (const due of this._trigger_time_db) due.sort((a, b) => a[0] - b[0]);
        this._end_tick = endTick;
    }

    /* RETURN: undefined. Asks the run to leave the timeline at the next
     *         firing; the run still announces termination. */
    stop() { this._running_f = false; }

    /* RETURN: Promise of undefined, resolved once the timeline has passed
     *         -- every trigger due awaited tick by tick in priority order,
     *         'sleep0()' after each -- and every trigger was told
     *         'on_termination(end_tick)' (also after 'stop()'). Rejected
     *         with CancelledError, announcing nothing, where the task
     *         carrying it was cancelled; with what a 'fire' threw, else. */
    async run() {
        outer:
        for (let pseudo_time = 0; pseudo_time < this._trigger_time_db.length; pseudo_time += 1) {
            if (!this._running_f) break;
            for (const [, trigger] of this._trigger_time_db[pseudo_time]) {
                if (!this._running_f) break outer;
                await trigger.fire(pseudo_time);
                await sleep0();
            }
        }
        for (const trigger of this._triggers) trigger.on_termination(this._end_tick);
    }

    /* RETURN: string, the schedule as built -- 'TriggerDispatcher', then one
     *         line per firing, '[tick] (priority)name', in the order of the
     *         run (Python's '__repr__'). */
    toString() {
        const line = ['TriggerDispatcher'];
        this._trigger_time_db.forEach((due, t) => {
            for (const [priority, trigger] of due) line.push(`[${t}] (${priority})${trigger.name}`);
        });
        return line.join('\n');
    }
}

module.exports = { Trigger, TriggerDispatcher, NotImplementedError, CancelledError,
                   Task, create_task, gather, sleep0 };
