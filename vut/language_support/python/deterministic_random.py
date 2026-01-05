import math
from   typeguard import typechecked

class DeterministicStream:
    """
    A platform-independent random number generator using a 
    Linear Congruential Generator (LCG).
    """
    def __init__(self, seed: int = 0x42):
        # Using parameters from glibc/POSIX
        self.state = seed & 0x7FFFFFFF

    @typechecked
    def next_int(self, v_min: int, v_max: int) -> int:
        """Returns a random integer in [v_min, v_max]."""
        self.state = (1103515245 * self.state + 12345) & 0x7FFFFFFF
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

    @typechecked
    def sample(self, population: list, n: int):
        assert len(population) >= n
        return [ 
            population[i] for i in self.sample_indices(len(population), n)
        ]

