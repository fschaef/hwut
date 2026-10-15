"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE FEATURE FACES -- 'hwut.features.<verb>' <=> 'services/lib/features/
<verb>.py' (the naming law's dotted clause, as 'hwut.labels.*'): acts on
ONE file, 'hwut-root-features.conf', beside 'hwut-root.conf' (spec 23
VERSION 10, exploration R-96). '_common.py' holds what they share.

    init        writes the central file: directory ids, leaves unplaced
    register    adds what is new below a directory; names what disagrees
    tree        prints the tree of features ('--list', '-b', '-e')
    retire      a claim into 'retired', as it was
    move        a directory moved, its 'directory_map' lines following
    key.add     a key on a leaf or an aggregate      (key/add.py)
    key.remove  a key taken off; '--all' everywhere  (key/remove.py)

The engine reads ('feature_registry.py'), judges ('feature_detector.py')
and amends ('feature_registry_edit.py'); a face only asks and prints.
______________________________________________________________________________
"""
