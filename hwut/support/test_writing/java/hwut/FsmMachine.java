/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
 *          port of 'Machine' in 'python/hwut_fsm.py' (README-hwut_fsm.txt).
 *          The states it may be in, the events that move it, the states it
 *          must never reach. A test FIRES the events it observes; every event
 *          the model does not allow, and every forbidden state entered, is
 *          WRITTEN as a line -- so it lands in the GOOD file.
 *
 *     FsmMachine m = FsmMachine.fromString("""
 *         initial: idle
 *         forbidden: crashed
 *         idle    ---( request )---> waiting ---( grant )---> busy
 *         busy    ---( release )---> idle
 *         :       ---( fault )--->   crashed
 *         """);
 *     m.fire("request", 1);       // true
 *     m.fire("release", 2);       // BREACH line 2: 'release' in 'waiting' -- allowed: grant
 *     m.report();
 *
 * The same model text, the same words, the same sorted reports as Python.
 * A MODEL THAT CANNOT BE MEANT throws FsmError where it is read.
 *
 * PYTHON'S KEYWORDS ARE OVERLOADS: 'fire(event)', 'fire(event, where)';
 * 'pathTo(state)', 'pathTo(state, start, masked)'; 'check()', 'check(masked)'.
 * 'where' is an Object: an Integer names a line ('line 3'), any other value
 * stands as its text, null names no place. 'with m.disallowed(...)' is
 * 'try (var phase = m.disallowed(...)) { ... }'.
 * _____________________________________________________________________________
 */
