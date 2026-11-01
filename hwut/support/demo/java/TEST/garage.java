/* @hwut {
 *     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
 *     build    { framework = "make", executable = "%.exe" }
 *     interactive = true
 *     choices {
 *         space       { features = ["space-from-hocon", "space-iterator", "hwut-runner"]
 *                       tolerance { constraints = ["mismatches == 0"] } }
 *         random      { features = ["deterministic-stream", "hwut-runner"]
 *                       tolerance { constraints = ["mismatches == 0"] } }
 *         race-naive  { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
 *                       tolerance { constraints = ["overbooked > 0"] } }
 *         race-atomic { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
 *                       tolerance { constraints = ["overbooked == 0"] } }
 *     }
 * }
 * ______________________________________________________________________________
 * SUBJECT  the counter of free spaces at a garage's gates: which cars it
 *          admits, which it refuses, and how many stand inside.
 * REQUIREMENT  The garage admits a car only while a space is free, lets a car
 *              out only while one stands inside, and never holds more cars
 *              than it has spaces -- also when two gates admit at once.
 *
 * No choice writes its cases out by hand. Each GENERATES them, with one of
 * hwut's helpers for writing tests -- the Java port, package 'hwut':
 *
 * space        'garage-space.hocon' states the tested space -- capacities,
 *              cars arriving, cars leaving -- in hwut's HOCON, read by
 *              'Hocon.parse'. A reviewer edits the space without reading
 *              Java. 'SpaceIterator.product' walks every combination: 3 x 5 x
 *              4 = 60 cases. Each is printed as one cell of a matrix, and
 *              checked against the model: admitted = min(arriving,
 *              capacity), out = min(leaving, admitted).
 *
 * random       'new DeterministicStream(4711)' draws 1000 cars arriving and
 *              leaving at a garage of 5. The draw is the same on every
 *              machine and in every language hwut supports -- the stream is
 *              a linear congruential generator, not java.util.Random -- so
 *              the GOOD is exact (it is the Python demo's), and a failing run
 *              can be replayed by its seed.
 *
 * race-naive   two gates, one free space. A gate CHECKS whether a space is
 *              free, and later ADMITS its car. 'TriggerDispatcher' runs the
 *              two gates as Triggers on timelines drawn as strings -- '1 1 '
 *              fires at tick 0 and tick 2 -- so every interleaving is played
 *              exactly, not hoped for with sleeps. 'SpaceIterator'
 *              generates all six interleavings of two two-step gates in four
 *              ticks. Where both gates check before either admits, both
 *              admit: the garage is overbooked. The law is 'overbooked > 0':
 *              the GOOD is the accepted violation report.
 *
 * race-atomic  the same six interleavings, the gate checking and admitting
 *              in ONE step under the counter's lock. 'overbooked == 0'.
 *
 * THE FRONT END is hwut's HwutRunner: the choice map below is the whole
 * command line, '--hwut-info' included. The header says
 * 'interactive = true': hwut starts the application ONCE and asks for the
 * choices one after another in that one session -- each choice in a JVM of
 * its own (Java has no fork); a choice's output equals what it prints when
 * run alone.
 * ______________________________________________________________________________
 */
import hwut.Async;
import hwut.DeterministicStream;
import hwut.Hocon;
import hwut.HwutRunner;
import hwut.PyText;
import hwut.SpaceIterator;
import hwut.Trigger;
import hwut.TriggerDispatcher;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Consumer;

final class Garage {
    /** The unit under test: a counter of the spaces a garage has. ('Garage'
     *  is the application's class -- the Makefile names it after the file.) */
    static final class Counter {
        final int capacity;
        int       occupied = 0;

        /** RETURN: Counter, an empty garage of 'capacity' spaces. */
        Counter(int capacity) { this.capacity = capacity; }

        /** RETURN: int, the number of spaces free now -- negative where the
         *          garage is overbooked. */
        int free() { return capacity - occupied; }

        /** RETURN: true, a car was admitted, if a space was free;
         *          false, else (the car is refused). */
        boolean arrive() {
            if (free() <= 0) return false;
            occupied += 1;
            return true;
        }

        /** RETURN: true, a car drove out, if one stood inside;
         *          false, else. */
        boolean leave() {
            if (occupied == 0) return false;
            occupied -= 1;
            return true;
        }
    }

    /** RETURN: Path, the directory this test stands in -- the parent of the
     *          classes directory it runs from. */
    static Path here() {
        try {
            return Path.of(Garage.class.getProtectionDomain().getCodeSource().getLocation().toURI()).getParent();
        } catch (java.net.URISyntaxException error) {
            throw new IllegalStateException(error);
        }
    }

