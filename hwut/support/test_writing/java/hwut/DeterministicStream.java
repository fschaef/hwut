/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: A RANDOM STREAM THAT IS THE SAME EVERYWHERE -- the port of
 *          'DeterministicStream' in 'python/deterministic_random.py', seed for
 *          seed, draw for draw.
 *
 *     DeterministicStream s = new DeterministicStream(0x42);
 *     s.nextInt(0, 9);  s.nextFloat();  s.coin(0.5);  s.select(list);
 *     s.selectUnchosen(list, marker);  s.sampleIndices(10, 3);  s.gauss(0, 1);
 *
 * The generator is Park-Miller MINSTD, 'state = 48271 * state mod (2^31 - 1)'
 * -- pure integer arithmetic, here in 'long' (the product needs 47 bits), so
 * every draw equals Python's. 'gauss' alone touches 'log', 'cos' and 'sqrt',
 * which are this platform's: it may differ from Python's in the last bit.
 * _____________________________________________________________________________
 */
package hwut;

import java.util.ArrayList;
import java.util.List;

public final class DeterministicStream {
    private long state;

    /** RETURN: DeterministicStream, seeded 0x42 (Python's default). */
    public DeterministicStream() { this(0x42); }

    /** RETURN: DeterministicStream, seeded with 'seed' -- its low 31 bits. */
    public DeterministicStream(long seed) { state = seed & 0x7FFFFFFFL; }

    /** RETURN: boolean, true with 'probabilityOfTrue', false else. THE FLOOR
     *          (TW-1): 'nextFloat' takes 1000001 values, so any 0 <
     *          probability <= 1/1000001 comes out as exactly 1/1000001. */
    public boolean coin(double probabilityOfTrue) { return nextFloat() < probabilityOfTrue; }

    /** RETURN: T, a uniformly random element of 'candidates' -- the same one
     *          for the same stream state and the same candidates. */
    public <T> T select(List<T> candidates) { return candidates.get(nextInt(0, candidates.size() - 1)); }

    /** RETURN: T, a uniformly random element of the array 'candidates'. */
    @SafeVarargs
    public final <T> T select(T... candidates) { return candidates[nextInt(0, candidates.length - 1)]; }

    /** RETURN: String, one uniformly random character (code point) of 'text',
     *          as Python's 'select' over a str. */
    public String select(String text) {
        int[] code = text.codePoints().toArray();
        return new String(code, nextInt(0, code.length - 1), 1);
    }

    /** RETURN: T, a random element of 'candidates' whose IDENTITY 'marker'
     *          has not seen -- drawn uniformly among those and recorded in
     *          'marker'; where every candidate was seen, 'marker' is reset
     *          and the draw is among all of them. */
    public <T> T selectUnchosen(List<T> candidates, SelectionMarker marker) {
        List<T> unchosen = new ArrayList<>();
        for (T c : candidates) if (!marker.chosen.contains(c)) unchosen.add(c);
        if (unchosen.isEmpty()) {
            marker.reset();
            unchosen = new ArrayList<>(candidates);
        }
        T choice = unchosen.get(nextInt(0, unchosen.size() - 1));
        marker.chosen.add(choice);
        return choice;
    }

    /** RETURN: int, a random integer in [vMin, vMax]; 'vMin' where both are
     *          equal (the stream steps all the same). */
    public int nextInt(int vMin, int vMax) {
        state = (48271L * state) % 2147483647L;
        if (vMin == vMax) return vMin;
        return (int) (vMin + Math.floorMod(state, (long) vMax - (long) vMin + 1L));
    }

    /** RETURN: double, a random value in [0.0, 1.0): one of 1000001 steps. */
    public double nextFloat() { return nextInt(0, 1000000) / 1000001.0; }

    /** RETURN: double, a draw of the normal distribution (mu, sigma) by the
     *          Box-Muller transform, unclipped. */
    public double gauss(double mu, double sigma) {
        return gauss(mu, sigma, Double.NEGATIVE_INFINITY, Double.POSITIVE_INFINITY);
    }

    /** RETURN: double, a draw of the normal distribution (mu, sigma) by the
     *          Box-Muller transform, clipped to [lower, upper]. NOT
     *          BIT-PORTABLE: 'log', 'cos', 'sqrt' are the platform's. */
    public double gauss(double mu, double sigma, double lower, double upper) {
        double u1 = nextFloat() + 1e-9;                         // avoid log(0)
        double u2 = nextFloat();
        double z0 = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
        double result = z0 * sigma + mu;
        if (result < lower) return lower;
        if (result > upper) return upper;
        return result;
    }

    /** RETURN: long, 'gauss(mu, sigma)' rounded to the nearest integer, a
     *          half to the even one (Python's 'round'). */
    public long gaussInt(double mu, double sigma) {
        return (long) Math.rint(gauss(mu, sigma));
    }

    /** RETURN: long, 'gauss(mu, sigma, lower, upper)' rounded as 'gaussInt'. */
    public long gaussInt(double mu, double sigma, double lower, double upper) {
        return (long) Math.rint(gauss(mu, sigma, lower, upper));
    }

    /** RETURN: T, a random element of 'sequence' (the draw 'select' makes). */
    public <T> T choice(List<T> sequence) { return sequence.get(nextInt(0, sequence.size() - 1)); }

    /** RETURN: List of Integer, 'k' distinct indices of range(populationSize)
     *          by Fisher-Yates, in the order drawn;
     *          throws IllegalArgumentException where k > populationSize. */
    public List<Integer> sampleIndices(int populationSize, int k) {
        if (populationSize < k) throw new IllegalArgumentException("population smaller than the sample");
        int[] index = new int[populationSize];
        for (int i = 0; i < populationSize; ++i) index[i] = i;
        List<Integer> result = new ArrayList<>(k);
        for (int i = 0; i < k; ++i) {
            int j = nextInt(i, populationSize - 1);
            int t = index[i]; index[i] = index[j]; index[j] = t;
            result.add(index[i]);
        }
        return result;
    }

    /** RETURN: List of T, 'n' distinct elements of 'population', drawn as
     *          'sampleIndices' draws their indices;
     *          throws IllegalArgumentException where n > its size. */
    public <T> List<T> sample(List<T> population, int n) {
        List<T> result = new ArrayList<>(n);
        for (int i : sampleIndices(population.size(), n)) result.add(population.get(i));
        return result;
    }
}