package hwut;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.function.Consumer;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class FsmMachine {
    /** One transition of the model: 'source' ---( event )---> 'target'. */
    public record Transition(String source, String event, String target) {}

    /** One transition fired: where, from, by, to. */
    public record Step(Object where, String state, String event, String target) {}

    /** A block during which a mask or a forbidden state stands; 'close'
     *  lifts it ('try (Phase p = m.disallowed(...)) { ... }'). */
    public static final class Phase implements AutoCloseable {
        private final Runnable leave;
        private Phase(Runnable enter, Runnable leave) { this.leave = leave; enter.run(); }
        /** RETURN: nothing; the phase ends -- however the block was left. */
        @Override public void close() { leave.run(); }
    }

    private record Key(String state, String event) {}

    private static final Comparator<Key> KEY_ORDER =
        Comparator.comparing(Key::state).thenComparing(Key::event);

    //  THE TEXT OF A MODEL (see 'fromString').
    private static final Pattern ARROW_RE = Pattern.compile("-+\\s*\\(\\s*([^()]*?)\\s*\\)\\s*-*>",
                                                            Pattern.UNICODE_CHARACTER_CLASS);
    private static final Pattern NAME_RE  = Pattern.compile("(?:state\\s+)?([A-Za-z_][\\w.\\-]*)",
                                                            Pattern.UNICODE_CHARACTER_CLASS);
    private static final Pattern KEY_RE   = Pattern.compile("(initial|forbidden|final)\\s*:\\s*(.*)",
                                                            Pattern.UNICODE_CHARACTER_CLASS | Pattern.DOTALL);

    public final String          name;
    public final boolean         dfaF;
    public final String          initial;
    private final Consumer<String> write;
    private final Map<Key, TreeSet<String>> edgeDb = new HashMap<>();
    private final Set<String>    modelForbidden;
    private final Set<String>    finalSet;
    private final List<String>   stateTuple;
    private final List<String>   eventTuple;

    private Map<Key, Object>     maskDb;            // (state | null, event) -> since
    private Map<String, Object>  forbidDb;          // state -> since
    private Map<String, Object>  permitDb;          // model-forbidden state -> since
    private Set<String>          current;
    private Map<String, Integer> visitDb;
    private Map<Transition, Integer> takenDb;
    private List<Step>           traceList;
    private int                  breachN;

    /** RETURN: FsmMachine over 'transitions', standing in 'initial' -- a DFA,
     *          named "fsm", writing to System.out, no state forbidden or final;
     *          throws FsmError as the full constructor does. */
    public FsmMachine(Collection<Transition> transitions, String initial) {
        this(transitions, initial, List.of(), List.of(), true, "fsm", null, List.of());
    }

    /** RETURN: FsmMachine, standing in 'initial', if success;
     *          throws FsmError, else -- a DFA ('dfaF') with two transitions
     *          for one (state, event); a forbidden or final state no
     *          transition names.
     *
     *  'states' names states no transition touches (yet). 'write' takes one
     *  line -- every breach and report goes through it; null writes a line
     *  to System.out. */
    public FsmMachine(Collection<Transition> transitions, String initial, Collection<String> forbidden,
                      Collection<String> fin, boolean dfaF, String name, Consumer<String> write,
                      Collection<String> states) {
        this.name    = name;
        this.dfaF    = dfaF;
        this.write   = write != null ? write : line -> System.out.println(line);
        this.initial = initial;
        Set<String> stateSet = new HashSet<>(states);
        stateSet.add(initial);
        for (Transition t : transitions) {
            TreeSet<String> targetSet = edgeDb.computeIfAbsent(new Key(t.source(), t.event()), k -> new TreeSet<>());
            if (dfaF && !targetSet.isEmpty() && !targetSet.contains(t.target()))
                throw new FsmError(String.format("'%s' --(%s)--> '%s' and '%s': a DFA moves one way per event -- or 'DFA=False'",
                                                 t.source(), t.event(), targetSet.first(), t.target()));
            targetSet.add(t.target());
            stateSet.add(t.source());
            stateSet.add(t.target());
        }
        modelForbidden = Collections.unmodifiableSet(new HashSet<>(forbidden));
        finalSet       = Collections.unmodifiableSet(new HashSet<>(fin));
        for (Object[] pair : new Object[][] { { "forbidden", modelForbidden }, { "final", finalSet } }) {
            @SuppressWarnings("unchecked") Set<String> chosen = (Set<String>) pair[1];
            TreeSet<String> unknown = new TreeSet<>(chosen);
            unknown.removeAll(stateSet);
            if (!unknown.isEmpty()) {
                List<String> quoted = new ArrayList<>();
                for (String s : unknown) quoted.add("'" + s + "'");
                throw new FsmError(pair[0] + " state(s) " + String.join(", ", quoted)
                                   + ": named nowhere else in the model");
            }
        }
        TreeSet<String> all = new TreeSet<>(stateSet);
        all.addAll(modelForbidden);
        stateTuple = List.copyOf(all);
        TreeSet<String> events = new TreeSet<>();
        for (Key k : edgeDb.keySet()) events.add(k.event());
        eventTuple = List.copyOf(events);
        reset();
    }

    // ------------------------------------------------------------- reading
    /** RETURN: FsmMachine, the model the text states -- a DFA named "fsm"
     *          writing to System.out -- if success; throws FsmError naming
     *          the line, else. See the full 'fromString'. */
    public static FsmMachine fromString(String text) { return fromString(text, true, "fsm", null); }

    /** RETURN: FsmMachine, the model the text states, if success;
     *          throws FsmError naming the line, else.
     *
     *  One statement per line; '#' starts a comment:
     *      initial: A              where the machine starts; default: the
     *                              first state the text names
     *      forbidden: X, Y         states the system must never enter
     *      final: A, B             states it may end in
     *      state A                 a state, transitions or not
     *      A ---( ev )---> B ---( ev2 )---> C     transitions, chained
     *      :  ---( ev )---> D      ':' is the state that began the line above */
    public static FsmMachine fromString(String text, boolean dfaF, String name, Consumer<String> write) {
        List<String[]>            tripleList = new ArrayList<>();
        Map<String, List<String>> declared   = new HashMap<>();
        Map<Key, Object[]>        lineOf     = new HashMap<>();   // -> { target, line }
        String first = null, previousHead = null;
        int number = 0;
        for (String raw : splitLines(text)) {
            number += 1;
            int hash = raw.indexOf('#');
            String line = (hash < 0 ? raw : raw.substring(0, hash)).strip();
            if (line.isEmpty()) continue;
            Matcher key = KEY_RE.matcher(line);
            if (key.matches()) {
                String word = key.group(1), rest = key.group(2);
                List<String> nameList = new ArrayList<>();
                for (String part : rest.split(",", -1)) if (!part.strip().isEmpty()) nameList.add(nameOf(part, number));
                if (word.equals("initial") && nameList.size() != 1)
                    throw new FsmError("line " + number + ": 'initial:' names one state");
                declared.computeIfAbsent(word, k -> new ArrayList<>()).addAll(nameList);
                continue;
            }
            List<String> partList = split(ARROW_RE, line);
            //  [state, event, state, event, state ...]: odd places are events
            if (partList.size() == 1) {
                String head = nameOf(line, number);
                if (first == null) first = head;
                tripleList.add(new String[] { head, null, null });
                previousHead = head;
                continue;
            }
            for (int i = 1; i < partList.size(); i += 2)
                if (partList.get(i).strip().isEmpty())
                    throw new FsmError("line " + number + ": an arrow names no event -- '---( event )--->'");
            String headText = partList.get(0).strip(), head;
            if (headText.equals(":")) {
                if (previousHead == null)
                    throw new FsmError("line " + number + ": ':' stands for the state of the line above, and none stands there");
                head = previousHead;
            } else head = nameOf(headText, number);
            if (first == null) first = head;
            previousHead = head;
            String source = head;
            for (int i = 1; i < partList.size(); i += 2) {
                String target = nameOf(partList.get(i + 1), number);
                String event  = partList.get(i).strip();
                Key    k      = new Key(source, event);
                //  THE DFA'S CONFLICT NAMED WHERE IT STANDS: both lines.
                if (dfaF && lineOf.containsKey(k) && !lineOf.get(k)[0].equals(target))
                    throw new FsmError(String.format("line %d: '%s' --(%s)--> '%s', and line %d: --> '%s' -- a DFA moves one way per event, or 'DFA=False'",
                                                     number, source, event, target, lineOf.get(k)[1], lineOf.get(k)[0]));
                lineOf.putIfAbsent(k, new Object[] { target, number });
                tripleList.add(new String[] { source, event, target });
                source = target;
            }
        }
        if (first == null && !declared.containsKey("initial")) throw new FsmError("the model names no state");
        List<String> declaredInitial = declared.get("initial");
        String start = (declaredInitial == null || declaredInitial.isEmpty()) ? first : declaredInitial.get(0);
        List<Transition> transitions = new ArrayList<>();
        Set<String>      states      = new HashSet<>();
        for (String[] t : tripleList) {
            if (t[1] != null) transitions.add(new Transition(t[0], t[1], t[2]));
            else              states.add(t[0]);
        }
        return new FsmMachine(transitions, start, declared.getOrDefault("forbidden", List.of()),
                              declared.getOrDefault("final", List.of()), dfaF, name, write, states);
    }

    /** RETURN: String, the model in the text 'fromString' reads, one
     *          transition per line, sorted -- what a GOOD file can show of it
     *          (Python's 'to_string'). */
    @Override public String toString() {
        List<String> lineList = new ArrayList<>();
        lineList.add("initial: " + initial);
        if (!modelForbidden.isEmpty()) lineList.add("forbidden: " + String.join(", ", new TreeSet<>(modelForbidden)));
        if (!finalSet.isEmpty())       lineList.add("final: " + String.join(", ", new TreeSet<>(finalSet)));
        Set<String> named = new HashSet<>(Set.of(initial));
        for (Key k : sortedKeys()) {
            for (String target : edgeDb.get(k)) {
                lineList.add(k.state() + " ---( " + k.event() + " )---> " + target);
                named.add(k.state());
                named.add(target);
            }
        }
        for (String s : stateTuple) if (!named.contains(s) && !modelForbidden.contains(s)) lineList.add("state " + s);
        return String.join("\n", lineList);
    }

    // ------------------------------------------------------------- running
    /** RETURN: nothing; the machine stands in its initial state again, under
     *          the model as written: what was seen is forgotten, and so is
     *          every mask and every state forbidden or permitted since. */
    public void reset() {
        maskDb    = new HashMap<>();
        forbidDb  = new LinkedHashMap<>();
        for (String s : modelForbidden) forbidDb.put(s, null);
        permitDb  = new HashMap<>();
        current   = new TreeSet<>(Set.of(initial));
        visitDb   = new HashMap<>(Map.of(initial, 1));
        takenDb   = new HashMap<>();
        traceList = new ArrayList<>();
        breachN   = 0;
    }

    /** RETURN: boolean, 'fire(event, null)' -- a breach line names no place. */
    public boolean fire(String event) { return fire(event, null); }

    /** RETURN: boolean, true where 'event' moved the machine and entered no
     *          forbidden state; false where it was not allowed where the
     *          machine stands -- a BREACH line is written and the machine
     *          stays -- or where it entered a forbidden state, which is
     *          written too. 'where' is the place the breach line names. */
    public boolean fire(String event, Object where) {
        TreeSet<String> moved  = new TreeSet<>();
        List<String>    masked = new ArrayList<>();
        for (String state : current) {
            Key k = new Key(state, event);
            if (maskedF(state, event)) {
                if (edgeDb.containsKey(k)) masked.add(state);
                continue;
            }
            for (String target : edgeDb.getOrDefault(k, new TreeSet<>())) {
                moved.add(target);
                takenDb.merge(new Transition(state, event, target), 1, Integer::sum);
                traceList.add(new Step(where, state, event, target));
            }
        }
        if (moved.isEmpty()) {
            breachN += 1;
            List<String> allowed = allowed();
            String hint = allowed.isEmpty() ? "no event leaves it" : "allowed: " + String.join(", ", allowed);
            if (!eventTuple.contains(event)) hint = "an event the model never names";
            else if (!masked.isEmpty()) {
                Key    one   = new Key(masked.get(0), event);
                Object since = maskDb.containsKey(one) ? maskDb.get(one) : maskDb.get(new Key(null, event));
                hint = "disallowed" + sinceText(since);
            }
            write.accept("BREACH" + whereText(where) + ": '" + event + "' in " + here() + " -- " + hint);
            return false;
        }
        current = moved;
        for (String state : moved) visitDb.merge(state, 1, Integer::sum);
        TreeSet<String> entered = new TreeSet<>(moved);
        entered.retainAll(forbidDb.keySet());
        for (String state : entered) {
            breachN += 1;
            write.accept("BREACH" + whereText(where) + ": '" + state + "' entered by '" + event + "' -- "
                         + (modelForbidden.contains(state) && forbidDb.get(state) == null
                            ? "a forbidden state" : "forbidden" + sinceText(forbidDb.get(state))));
        }
        return entered.isEmpty();
    }

    // --------------------------------------------------- the law, changing
    /** RETURN: Set of String, the states forbidden NOW -- the model's, less
     *          those permitted, with those forbidden since; unmodifiable. */
    public Set<String> forbidden() { return Collections.unmodifiableSet(new HashSet<>(forbidDb.keySet())); }

    /** RETURN: boolean, true if 'event' is disallowed in 'state' now -- in
     *          every state, or in that one. */
    private boolean maskedF(String state, String event) {
        return maskDb.containsKey(new Key(null, event)) || maskDb.containsKey(new Key(state, event));
    }

    /** RETURN: nothing, where 'event' and 'state' (either may be null) are
     *          named by the model; throws FsmError naming what is not, else. */
    private void known(String event, String state) {
        if (event != null && !eventTuple.contains(event))
            throw new FsmError("'" + event + "': an event the model never names -- events: " + String.join(", ", eventTuple));
        if (state != null && !stateTuple.contains(state))
            throw new FsmError("'" + state + "': a state the model never names -- states: " + String.join(", ", stateTuple));
    }

    /** RETURN: nothing; 'disallow(event, null, null)' -- in every state. */
    public void disallow(String event) { disallow(event, null, null); }

    /** RETURN: nothing; from now on 'event' is a breach -- in 'state' alone,
     *          or in every state where null -- until 'allow' lifts it; the
     *          breach line says 'disallowed since <where>'. A mask already
     *          standing keeps its 'where'. Throws FsmError where the model
     *          names no such event or state. */
    public void disallow(String event, String state, Object where) {
        known(event, state);
        Key k = new Key(state, event);
        if (!maskDb.containsKey(k)) maskDb.put(k, where);
    }

    /** RETURN: nothing; 'allow(event, null, null)' -- the every-state mask. */
    public void allow(String event) { allow(event, null, null); }

    /** RETURN: nothing; the mask 'disallow(event, state)' set is lifted; a
     *          mask set for another scope stays. 'where' is not kept.
     *          Throws FsmError where the model names no such event or state. */
    public void allow(String event, String state, Object where) {
        known(event, state);
        maskDb.remove(new Key(state, event));
    }

    /** RETURN: nothing; 'forbid(state, null)'. */
    public void forbid(String state) { forbid(state, null); }

    /** RETURN: nothing; from now on entering 'state' is a breach, until
     *          'permit'. Where the machine STANDS in it, one BREACH line is
     *          written at once. Throws FsmError where the model names no
     *          such state. */
    public void forbid(String state, Object where) {
        known(null, state);
        if (forbidDb.containsKey(state)) return;
        forbidDb.put(state, where);
        permitDb.remove(state);
        if (current.contains(state)) {
            breachN += 1;
            write.accept("BREACH" + whereText(where) + ": stands in '" + state + "' -- forbidden" + sinceText(where));
        }
    }

    /** RETURN: nothing; 'permit(state, null)'. */
    public void permit(String state) { permit(state, null); }

    /** RETURN: nothing; 'state' is no longer forbidden -- a state of the
     *          model's own 'forbidden:' too, until 'forbid' again (the report
     *          says 'permitted' for that one). Throws FsmError where the model
     *          names no such state. */
    public void permit(String state, Object where) {
        known(null, state);
        boolean presentF = forbidDb.containsKey(state);
        forbidDb.remove(state);
        if (presentF && modelForbidden.contains(state)) permitDb.put(state, where);
    }

    /** RETURN: Phase, 'event' disallowed (see 'disallow') until the phase is
     *          closed -- 'try (Phase p = m.disallowed(...)) { ... }'. */
    public Phase disallowed(String event, String state, Object where) {
        return new Phase(() -> disallow(event, state, where), () -> allow(event, state, null));
    }

    /** RETURN: Phase, 'state' forbidden (see 'forbid') until the phase is
     *          closed. */
    public Phase forbidding(String state, Object where) {
        return new Phase(() -> forbid(state, where), () -> permit(state, null));
    }

    /** RETURN: String, where the machine stands: "'idle'", or "{'a', 'b'}"
     *          for a set. */
    private String here() {
        if (current.size() == 1) return "'" + current.iterator().next() + "'";
        List<String> quoted = new ArrayList<>();
        for (String s : current) quoted.add("'" + s + "'");
        return "{" + String.join(", ", quoted) + "}";
    }

    // ------------------------------------------------------------ questions
    /** RETURN: String, the one state the machine stands in, if success;
     *          throws FsmError, else -- a set of states stands (DFA false):
     *          ask 'current()'. */
    public String state() {
        if (current.size() != 1) throw new FsmError("the machine stands in " + here() + ": ask 'current()'");
        return current.iterator().next();
    }

    /** RETURN: Set of String, every state the machine stands in, sorted;
     *          unmodifiable. */
    public Set<String> current() { return Collections.unmodifiableSet(current); }

    /** RETURN: boolean, true if the machine stands in 'state'. */
    public boolean inState(String state) { return current.contains(state); }

    /** RETURN: boolean, true if 'event' would move the machine now. */
    public boolean can(String event) {
        for (String s : current) if (edgeDb.containsKey(new Key(s, event)) && !maskedF(s, event)) return true;
        return false;
    }

    /** RETURN: List of String, the events that would move the machine now,
     *          sorted. */
    public List<String> allowed() {
        TreeSet<String> result = new TreeSet<>();
        for (Key k : edgeDb.keySet()) if (current.contains(k.state()) && !maskedF(k.state(), k.event())) result.add(k.event());
        return List.copyOf(result);
    }

    /** RETURN: List of Step, every transition fired, in order. */
    public List<Step> trace() { return List.copyOf(traceList); }

    /** RETURN: int, the breaches seen so far. */
    public int breachN() { return breachN; }

    // ------------------------------------------------------ the model alone
    /** RETURN: Map, state -> list of { event, target } leaving it, sorted --
     *          under the masks where 'masked', as written else. */
    private Map<String, List<String[]>> successorDb(boolean masked) {
        Map<String, List<String[]>> found = new HashMap<>();
        for (Map.Entry<Key, TreeSet<String>> e : edgeDb.entrySet()) {
            Key k = e.getKey();
            if (masked && maskedF(k.state(), k.event())) continue;
            for (String target : e.getValue())
                found.computeIfAbsent(k.state(), s -> new ArrayList<>()).add(new String[] { k.event(), target });
        }
        for (List<String[]> pairList : found.values())
            pairList.sort(Comparator.<String[], String>comparing(p -> p[0]).thenComparing(p -> p[1]));
        return found;
    }

    /** RETURN: List of String, 'pathTo(state, null, true)'. */
    public List<String> pathTo(String state) { return pathTo(state, null, true); }

    /** RETURN: List of String, the shortest sequence of events from 'start'
     *          -- the initial state where null, "now" for where the machine
     *          stands -- into 'state', if one exists (empty where 'start' is
     *          'state'); among equally short paths the one first in event
     *          order; under the masks standing now unless not 'masked';
     *          null, else: 'state' cannot be reached from there. */
    public List<String> pathTo(String state, String start, boolean masked) {
        Set<String> startSet = "now".equals(start) ? new TreeSet<>(current)
                             : new TreeSet<>(Set.of(start == null ? initial : start));
        if (startSet.contains(state)) return List.of();
        Map<String, List<String[]>> successor = successorDb(masked);
        ArrayDeque<Object[]> queue = new ArrayDeque<>();
        for (String s : startSet) queue.add(new Object[] { s, List.<String>of() });
        Set<String> seen = new HashSet<>(startSet);
        while (!queue.isEmpty()) {
            Object[] head = queue.poll();
            @SuppressWarnings("unchecked") List<String> path = (List<String>) head[1];
            for (String[] pair : successor.getOrDefault((String) head[0], List.of())) {
                if (seen.contains(pair[1])) continue;
                List<String> longer = new ArrayList<>(path);
                longer.add(pair[0]);
                if (pair[1].equals(state)) return List.copyOf(longer);
                seen.add(pair[1]);
                queue.add(new Object[] { pair[1], longer });
            }
        }
        return null;
    }

    /** RETURN: boolean, 'stateReachable(state, null, true)'. */
    public boolean stateReachable(String state) { return stateReachable(state, null, true); }

    /** RETURN: boolean, true if 'state' can be reached from 'start' (see
     *          'pathTo'). */
    public boolean stateReachable(String state, String start, boolean masked) {
        return pathTo(state, start, masked) != null;
    }

    /** RETURN: Set of String, the states forbidden now where 'masked', the
     *          model's own else. */
    private Set<String> forbiddenOf(boolean masked) { return masked ? forbidDb.keySet() : modelForbidden; }

    /** RETURN: List of String, the states no path from the initial state
     *          reaches, forbidden ones left out -- sorted; under the masks
     *          unless not 'masked'. */
    public List<String> unreachable(boolean masked) {
        List<String> result = new ArrayList<>();
        Set<String>  forbidden = forbiddenOf(masked);
        for (String s : stateTuple) if (!forbidden.contains(s) && !stateReachable(s, null, masked)) result.add(s);
        return result;
    }

    /** RETURN: List of String, the states no event leaves that are neither
     *          final nor forbidden -- where a system would hang -- sorted;
     *          under the masks unless not 'masked'. */
    public List<String> deadEnds(boolean masked) {
        Map<String, List<String[]>> successor = successorDb(masked);
        Set<String>  forbidden = forbiddenOf(masked);
        List<String> result = new ArrayList<>();
        for (String s : stateTuple)
            if (!successor.containsKey(s) && !finalSet.contains(s) && !forbidden.contains(s)) result.add(s);
        return result;
    }

    /** RETURN: List of String, the forbidden states the model lets the system
     *          reach from the initial state -- sorted; under the masks and the
     *          states forbidden now unless not 'masked'. */
    public List<String> forbiddenReachable(boolean masked) {
        List<String> result = new ArrayList<>();
        for (String s : new TreeSet<>(forbiddenOf(masked))) if (stateReachable(s, null, masked)) result.add(s);
        return result;
    }

    /** RETURN: int, 'check(true)'. */
    public int check() { return check(true); }

    /** RETURN: int, how many findings the MODEL has, each written as one line
     *          'MODEL: ...' -- states no path reaches, dead ends, forbidden
     *          states it lets be reached (with the shortest way there);
     *          under the masks standing now unless not 'masked'; 0 for none. */
    public int check(boolean masked) {
        List<String> lineList = new ArrayList<>();
        for (String s : unreachable(masked)) lineList.add("MODEL: '" + s + "' cannot be reached");
        for (String s : deadEnds(masked))    lineList.add("MODEL: '" + s + "' is a dead end -- no event leaves it");
        for (String s : forbiddenReachable(masked))
            lineList.add("MODEL: forbidden '" + s + "' is reachable: " + String.join(" ", pathTo(s, null, masked)));
        for (String line : lineList) write.accept(line);
        return lineList.size();
    }

    // -------------------------------------------------------------- the end
    /** RETURN: int, the breaches seen, counting a non-final end; written
     *          before it, sorted, what the events covered of the model --
     *          states counted without the forbidden ones:
     *              fsm: 3 of 3 states visited, 3 of 4 transitions taken, 1 breach
     *                taken      idle ---( request )---> waiting   x2
     *                not taken  busy ---( fault )---> crashed
     *                never in   ...
     *                ended in   'idle'
     *          then the masks and forbidden or permitted states still
     *          standing; a machine with final states that ends elsewhere adds
     *          a BREACH line. */
    public int report() {
        List<Transition> allEdge = new ArrayList<>();
        for (Key k : sortedKeys()) for (String t : edgeDb.get(k)) allEdge.add(new Transition(k.state(), k.event(), t));
        int breach = breachN;
        boolean endF = finalSet.isEmpty() || current.stream().anyMatch(finalSet::contains);
        if (!endF) breach += 1;
        //  A FORBIDDEN STATE IS NO GOAL OF COVERAGE: counted out.
        int goalN = 0, visitedN = 0;
        for (String s : stateTuple) {
            if (modelForbidden.contains(s)) continue;
            goalN += 1;
            if (visitDb.containsKey(s)) visitedN += 1;
        }
        write.accept(String.format("%s: %d of %d states visited, %d of %d transitions taken, %d breach%s",
                                   name, visitedN, goalN, takenDb.size(), allEdge.size(), breach,
                                   breach == 1 ? "" : "es"));
        for (Transition edge : allEdge) {
            Integer n = takenDb.get(edge);
            write.accept("  " + (n != null ? "taken    " : "not taken") + "  " + edge.source() + " ---( "
                         + edge.event() + " )---> " + edge.target() + (n != null && n > 1 ? "   x" + n : ""));
        }
        for (String state : stateTuple)
            if (!visitDb.containsKey(state) && !modelForbidden.contains(state)) write.accept("  never in   '" + state + "'");
        write.accept("  ended in   " + here());
        //  A PHASE NEVER LIFTED IS SAID: what still stands at the end.
        List<Key> maskList = new ArrayList<>(maskDb.keySet());
        maskList.sort(Comparator.comparing(Key::event)
                                .thenComparing(k -> k.state() == null ? "" : k.state()));
        for (Key k : maskList)
            write.accept("  disallowed '" + k.event() + "' "
                         + (k.state() == null ? "in every state" : "in '" + k.state() + "'") + sinceText(maskDb.get(k)));
        TreeSet<String> forbiddenSince = new TreeSet<>(forbidDb.keySet());
        forbiddenSince.removeAll(modelForbidden);
        for (String state : forbiddenSince) write.accept("  forbidden  '" + state + "'" + sinceText(forbidDb.get(state)));
        for (String state : new TreeMap<>(permitDb).keySet())
            write.accept("  permitted  '" + state + "'" + sinceText(permitDb.get(state)));
        if (!endF) write.accept("BREACH: ended in " + here() + " -- final: " + String.join(", ", new TreeSet<>(finalSet)));
        return breach;
    }

    // --------------------------------------------------------------- helpers
    /** RETURN: List of Key, the keys of the edge table sorted by (state,
     *          event). */
    private List<Key> sortedKeys() {
        List<Key> keyList = new ArrayList<>(edgeDb.keySet());
        keyList.sort(KEY_ORDER);
        return keyList;
    }

    /** RETURN: String, the state named by 'text' -- 'A' or 'state A' -- if
     *          success; throws FsmError naming line 'number', else. */
    private static String nameOf(String text, int number) {
        Matcher found = NAME_RE.matcher(text.strip());
        if (!found.matches())
            throw new FsmError("line " + number + ": '" + text.strip()
                               + "' names no state -- a state is a word ('A', 'state A')");
        return found.group(1);
    }

    /** RETURN: String, " line 3" for the Integer 3, " <text>" for any other
     *          value, "" for null -- the place a breach line names. */
    private static String whereText(Object where) {
        if (where == null) return "";
        if (where instanceof Integer || where instanceof Long) return " line " + where;
        return " " + where;
    }

    /** RETURN: String, " since line 9" for 9, " since <text>" for a text, ""
     *          for null -- when a mask or a forbidden state began. */
    private static String sinceText(Object where) { return where == null ? "" : " since" + whereText(where); }

    /** RETURN: List of String, 'text' cut by 'pattern' with the pattern's
     *          group 1 kept between the pieces (Python's 're.split'). */
    private static List<String> split(Pattern pattern, String text) {
        List<String> result = new ArrayList<>();
        Matcher m = pattern.matcher(text);
        int at = 0;
        while (m.find()) {
            result.add(text.substring(at, m.start()));
            result.add(m.group(1));
            at = m.end();
        }
        result.add(text.substring(at));
        return result;
    }

    /** RETURN: List of String, 'text' cut at its line boundaries as Python's
     *          'str.splitlines' cuts: '\n', '\r\n', '\r', '\u000b', '\f',
     *          '\u001c'..'\u001e', '\u0085', ' ', ' '; no empty
     *          last piece after a final boundary. */
    static List<String> splitLines(String text) {
        List<String> result = new ArrayList<>();
        int at = 0, i = 0, n = text.length();
        while (i < n) {
            char c = text.charAt(i);
            boolean breakF = c == '\n' || c == '\r' || c == '\u000b' || c == '\f' || (c >= '\u001c' && c <= '\u001e')
                             || c == '\u0085' || c == ' ' || c == ' ';
            if (!breakF) { ++i; continue; }
            result.add(text.substring(at, i));
            i += (c == '\r' && i + 1 < n && text.charAt(i + 1) == '\n') ? 2 : 1;
            at = i;
        }
        if (at < n) result.add(text.substring(at));
        return result;
    }
}