    /** RETURN: nothing; 'format' laid out with 'args' is printed as one line. */
    static void say(String format, Object... args) {
        System.out.println(String.format(Locale.ROOT, format, args));
    }

    // _________________________________________________________________________
    // space -- the tested space from HOCON, walked by SpaceIterator
    //
    /** One dimension of the space: its name and its values. */
    record Dimension(String name, List<Long> values) {}

    /** RETURN: List of Dimension, the dimensions of the space in 'path', in
     *          the order written. Every fault the HOCON reader found is
     *          printed with '!!' first. */
    static List<Dimension> readSpace(Path path) {
        List<String> textList;
        try { textList = Files.readAllLines(path, StandardCharsets.UTF_8); }
        catch (IOException error) { throw new IllegalStateException(error); }
        List<Hocon.SourceLine> lineList = new ArrayList<>();
        for (int i = 0; i < textList.size(); ++i) lineList.add(new Hocon.SourceLine(textList.get(i), i + 1, 0));
        Hocon.Result result = Hocon.parse(lineList, path.getFileName().toString());
        for (Hocon.ParseFault fault : result.faultList()) System.out.println("!! " + fault);
        Hocon.ObjectNode space = (Hocon.ObjectNode) result.document().get("space").node();
        List<Dimension> dimensionList = new ArrayList<>();
        for (Hocon.Entry e : space.entryList()) {
            List<Long> values = new ArrayList<>();
            for (Hocon.Node item : ((Hocon.ListNode) e.node()).itemList())
                values.add((Long) ((Hocon.ScalarNode) item).value());
            dimensionList.add(new Dimension(e.key(), values));
        }
        return dimensionList;
    }

    /** RETURN: nothing; every case of the space is printed as a matrix cell. */
    static void space() {
        List<Dimension> dimensionList = readSpace(here().resolve("garage-space.hocon"));
        List<List<Long>> valueList = new ArrayList<>();
        List<String>     headList  = new ArrayList<>();
        for (Dimension d : dimensionList) {
            valueList.add(d.values());
            headList.add(d.name() + " " + PyText.repr(d.values()));
        }
        System.out.println("space: " + String.join("  x  ", headList));
        System.out.println("cell: cars inside / cars refused at the gate ('!!' differs from the model)");
        int mismatchN = 0;
        Map<String, List<String>> rowDb = new LinkedHashMap<>();
        for (List<Object> point : SpaceIterator.product(valueList)) {
            int capacity = ((Long) point.get(0)).intValue();
            int arriving = ((Long) point.get(1)).intValue();
            int leaving  = ((Long) point.get(2)).intValue();
            Counter garage  = new Counter(capacity);
            int     refused = 0;
            for (int i = 0; i < arriving; ++i) if (!garage.arrive()) ++refused;
            for (int i = 0; i < leaving; ++i) garage.leave();
            int admitted = Math.min(arriving, capacity);
            boolean sameF = garage.occupied == admitted - Math.min(leaving, admitted)
                         && refused == arriving - admitted;
            if (!sameF) ++mismatchN;
            rowDb.computeIfAbsent(capacity + "/" + arriving, k -> new ArrayList<>())
                 .add(garage.occupied + "/" + refused + (sameF ? "  " : "!!"));
        }
        for (Long capacity : valueList.get(0)) {
            List<String> leaveList = new ArrayList<>();
            for (Long l : valueList.get(2)) leaveList.add(String.format(Locale.ROOT, "leave %-3d", l));
            System.out.println(("capacity " + capacity + "   " + String.join("  ", leaveList)).stripTrailing());
            for (Long arriving : valueList.get(1)) {
                List<String> cellList = new ArrayList<>();
                for (String c : rowDb.get(capacity + "/" + arriving)) cellList.add(String.format(Locale.ROOT, "%-9s", c));
                System.out.println(("  arrive " + arriving + "   " + String.join("  ", cellList)).stripTrailing());
            }
        }
        say("cases %d, differing from the model ((mismatches: %d))", rowDb.size() * valueList.get(2).size(), mismatchN);
    }

    // _________________________________________________________________________
    // random -- a deterministic stream of arrivals and departures
    //
    /** RETURN: nothing; the summary of 1000 drawn cars, model-checked, is printed. */
    static void randomStream() {
        DeterministicStream stream = new DeterministicStream(4711);
        Counter garage = new Counter(5);
        int model = 0, arriveN = 0, refusedN = 0, leaveN = 0, emptyN = 0, mismatchN = 0;
        int[] histogram = new int[6];
        StringBuilder strip = new StringBuilder();
        for (int i = 0; i < 1000; ++i) {
            if (stream.coin(0.55)) {
                ++arriveN;
                if (!garage.arrive()) ++refusedN;
                model = Math.min(5, model + 1);
                strip.append('+');
            } else {
                ++leaveN;
                if (!garage.leave()) ++emptyN;
                model = Math.max(0, model - 1);
                strip.append('-');
            }
            if (garage.occupied != model) ++mismatchN;
            histogram[garage.occupied] += 1;
        }
        System.out.println("seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves");
        System.out.println("first 60: " + strip.substring(0, 60));
        say("arrivals %d, refused %d; departures %d, from an empty garage %d", arriveN, refusedN, leaveN, emptyN);
        System.out.println("cars inside after each event:");
        for (int n = 0; n < histogram.length; ++n)
            say("    %d  %4d  %s", n, histogram[n], "#".repeat(histogram[n] / 10));
        say("steps differing from the model ((mismatches: %d))", mismatchN);
    }

