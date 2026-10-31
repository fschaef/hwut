/* @hwut {
 *     title      = "DeterministicStream RNG and SelectionMarker spread"
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         gauss      { features = ["java-random"] }
 *         primitives { features = ["java-random"] }
 *         ranges     { features = ["java-random"] }
 *         sample     { features = ["java-random"] }
 *         seed_sweep { features = ["java-random"] }
 *         select     { features = ["java-random"] }
 *         unchosen   { features = ["java-random"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The Java port of 'python/TEST/test-deterministic-random.py', choice
 *          for choice, held against its GOOD files by '.link'. 'gauss' prints
 *          its full-precision blocks inside the Python test's tolerance region
 *          ('##! table numeric={1:1e-12}'): libm's last bits may differ.
 * _____________________________________________________________________________
 */
import hwut.DeterministicStream;
import hwut.HwutRunner;
import hwut.PyText;
import hwut.SelectionMarker;

import java.util.ArrayList;
import java.util.List;

final class TestDeterministicRandom {
    static final int    SEED                   = 0x42;
    static final String TOLERANCE_REGION_BEGIN = "##! table numeric={1:1e-12}";
    static final String REGION_END             = "####";

    /** RETURN: nothing; the section heading is printed. */
    static void banner(String label) {
        System.out.println();
        System.out.println("--- " + label + " ---");
    }

    /** RETURN: nothing; the bare generator: nextInt, nextFloat, coin. */
    static void runPrimitives() {
        banner("next_int(0, 1000000) -- first 20");
        DeterministicStream s = new DeterministicStream(SEED);
        for (int i = 0; i < 20; ++i) System.out.printf("[%02d] %d%n", i, s.nextInt(0, 1000000));

        banner("next_float -- first 10 (full precision)");
        s = new DeterministicStream(SEED);
        for (int i = 0; i < 10; ++i) System.out.printf("[%02d] %s%n", i, PyText.floatRepr(s.nextFloat()));

        banner("coin(0.5) -- 40 draws");
        s = new DeterministicStream(SEED);
        List<String> text = new ArrayList<>();
        for (int i = 0; i < 40; ++i) text.add(s.coin(0.5) ? "T" : "F");
        System.out.println(String.join(" ", text));
    }

    /** RETURN: nothing; nextInt over small and degenerate ranges. */
    static void runRanges() {
        banner("next_int(0, 9) -- 30 draws");
        DeterministicStream s = new DeterministicStream(SEED);
        List<String> text = new ArrayList<>();
        for (int i = 0; i < 30; ++i) text.add(Integer.toString(s.nextInt(0, 9)));
        System.out.println(String.join(" ", text));

        banner("next_int(5, 5) -- degenerate range returns the bound");
        s = new DeterministicStream(SEED);
        text.clear();
        for (int i = 0; i < 5; ++i) text.add(Integer.toString(s.nextInt(5, 5)));
        System.out.println(String.join(" ", text));

        banner("next_int(-3, 3) -- spanning zero");
        s = new DeterministicStream(SEED);
        text.clear();
        for (int i = 0; i < 20; ++i) text.add(String.format("%+d", s.nextInt(-3, 3)));
        System.out.println(String.join(" ", text));
    }

    /** RETURN: nothing; the libm path: gauss, clamped gauss, gaussInt. The two
     *          full-precision blocks stand in a 'table' tolerance region. */
    static void runGauss() {
        banner("gauss(0, 1) -- 10 draws (full precision)");
        DeterministicStream s = new DeterministicStream(SEED);
        System.out.println(TOLERANCE_REGION_BEGIN);
        for (int i = 0; i < 10; ++i) System.out.printf("[%02d] %s%n", i, PyText.floatRepr(s.gauss(0.0, 1.0)));
        System.out.println(REGION_END);

        banner("gauss(0, 1) clamped to [-1, 1]");
        s = new DeterministicStream(SEED);
        System.out.println(TOLERANCE_REGION_BEGIN);
        for (int i = 0; i < 10; ++i) System.out.printf("[%02d] %s%n", i, PyText.floatRepr(s.gauss(0.0, 1.0, -1.0, 1.0)));
        System.out.println(REGION_END);

        banner("gauss_int(100, 15) -- 20 draws");
        s = new DeterministicStream(SEED);
        List<String> text = new ArrayList<>();
        for (int i = 0; i < 20; ++i) text.add(Long.toString(s.gaussInt(100.0, 15.0)));
        System.out.println(String.join(" ", text));
    }

