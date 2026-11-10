"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE FEATURE FACES -- 'hwut.features.<verb>' <=> 'services/lib/features/
<verb>.py' (the naming law's dotted clause, as 'hwut.labels.*'): they act on
the three files beside the 'hwut-root.conf' that begins the features of a
tree (spec 43): 'hwut-feature-forest.csv', 'hwut-feature-doc.dat',
'hwut-feature-external-map.csv'. '_common.py' holds what they share.

    init        writes an empty forest and an empty doc file
    register    names what the files and the links disagree about
    tree        prints the forest ('--list', '-e')
    rename      an id changes, every reference follows
    retire      a claim no longer made: its block retired, out of the forest

The engine reads ('feature_forest', 'feature_doc', 'feature_external',
'feature_view'), judges ('feature_detector') and writes ('feature_act'); a
face only asks and prints. 'hwut.features.move' and 'key.add'/'key.remove'
are gone: no file holds a directory, keys are left out (T-q).
______________________________________________________________________________
"""
