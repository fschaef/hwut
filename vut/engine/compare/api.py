"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE DOOR into 'engine/compare'. Everything outside the
         component reaches it through this module and through no other.

    Configuration       what a comparison is told: the tolerances, the
                        analogies, the region handlers -- built by the
                        caller, read by the engine
    is_equivalent       the VERDICT: does the subject stand against the
                        nominal. Aborts as soon as 'False' can be
                        stated and consumes no further input, so the
                        caller may terminate the producer
    associate           the PAIRING, for a caller that wants to see
                        which line answered which -- the display of a
                        difference already found
    RegionSyntaxError   the one fault a caller must catch: the input's
                        region framing is broken

    feeder_ui           the interactive feeder's terminal front, for
                        the face that drives a comparison by hand

WHY A DOOR AT ALL. 'compare' is the largest component of the tree and
the one whose insides move most: regions, solvers, edit operations,
readers. What the rest of the tree needs of it is five names, and they
have not changed in a long time. Naming them here separates the two
rates of change -- the inside may be rearranged without a single
import elsewhere moving, and a rearrangement that WOULD move one is
visible as a change to this file, which is the point.

IT HOLDS NOTHING OF ITS OWN. Imports and '__all__', and nothing else:
a door with logic in it becomes a component, and then there are two
compares.

THE RULE IS EXECUTABLE. 'adm/LAYERING.txt' states it at module depth
and 'adm/import_graph.py --check' enforces it: anything may import
'engine/compare/api'; nothing outside 'engine/compare' may import
anything else beneath it. A leak is caught by a suite, not by a
reading.

THE COMPONENT'S OWN SUITES ARE INSIDE THE WALL and reach whatever they
test directly: a door is for callers, and a test of the potpourri
solver is not a caller.
______________________________________________________________________________
"""
from .configuration        import Configuration, ConfigurationDiffDisplayParameters
from .contract.enums       import RegionSyntaxError
from .feeder               import ui as feeder_ui
from .main                 import associate, is_equivalent

__all__ = ("Configuration", "ConfigurationDiffDisplayParameters", "RegionSyntaxError", "associate",
           "feeder_ui", "is_equivalent")