    /** RETURN: nothing; sampleIndices (Fisher-Yates) and sample over a list. */
    static void runSample() {
        banner("sample_indices(10, 10) -- full permutation");
        DeterministicStream s = new DeterministicStream(SEED);
        System.out.println(PyText.repr(s.sampleIndices(10, 10)));

        banner("sample_indices(20, 5) -- partial draw");
        s = new DeterministicStream(SEED);
        System.out.println(PyText.repr(s.sampleIndices(20, 5)));

        banner("choice from a list -- 20 draws");
        s = new DeterministicStream(SEED);
        List<String> pool = List.of("alpha", "beta", "gamma", "delta", "epsilon");
        List<String> text = new ArrayList<>();
        for (int i = 0; i < 20; ++i) text.add(s.choice(pool));
        System.out.println(String.join(" ", text));

        banner("sample(list, 4) -- unique elements");
        s = new DeterministicStream(SEED);
        System.out.println(PyText.repr(s.sample(List.of("A", "B", "C", "D", "E", "F", "G", "H"), 4)));
    }

    /** RETURN: nothing; stateless select: same state + same pool -> same element. */
    static void runSelect() {
        banner("select over a list -- 20 draws");
        DeterministicStream s = new DeterministicStream(SEED);
        List<String> pool = List.of("a", "b", "c", "d");
        List<String> text = new ArrayList<>();
        for (int i = 0; i < 20; ++i) text.add(s.select(pool));
        System.out.println(String.join(" ", text));

        banner("select over a tuple -- 12 draws");
        s = new DeterministicStream(SEED);
        String[] branches = { "p", "q", "r" };
        text.clear();
        for (int i = 0; i < 12; ++i) text.add(s.select(branches));
        System.out.println(String.join(" ", text));
    }

    /** RETURN: nothing; selectUnchosen's spread is identity-keyed, not keyed
     *          by the container: a stable pool, a fresh container each call,
     *          a sub-pool then the full pool, and 'reset'. */
    static void runUnchosen() {
        banner("stable pool -- three full cycles of 4 elements");
        DeterministicStream s = new DeterministicStream(SEED);
        List<String> pool = List.of("a", "b", "c", "d");
        SelectionMarker m = new SelectionMarker();
        List<String> text = new ArrayList<>();
        for (int i = 0; i < 12; ++i) text.add(s.selectUnchosen(pool, m));
        System.out.println(String.join(" ", text));

        banner("FRESH container each call -- identical to the stable pool above");
        s = new DeterministicStream(SEED);
        m = new SelectionMarker();
        text.clear();
        for (int i = 0; i < 12; ++i) {
            List<String> fresh = new ArrayList<>(List.of("a", "b", "c", "d"));   // a new list every call
            text.add(s.selectUnchosen(fresh, m));
        }
        System.out.println(String.join(" ", text));

        banner("sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]");
        s = new DeterministicStream(SEED);
        m = new SelectionMarker();
        List<String> full = List.of("a", "b", "c", "d"), sub = List.of("a", "b");
        String first = s.selectUnchosen(sub, m);
        text.clear();
        for (int i = 0; i < 3; ++i) text.add(s.selectUnchosen(full, m));
        System.out.println("first(from sub): " + first + "  then(from full): " + String.join(" ", text));

        banner("reset() restarts the cycle");
        s = new DeterministicStream(SEED);
        m = new SelectionMarker();
        List<String> before = new ArrayList<>(), after = new ArrayList<>();
        for (int i = 0; i < 4; ++i) before.add(s.selectUnchosen(pool, m));
        m.reset();
        for (int i = 0; i < 4; ++i) after.add(s.selectUnchosen(pool, m));
        System.out.println("before reset: " + String.join(" ", before));
        System.out.println("after  reset: " + String.join(" ", after));
    }

    /** RETURN: nothing; the first nextInt per seed -- pins seed handling. */
    static void runSeedSweep() {
        banner("first next_int(0, 1000000) per seed 0..15");
        for (int seed = 0; seed < 16; ++seed) {
            DeterministicStream s = new DeterministicStream(seed);
            System.out.printf("seed=%2d -> %d%n", seed, s.nextInt(0, 1000000));
        }
    }

    public static void main(String[] args) {
        new HwutRunner(args, "DeterministicStream RNG and SelectionMarker spread")
            .choice("primitives", TestDeterministicRandom::runPrimitives)
            .choice("ranges",     TestDeterministicRandom::runRanges)
            .choice("gauss",      TestDeterministicRandom::runGauss)
            .choice("sample",     TestDeterministicRandom::runSample)
            .choice("select",     TestDeterministicRandom::runSelect)
            .choice("unchosen",   TestDeterministicRandom::runUnchosen)
            .choice("seed_sweep", TestDeterministicRandom::runSeedSweep)
            .run();
    }
}