    // _________________________________________________________________________
    // race -- two gates on drawn timelines
    //
    /** A gate on a timeline: its first tick checks, its second admits. */
    static final class Gate extends Trigger {
        final Counter          garage;
        final boolean          atomicF;
        final Consumer<String> log;
        int     step     = 0;
        boolean sawFreeF = false;

        /** RETURN: Gate named 'name' on 'timeline', at 'garage'. */
        Gate(String name, String timeline, Counter garage, boolean atomicF, Consumer<String> log) {
            super(timeline, name);
            this.garage = garage; this.atomicF = atomicF; this.log = log;
        }

        /** RETURN: nothing; the gate's next step was performed at 'pseudoTime'. */
        @Override public void fire(int pseudoTime) {
            if (step == 0 && atomicF) {
                sawFreeF = garage.arrive();
                log.accept(sawFreeF ? name + " checks+admits" : name + " refuses");
            } else if (step == 0) {
                sawFreeF = garage.free() > 0;
                log.accept(name + " sees " + garage.free() + " free");
            } else if (atomicF) {
                log.accept(sawFreeF ? name + " opens" : name + " stays shut");
            } else if (sawFreeF) {
                garage.occupied += 1;                     // the naive admit
                log.accept(name + " admits");
            } else {
                log.accept(name + " refuses");
            }
            step += 1;
        }
    }

    /** RETURN: List of String[2], every pair of timelines in four ticks in
     *          which each of two gates fires twice, never at the same tick:
     *          gate A's and gate B's. */
    static List<String[]> interleavingList() {
        List<String[]> result = new ArrayList<>();
        List<Integer>  tick   = List.of(0, 1, 2, 3);
        for (List<Object> p : SpaceIterator.product(List.of(tick, tick, tick, tick))) {
            int a1 = (Integer) p.get(0), a2 = (Integer) p.get(1), b1 = (Integer) p.get(2), b2 = (Integer) p.get(3);
            if (a1 < a2 && b1 < b2 && new HashSet<>(p).size() == 4)
                result.add(new String[] { line(a1, a2), line(b1, b2) });
        }
        return result;
    }

    /** RETURN: String, four ticks, '1' at 'x' and 'y', blank elsewhere. */
    static String line(int x, int y) {
        StringBuilder text = new StringBuilder();
        for (int t = 0; t < 4; ++t) text.append(t == x || t == y ? '1' : ' ');
        return text.toString();
    }

    /** RETURN: nothing; every interleaving of two gates at one space was played. */
    static void race(boolean atomicF) {
        System.out.println("one free space, two gates, one car at each; timelines: a digit fires");
        System.out.println("    gate A  gate B  what happens                                    inside");
        int overbookedN = 0;
        for (String[] pair : interleavingList()) {
            Counter      garage    = new Counter(1);
            List<String> eventList = new ArrayList<>();
            List<Gate>   gateList  = List.of(new Gate("A", pair[0], garage, atomicF, eventList::add),
                                             new Gate("B", pair[1], garage, atomicF, eventList::add));
            Async.run(new TriggerDispatcher(gateList)::run);
            boolean overF = garage.occupied > garage.capacity;
            if (overF) ++overbookedN;
            say("%s", String.format(Locale.ROOT, "    \"%s\"  \"%s\"  %-46s  %d %s", pair[0], pair[1],
                                    String.join(", ", eventList), garage.occupied, overF ? "!!" : "  ").stripTrailing());
        }
        say("interleavings overbooking the garage ((overbooked: %d)) of %d", overbookedN, interleavingList().size());
    }

    public static void main(String[] args) {
        Map<String, Runnable> choiceMap = new LinkedHashMap<>();
        choiceMap.put("space",       Garage::space);
        choiceMap.put("random",      Garage::randomStream);
        choiceMap.put("race-naive",  () -> race(false));
        choiceMap.put("race-atomic", () -> race(true));
        new HwutRunner(args, "Demo: a garage's space counter -- a space, a stream and races, generated;", choiceMap).run();
    }
}
