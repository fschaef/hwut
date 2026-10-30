"""
______________________________________________________________________________
A DNS FORWARDER'S TIMING, modelled small -- the unit 'TEST/test-leap.py'
tests.

The forwarder measures each upstream query's round-trip time as 'end -
start' and draws a back-off from it: 'int63n(rtt_ms)', a random integer in
[0, rtt_ms) -- as Go's 'rand.Int63n', which PANICS when given a value <= 0.

Two clocks the forwarder may read:

    wall_clock(t)   UTC as the kernel keeps it across a leap second: the
                    inserted second 23:59:60 is shown as a second
                    23:59:59, so from the leap on the clock reads one
                    second behind
    monotonic(t)    seconds since boot: never steps
______________________________________________________________________________
"""

class Panic(Exception):
    """What Go's 'rand.Int63n' does with an argument <= 0."""


def wall_clock(t, leap_t):
    """
    RETURN: float, the wall-clock reading at true time 't' (seconds), with
            a leap second inserted at true time 'leap_t': one second less
            from 'leap_t' on.
    """
    return t if t < leap_t else t - 1.0


def monotonic(t, leap_t):
    """RETURN: float, the monotonic clock at true time 't': 't' itself."""
    return t


def int63n(n, seed):
    """
    RETURN: int, a pseudo-random integer in [0, n), from 'seed'.
    Raises Panic where 'n' <= 0: 'invalid argument to Int63n'.
    """
    if n <= 0:
        raise Panic("invalid argument to Int63n")
    return (seed * 2654435761) % n


def query(start_t, end_t, leap_t, clock):
    """
    RETURN: [0] float, the round-trip time in ms the forwarder measures
                with 'clock' for a query from 'start_t' to 'end_t';
            [1] int, the back-off it draws from it.
    Raises Panic where the measured time is not positive.
    """
    rtt_ms = (clock(end_t, leap_t) - clock(start_t, leap_t)) * 1000.0
    return rtt_ms, int63n(int(round(rtt_ms)), int(start_t * 10))
