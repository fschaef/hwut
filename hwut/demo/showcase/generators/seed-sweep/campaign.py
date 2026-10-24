"""campaign.py -- the seeding schemes of a nightly fuzz campaign.

A campaign runs RUNS independent streams; run i gets the seed 'seed_of(i)'.
Each stream is a hwut DeterministicStream (MINSTD); the first draws decide
the shape of the generated input (which message type, which field to
corrupt, ...).
"""
MODULUS = 2**31 - 1          # MINSTD lives on the seeds 1 .. MODULUS - 1


def seed_consecutive(i):
    """The scheme everybody writes first: run i, seed i."""
    return i


def seed_multiplicative(i):
    """Run i through Knuth's multiplicative hash (2654435761), then into the
    live range. Looks scrambled -- but it is LINEAR in i, and MINSTD is
    linear too."""
    return 1 + (i * 2654435761 + 0x5EED) % (MODULUS - 1)


def seed_splitmix(i):
    """Run i through the splitmix64 finaliser (xor-shift-multiply: NOT
    linear over the integers), then into the live range."""
    z = (i + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    z = z ^ (z >> 31)
    return 1 + z % (MODULUS - 1)
