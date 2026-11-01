"""
______________________________________________________________________________
TOUCHDOWN DETECTION OF A LANDER -- the unit 'TEST/test-mpl.py' tests.

Three landing legs carry a touchdown sensor each, read every 0.1 s. A leg
INDICATES touchdown when its sensor reads high on two consecutive readings.
Touchdown sensing is ENABLED at 40 m: from then on an indication stops the
descent engine.

    Lander1999        an indication is latched whenever it occurs, also
                      before sensing is enabled -- so a latch set at leg
                      deployment stops the engine the moment sensing is
                      enabled
    LanderCleared     the latches are cleared when sensing is enabled; only
                      an indication after that stops the engine
______________________________________________________________________________
"""

class Lander1999:
    """The touchdown logic as flown: indications latched from the start."""

    def __init__(self):
        """RETURN: None. No leg latched, sensing off, engine on."""
        self.previous = [False, False, False]
        self.latched  = [False, False, False]
        self.sensing  = False
        self.engine   = True

    def enable_sensing(self):
        """RETURN: None. Touchdown sensing on (at 40 m)."""
        self.sensing = True

    def read(self, sensor_list):
        """
        RETURN: None. One reading of the three sensors: a leg high on this
                and the previous reading latches; with sensing on, any
                latched leg stops the engine.
        """
        for leg, high in enumerate(sensor_list):
            if high and self.previous[leg]:
                self.latched[leg] = True
        self.previous = list(sensor_list)
        if self.sensing and any(self.latched):
            self.engine = False


class LanderCleared(Lander1999):
    """The fix: what was latched before sensing is enabled is discarded."""

    def enable_sensing(self):
        """RETURN: None. Sensing on, every earlier latch cleared."""
        self.latched  = [False, False, False]
        self.previous = [False, False, False]
        self.sensing  = True
