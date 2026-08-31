"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE DOOR into 'engine/procsitter'. Everything outside the
         component reaches it through this module and through no other.

    ProcsitterConfig    WHAT A SUPERVISED CALL IS TOLD: the caps, the
                        environment overlay, the scratch ground
    Procsitter          the supervisor itself
    ProcsitterResult    what it answers: containment, exit code, the
                        telemetry, what the call created and left
    E_Containment       the verdict of the supervision, by name
    Link, chain, tee    the plumbing of a supervised pipeline: a stage
                        feeds the next, and the caller holds the ends
    spawn               ONE supervised call, synchronously, in
                        'subprocess.run''s shape, for a test that runs
                        a command of its own

A CONFIGURATION CONFIGURES A COMPONENT, SO IT STANDS ON THE
COMPONENT'S DOOR. There is no question about it: the type a caller
must build in order to call at all is the first thing the door owes
them. 'ProcsitterConfig' is that type here.

IT HOLDS NOTHING OF ITS OWN -- imports and '__all__'. A door with
logic in it becomes a component, and then there are two procsitters.

SUBSTITUTE AT THE DOOR. A door is a re-export, and a re-export binds
its names ONCE, when this module is imported. 'api.Procsitter' and
'procsitter.Procsitter' are then two names for one class, and
rebinding one does not touch the other. A test that replaces a class
-- a double, a future version, a patch -- must replace it HERE, since
this is what the product reads; patching the module behind the door
leaves the door holding the original, the substitution appears to
succeed, and the code under test runs against the old class.

THE RULE IS EXECUTABLE. 'adm/LAYERING.txt' names this module in a
'DOOR' line and 'adm/import_graph.py --check' enforces it: anything
may import it; nothing outside 'engine/procsitter' may import anything
else beneath the component. The component's own suites are inside the
wall and reach whatever they test directly -- a door is for callers,
and a test of the watchdog is not a caller.
______________________________________________________________________________
"""
from .construction import Link, chain, tee
from .procsitter   import (E_Containment, Procsitter, ProcsitterConfig,
                           ProcsitterResult)
from .spawn        import CSpawned, spawn

__all__ = ("CSpawned", "E_Containment", "Link", "Procsitter",
           "ProcsitterConfig", "ProcsitterResult", "chain", "spawn",
           "tee")
