// @hwut {
//     title      = "TriggerDispatcher: schedule, priority, and the end of time"
//     choices {
//         abstract    { features = ["node-timeline"] }
//         cancel      { features = ["node-timeline"] }
//         edges       { features = ["node-timeline"] }
//         priority    { features = ["node-timeline"] }
//         schedule    { features = ["node-timeline"] }
//         stable      { features = ["node-timeline"] }
//         stop        { features = ["node-timeline"] }
//         termination { features = ["node-timeline"] }
//         yielding    { features = ["node-timeline"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: The node port of 'python/TEST/test-deterministic-timeline.py',
//          choice for choice, held against its GOOD files by '.link'. Python's
//          'asyncio.run', 'create_task', 'gather' and 'sleep(0)' are the
//          module's 'create_task', 'gather' and 'sleep0' on node's loop.
//_____________________________________________________________________________
'use strict';
const path = require('path');
const { HwutRunner } = require(path.join(__dirname, '..', 'hwut_runner.js'));
const { Trigger, TriggerDispatcher, NotImplementedError, CancelledError,
        create_task, gather, sleep0 } = require(path.join(__dirname, '..', 'deterministic_timeline.js'));

const say    = text => console.log(text);
const banner = label => say(`\n--- ${label} ---`);

/* A trigger that says what it is asked to do, and when. */
class SpeakingTrigger extends Trigger {
    constructor(name, timeline, silentTerminationF = false) {
        super(timeline, name);
        this.silent_termination_f = silentTerminationF;
        say(`SETUP: ${name.padEnd(7)} |${timeline}|`);
    }
    async fire(pseudo_time) { say(`  [t:${pseudo_time}] ${this.name} fires`); }
    on_termination(end_tick) {
        if (this.silent_termination_f) return;
        say(`  [end:${end_tick}] ${this.name} notified`);
    }
}

/* A trigger that fires and does NOT override 'on_termination'. */
class MuteTrigger extends Trigger {
    constructor(name, timeline) {
        super(timeline, name);
        say(`SETUP: ${name.padEnd(7)} |${timeline}|  (no on_termination override)`);
    }
    async fire(pseudo_time) { say(`  [t:${pseudo_time}] ${this.name} fires`); }
}

/* RETURN: Promise of undefined; a dispatcher over 'triggerList' ran to its end. */
async function dispatch(triggerList) { await new TriggerDispatcher(triggerList).run(); }

async function runSchedule() {
    banner('staggered: A at 0, B at 2, C at 4');
    await dispatch([new SpeakingTrigger('A', '1    '),
                    new SpeakingTrigger('B', '  1  '),
                    new SpeakingTrigger('C', '    1')]);

    banner('a SHORT timeline stops contributing; the long one goes on');
    await dispatch([new SpeakingTrigger('SHORT', '11'),
                    new SpeakingTrigger('LONG',  '111111')]);

    banner("the SCHEDULE as built -- '[tick] (priority)name'");
    say(String(new TriggerDispatcher([new SpeakingTrigger('A', '12'),
                                      new SpeakingTrigger('B', '21')])));
}

async function runPriority() {
    banner('digits swap between ticks: B leads at 0, A leads at 1');
    await dispatch([new SpeakingTrigger('A', '21'), new SpeakingTrigger('B', '12')]);

    banner('0 is the strongest digit, 9 the weakest');
    await dispatch([new SpeakingTrigger('WEAK', '9'), new SpeakingTrigger('STRONG', '0')]);
}

async function runStable() {
    banner('three triggers, all digit 1 at tick 0');
    await dispatch([new SpeakingTrigger('first', '1'), new SpeakingTrigger('second', '1'),
                    new SpeakingTrigger('third', '1')]);

    banner('registered BACKWARDS -- the order follows registration, not the name');
    await dispatch([new SpeakingTrigger('third', '1'), new SpeakingTrigger('second', '1'),
                    new SpeakingTrigger('first', '1')]);
}

async function runTermination() {
    banner('end_tick is the LENGTH -- 5 characters, last firing at tick 0');
    await dispatch([new SpeakingTrigger('EARLY', '1    ')]);

    banner('a trigger that NEVER fires is notified all the same');
    await dispatch([new SpeakingTrigger('FIRES', '1  '), new SpeakingTrigger('SILENT', '   ')]);

    banner('the LONGEST timeline sets end_tick for everybody');
    await dispatch([new SpeakingTrigger('SHORT', '1'), new SpeakingTrigger('LONG', '1      ')]);

    banner('a trigger that does not override is simply silent at the end');
    await dispatch([new SpeakingTrigger('SPEAKS', '1 '), new MuteTrigger('MUTE', '1 ')]);
}

