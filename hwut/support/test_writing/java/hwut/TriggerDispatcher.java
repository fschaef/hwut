/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: RACES DRAWN AS STRINGS -- the port of 'TriggerDispatcher' in
 *          'python/deterministic_timeline.py': the position of a digit in a
 *          trigger's timeline is its tick, the digit its priority within the
 *          tick (0 first), equal digits in registration order.
 *
 *         Trigger A: "1  12 1"
 *         Trigger B: " 1  1 2"
 *
 *     Async.run(() -> new TriggerDispatcher(List.of(a, b, c)).run());
 *
 * 'run' is a COROUTINE (see 'Async'): it fires every trigger due at a tick in
 * order and YIELDS after each, so a consumer task beside it takes what was
 * produced before the next tick. THE END OF THE TIMELINE IS AN EVENT: every
 * trigger is told 'onTermination(endTick)', 'endTick' the length of the
 * longest timeline -- also after 'stop()'. A cancelled run announces
 * nothing: a cancellation is an abandonment, not an ending.
 * _____________________________________________________________________________
 */
package hwut;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public final class TriggerDispatcher {
    /** ONE FIRING: at its tick, with its priority. */
    private record Firing(int priority, Trigger trigger) {}

    private volatile boolean      runningF = true;
    private final List<Trigger>   triggerList;
    private final List<List<Firing>> triggerTimeDb;
    private final int             endTick;

    /** RETURN: TriggerDispatcher over 'triggers', its timeline built: one
     *          entry per tick up to the longest timeline. */
    public TriggerDispatcher(List<? extends Trigger> triggers) {
        triggerList   = new ArrayList<>(triggers);
        triggerTimeDb = build(triggerList);
        endTick       = triggerTimeDb.size();
    }

    /** RETURN: List of List of Firing, one entry per tick; entry t holds the
     *          firings whose timeline carries a digit at position t, sorted
     *          by priority -- equal ones in registration order (the sort is
     *          stable). As long as the longest timeline; empty for none. */
    private static List<List<Firing>> build(List<Trigger> triggers) {
        int end = 0;
        for (Trigger t : triggers) end = Math.max(end, t.timeline.length());
        List<List<Firing>> result = new ArrayList<>();
        for (int i = 0; i < end; ++i) result.add(new ArrayList<>());
        for (Trigger trigger : triggers) {
            for (int t = 0; t < trigger.timeline.length(); ++t) {
                char c = trigger.timeline.charAt(t);
                if (Character.isDigit(c)) result.get(t).add(new Firing(Character.digit(c, 10), trigger));
            }
        }
        for (List<Firing> tick : result) tick.sort(Comparator.comparingInt(Firing::priority));
        return result;
    }

    /** RETURN: nothing; the run leaves the timeline at the next firing and
     *          still announces termination on its way out. */
    public void stop() { runningF = false; }

    /** RETURN: nothing, once the timeline is walked -- or 'stop()' cut it
     *          short -- and every trigger was told 'onTermination(endTick)'.
     *          A COROUTINE: call it in a task ('Async'); it yields after
     *          every firing. Throws what a 'fire' throws, CancelledError
     *          where its task is cancelled -- and then announces nothing. */
    public void run() {
        outer:
        for (int pseudoTime = 0; pseudoTime < triggerTimeDb.size(); ++pseudoTime) {
            if (!runningF) break;
            for (Firing firing : triggerTimeDb.get(pseudoTime)) {
                if (!runningF) break outer;
                firing.trigger().fire(pseudoTime);
                Async.sleep0();
            }
        }
        for (Trigger trigger : triggerList) trigger.onTermination(endTick);
    }

    /** RETURN: String, the built timeline, one line per scheduled firing --
     *          '[tick] (priority)name' -- after the line 'TriggerDispatcher';
     *          ticks ascending, within a tick in the order of the run
     *          (Python's 'repr'). */
    @Override public String toString() {
        List<String> result = new ArrayList<>();
        result.add("TriggerDispatcher");
        for (int t = 0; t < triggerTimeDb.size(); ++t)
            for (Firing f : triggerTimeDb.get(t))
                result.add("[" + t + "] (" + f.priority() + ")" + f.trigger().name);
        return String.join("\n", result);
    }
}
