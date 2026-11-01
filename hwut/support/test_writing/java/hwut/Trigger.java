/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: ONE DISPATCHABLE EVENT OF A TIMELINE -- the port of 'Trigger' in
 *          'python/deterministic_timeline.py'; see 'TriggerDispatcher'.
 *
 *     class MyTrigger extends Trigger {
 *         MyTrigger(String timeline, String name) { super(timeline, name); }
 *         @Override public void fire(int pseudoTime) { System.out.println(name + " fired"); }
 *     }
 *
 * 'fire' is the coroutine: it runs as a part of the dispatcher's task and may
 * yield ('Async.sleep0()'). It REFUSES in the base -- a trigger that does
 * nothing at its tick has no reason to stand in the timeline -- but it is not
 * Java-abstract, as Python's is not: a Trigger can be made, and refuses only
 * when it fires. 'onTermination' is optional and silent.
 * _____________________________________________________________________________
 */
package hwut;

public class Trigger {
    /** The timeline: a digit '0'..'9' at position t fires at tick t, the
     *  digit its priority (lower first); anything else is no firing. */
    public final String timeline;
    /** The name a report prints. */
    public final String name;

    /** RETURN: Trigger on 'timeline', named 'name' -- 'trigger-<identity>'
     *          where 'name' is null or empty. */
    public Trigger(String timeline, String name) {
        this.timeline = timeline;
        this.name     = (name == null || name.isEmpty())
                      ? "trigger-" + System.identityHashCode(this) : name;
    }

    /** RETURN: Trigger on 'timeline', named 'trigger-<identity>'. */
    public Trigger(String timeline) { this(timeline, ""); }

    /** RETURN: nothing; the action this trigger performs at 'pseudoTime', a
     *          tick its timeline marked with a digit. Runs in the
     *          dispatcher's task and may yield. Throws
     *          UnsupportedOperationException in the base (Python's
     *          NotImplementedError): a derived class says what it does. */
    public void fire(int pseudoTime) {
        throw new UnsupportedOperationException("Trigger.fire: a trigger must say what it does");
    }

    /** RETURN: nothing; the action this trigger performs once the timeline
     *          has passed -- announcing end-of-stream, typically. 'endTick'
     *          is the timeline's length. Does nothing in the base; not a
     *          coroutine: the run is over, nobody is left to yield to. */
    public void onTermination(int endTick) {}
}
