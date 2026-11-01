"""therac.py -- MODEL of the Therac-25 race of the East Texas Cancer Center
accidents (Leveson & Turner, IEEE Computer 26(7), 1993), reduced to what the
race needs. Not the original code (PDP-11 assembly); its structure:

    data entry   the operator's keyboard handler. An EDIT of the treatment
                 mode (X-ray -> electron) changes the mode, moves the
                 turntable for the new mode at once, and raises the edit flag.
    setup task   reads the mode, sets the beam current for it, then sets the
                 bending magnets: about 8 s, one step per second. While the
                 magnets are being set, edits are not looked at.
    treat        on 'beam on': if the edit flag is up, the setup is done
                 again; otherwise the beam fires with the current the setup
                 chose and the turntable where the edit left it.

AS_DELIVERED = True models the defect: the magnet routine CLEARS the edit
flag when it finishes, without looking at it -- an edit made during the
magnet setting is forgotten. AS_DELIVERED = False: the routine checks the
flag before it clears it, and a pending edit starts the setup again.

X-ray mode needs a HIGH current (about 100 times the electron current)
with the target and flattener in the beam; electron mode a LOW current
without them. HIGH current with the turntable in the electron position is
the massive overdose.
"""

CURRENT = {"X": "HIGH", "E": "LOW"}
MAGNET_STEPS = 8


class Machine:
    def __init__(self, as_delivered):
        self.as_delivered = as_delivered
        self.mode = "X"                   # what the operator typed first
        self.turntable = "X"              # follows edits at once
        self.current = None               # chosen by the setup task
        self.edit_flag = False
        self.phase = "read"               # setup task: read, magnets, ready
        self.magnets_left = 0
        self.fired = None                 # (current, turntable) once fired
        self.log = []                     # (tick, lane, letter)

    def edit(self, tick, mode):
        self.mode = mode
        self.turntable = mode
        self.edit_flag = True
        self.log.append((tick, "op", "e"))

    def setup_step(self, tick):
        if self.fired:
            return
        if self.phase == "read":
            self.current = CURRENT[self.mode]
            self.edit_flag = False
            self.magnets_left = MAGNET_STEPS
            self.phase = "magnets"
            self.log.append((tick, "setup", "S"))
        elif self.phase == "magnets":
            self.magnets_left -= 1
            if self.magnets_left > 0:
                self.log.append((tick, "setup", "m"))
                return
            if not self.as_delivered and self.edit_flag:
                self.phase = "read"           # an edit came in: start again
                self.log.append((tick, "setup", "!"))
                return
            self.edit_flag = False            # as delivered: cleared, unread
            self.phase = "ready"
            self.log.append((tick, "setup", "R"))

    def beam_on(self, tick):
        if self.fired:
            return
        if self.phase != "ready":
            self.log.append((tick, "op", "b"))         # pressed, not ready
            return
        if self.edit_flag:
            self.phase = "read"
            self.log.append((tick, "op", "?"))         # treat sees the edit
            return
        self.fired = (self.current, self.turntable)
        self.log.append((tick, "op", "F"))
