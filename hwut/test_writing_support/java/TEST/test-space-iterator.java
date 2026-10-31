/* @hwut {
 *     title      = "space_iterator: every combination of a parameter basis"
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         product { features = ["java-space"] }
 *         edges   { features = ["java-space"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The Java port of 'python/TEST/test-space-iterator.py', held against
 *          its GOOD files by '.link'.
 * _____________________________________________________________________________
 */
import hwut.HwutRunner;
import hwut.SpaceIterator;

import java.util.ArrayList;
import java.util.List;

final class TestSpaceIterator {
    /** RETURN: nothing; the section heading is printed. */
    static void banner(String label) {
        System.out.println();
        System.out.println("--- " + label + " ---");
    }

    /** RETURN: nothing; every point of 'basis', one per line, then the count. */
    static void points(List<? extends List<?>> basis) {
        int n = 0;
        for (List<Object> point : SpaceIterator.product(basis)) {
            List<String> text = new ArrayList<>();
            for (Object value : point) text.add(String.valueOf(value));
            System.out.println("  (" + String.join(", ", text) + ")");
            n += 1;
        }
        System.out.println("  " + n + " point(s)");
    }

    /** RETURN: nothing; three dimensions, the rightmost changes fastest. */
    static void runProduct() {
        banner("[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points");
        points(List.of(List.of(0, 2, 4), List.of("otto", "heinz"), List.of(1, 2)));
    }

    /** RETURN: nothing; the empty basis, an empty dimension, one dimension. */
    static void runEdges() {
        banner("an EMPTY basis -- one point, the empty one");
        points(List.of());
        banner("a basis with an EMPTY dimension -- nothing");
        points(List.of(List.of(1, 2), List.of(), List.of(3)));
        banner("ONE dimension -- its values one by one");
        points(List.of(List.of("a", "b", "c")));
    }

    public static void main(String[] args) {
        new HwutRunner(args, "space_iterator: every combination of a parameter basis")
            .choice("product", TestSpaceIterator::runProduct)
            .choice("edges",   TestSpaceIterator::runEdges)
            .run();
    }
}
