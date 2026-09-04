import math
# from   typeguard import typechecked -- too costly in most applications


class SelectionMarker:
    """Remembers which candidate OBJECTS have been chosen at one selection site.

    Keyed by object identity (id), never equality: two structurally equal
    candidates are still distinct alternatives. The marker is caller-owned, so
    'prefer unchosen' is reproducible regardless of container address reuse --
    the marker, not id(container), is the memory. One marker per logical site
    (e.g. one per grammar ALT node) gives coverage-style spread across a walk.

    Safe to key on id() because the caller holds the candidate objects alive
    for the marker's lifetime (e.g. grammar branches are long-lived nodes).
    """
    def __init__(self):
        """RETURN: None. Starts with an empty chosen-set."""
        self.chosen = set()      # set of id(candidate)

    def reset(self):
        """RETURN: None. Forgets all chosen candidates; the next cycle restarts."""
        self.chosen.clear()


class DeterministicStream:
    """
    A platform-independent random number generator using a
    Linear Congruential Generator (LCG).
    """
    def __init__(self, seed: int = 0x42):
        # Using parameters from glibc/POSIX
        self.state = seed & 0x7FFFFFFF

    def coin(self, probability_of_true) -> bool:
        return bool(self.next_float() < probability_of_true)

    # @typechecked -- too costly
    def select(self, candidates: list|tuple|str):
        """RETURN: object, a uniformly random candidate from 'candidates'.

        Stateless: the same stream state and the same 'candidates' always yield
        the same element. For spread that prefers not-yet-chosen candidates, use
        'select_unchosen' with a caller-owned SelectionMarker.
        """
        return candidates[self.next_int(0, len(candidates) - 1)]

    # @typechecked -- too costly
    def select_unchosen(self, candidates: list|tuple|str, marker: "SelectionMarker"):
        """RETURN: object, a random candidate whose identity 'marker' has not seen.

        Draws uniformly among the candidates absent from 'marker' (by object
        identity), records the choice, and returns it. When every candidate has
        been seen, resets 'marker' and draws from the full pool.

        Identity-keyed, so the result is independent of pool composition: a
        candidate counts as 'the same' across differing sub-pools of one site
        (e.g. a branch seen via a 'recursive' sub-list is remembered when the
        full branch list is offered next). Determinism does not depend on the
        container's address -- only on the stream state and the marker.
        """
        unchosen = [c for c in candidates if id(c) not in marker.chosen]
        if not unchosen:
            marker.reset()
            unchosen = list(candidates)
        choice = unchosen[self.next_int(0, len(unchosen) - 1)]
        marker.chosen.add(id(choice))
        return choice

    # @typechecked -- too costly
    def next_int(self, v_min: int, v_max: int) -> int:
        """Returns a random integer in [v_min, v_max]."""
        # Park-Miller "Minimal Standard" (MINSTD) generator.
        # Uses Mersenne prime 2^31 - 1 to avoid low-bit correlations found in power-of-2 LCGs.
        # Multiplier 48271 is the modern standard (improved over original 16807).
        self.state = (48271 * self.state) % 2147483647
        if v_min == v_max:
            return v_min
        return v_min + (self.state % (v_max - v_min + 1))

    def next_float(self) -> float:
        """Returns a random float in [0.0, 1.0)."""
        return self.next_int(0, 1000000) / 1000001.0

    def gauss(self, mu: float, sigma: float, lower: float=-math.inf, upper: float=math.inf) -> float:
        """
        Box-Muller transform to generate Gaussian distribution
        independently of platform libraries.
        """
        u1 = self.next_float() + 1e-9 # Avoid log(0)
        u2 = self.next_float()
        z0 = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

        result = z0 * sigma + mu
        if   result < lower: return lower
        elif result > upper: return upper
        else:                return result

    def gauss_int(self, mu: float, sigma: float, lower: int=-math.inf, upper: int=math.inf) -> float:
        return int(round(self.gauss(mu, sigma, float(lower), float(upper))))

    def choice(self, seq: list):
        """Pick a random element from a list."""
        return seq[self.next_int(0, len(seq) - 1)]

    def sample_indices(self, population_size: int, k: int) -> list[int]:
        """Returns k unique indices from range(population_size)."""
        assert population_size >= k
        indices = list(range(population_size))
        result = []
        for i in range(k):
            # Swap current index with a random remaining one (Fisher-Yates)
            idx = self.next_int(i, population_size - 1)
            indices[i], indices[idx] = indices[idx], indices[i]
            result.append(indices[i])
        return result

    # @typechecked -- to costly
    def sample(self, population: list, n: int):
        assert len(population) >= n
        return [
            population[i] for i in self.sample_indices(len(population), n)
        ]