async function runYielding() {
    banner('producer fires at every tick; consumer waits between them');

    class ProducingTrigger extends Trigger {
        constructor(name, timeline) {
            super(timeline, name);
            this.item = null;
            this.finished = false;
            say(`SETUP: ${name.padEnd(7)} |${timeline}|`);
        }
        async fire(pseudo_time) {
            this.item = `item@${pseudo_time}`;
            say(`  [t:${pseudo_time}] ${this.name} prepared ${this.item}`);
        }
        on_termination(end_tick) {
            this.finished = true;
            say(`  [end:${end_tick}] ${this.name} announced end-of-stream`);
        }
    }

    async function consume(producer) {
        let taken = 0;
        while (true) {
            while (producer.item === null) {
                if (producer.finished) {
                    say(`  consumer saw end-of-stream after ${taken} item(s)`);
                    return;
                }
                await sleep0();
            }
            taken += 1;
            say(`        consumer took ${producer.item}`);
            producer.item = null;
        }
    }

    const producer = new ProducingTrigger('PROD', '111');
    await gather(() => new TriggerDispatcher([producer]).run(), () => consume(producer));
    say('');
    say('Each item was taken BEFORE the next tick prepared one: the run yields.');
}

async function runStop() {
    banner('stop() after the first tick -- ticks 1.. are not walked, the announcement still comes');

    class StoppingTrigger extends SpeakingTrigger {
        constructor(name, timeline) { super(name, timeline); this.dispatcher = null; }
        async fire(pseudo_time) {
            await super.fire(pseudo_time);
            say('  ... asks the dispatcher to stop');
            this.dispatcher.stop();
        }
    }

    const stopper    = new StoppingTrigger('STOPPER', '1111');
    const bystander  = new SpeakingTrigger('OTHER',   '1111');
    const dispatcher = new TriggerDispatcher([stopper, bystander]);
    stopper.dispatcher = dispatcher;
    await dispatcher.run();

    say('');
    say("end_tick is still the timeline's length, not the tick the run stopped at.");
}

async function runCancel() {
    banner('cancel() the task carrying run() -- no announcement follows');
    const dispatcher = new TriggerDispatcher([new SpeakingTrigger('A', '1111111111')]);
    const task       = create_task(() => dispatcher.run());
    await sleep0();
    task.cancel();
    try {
        await task.promise;
    } catch (error) {
        if (!(error instanceof CancelledError)) throw error;
        say('  run() was cancelled');
    }
    say('');
    say("No '[end:..]' line above: the triggers were abandoned, not ended.");
}

async function runEdges() {
    banner('an EMPTY timeline -- end_tick 0');
    await dispatch([new SpeakingTrigger('EMPTY', '')]);

    banner('a timeline of BLANKS -- no digit, so nothing fires');
    await dispatch([new SpeakingTrigger('BLANK', '    ')]);

    banner('NO TRIGGERS at all -- nothing to announce, and no failure');
    await dispatch([]);
    say('  (dispatcher ran; nothing was scheduled)');

    banner('a timeline of blanks beside one that fires');
    await dispatch([new SpeakingTrigger('BLANK', '   '), new SpeakingTrigger('FIRES', ' 1 ')]);
}

async function runAbstract() {
    banner("the BASE 'fire' is abstract -- it refuses");
    class BareTrigger extends Trigger { }
    try {
        await dispatch([new BareTrigger('1', 'BARE')]);
    } catch (error) {
        if (!(error instanceof NotImplementedError)) throw error;
        say('  NotImplementedError -- as owed: a trigger must say what it does');
    }

    banner("the BASE 'on_termination' is optional -- it is silent");
    const bare = new BareTrigger('', 'BARE');
    bare.on_termination(0);
    say('  returned quietly; nothing raised, nothing printed');

    banner('a NAME given is the name kept');
    say(`  name: ${new Trigger('1', 'GIVEN').name}`);
}

new HwutRunner({
    argv:       process.argv.slice(1),
    title:      'TriggerDispatcher: schedule, priority, and the end of time',
    choice_map: {
        schedule:    runSchedule,
        priority:    runPriority,
        stable:      runStable,
        termination: runTermination,
        yielding:    runYielding,
        stop:        runStop,
        cancel:      runCancel,
        edges:       runEdges,
        abstract:    runAbstract,
    },
}).run();
