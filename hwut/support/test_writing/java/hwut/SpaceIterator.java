/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: EVERY COMBINATION OF A PARAMETER BASIS -- the port of
 *          'python/space_iterator.py'.
 *
 *     List<List<?>> basis = List.of(List.of(0, 2, 4), List.of("otto", "heinz"), List.of(1, 2));
 *     for (List<Object> point : SpaceIterator.product(basis)) { ... }
 *
 *     yields  [0, otto, 1], [0, otto, 2], [0, heinz, 1], ... -- the RIGHTMOST
 *     dimension changes fastest (itertools.product's order).
 *
 * An EMPTY basis yields exactly one point, the empty one; a basis with an
 * EMPTY dimension yields nothing.
 * _____________________________________________________________________________
 */
package hwut;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.NoSuchElementException;

public final class SpaceIterator implements Iterator<List<Object>> {
    private final List<List<Object>> pool = new ArrayList<>();
    private final int[]              index;
    private boolean                  doneF;

    /** RETURN: SpaceIterator, before the first point of the cartesian
     *          product of 'basis' -- each dimension copied as it stands now. */
    public SpaceIterator(List<? extends Iterable<?>> basis) {
        for (Iterable<?> dimension : basis) {
            List<Object> values = new ArrayList<>();
            for (Object value : dimension) values.add(value);
            pool.add(values);
        }
        index = new int[pool.size()];
        for (List<Object> values : pool) if (values.isEmpty()) doneF = true;
    }

    /** RETURN: Iterable of List of Object, the points of the cartesian
     *          product of 'basis', the rightmost dimension fastest; each
     *          point an unmodifiable list, one value per dimension. */
    public static Iterable<List<Object>> product(List<? extends Iterable<?>> basis) {
        return () -> new SpaceIterator(basis);
    }

    /** RETURN: boolean, true where a point remains. */
    @Override public boolean hasNext() { return !doneF; }

    /** RETURN: List of Object, the next point, if one remains;
     *          throws NoSuchElementException, else. */
    @Override public List<Object> next() {
        if (doneF) throw new NoSuchElementException();
        List<Object> point = new ArrayList<>(index.length);
        for (int i = 0; i < index.length; ++i) point.add(pool.get(i).get(index[i]));
        int i = index.length - 1;
        while (i >= 0) {
            if (++index[i] < pool.get(i).size()) break;
            index[i] = 0;
            --i;
        }
        if (i < 0) doneF = true;
        return Collections.unmodifiableList(point);
    }
}
