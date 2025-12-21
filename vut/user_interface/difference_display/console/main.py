"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE:
______________________________________________________________________________
"""
from   vut.user_interface.difference_display.console.ui_diff  import ConsoleUIUI
from   vut.user_interface.difference_display.console.ui_merge import ConsoleCanvasMergeUI
from   vut.engine.compare.engine.chunk_pair                   import ChunkPair, \
                                                                     LinePairList
from   vut.engine.compare.engine.chunk_pair_list              import ChunkPairList

from   typeguard import typechecked

@typechecked
def diff(lina_chunk_list: ChunkPairList, text_offset=0, sort_potpourri_by_subject_line_n_f: bool=False):
    """Displays a comparison of subject and nominal lines clustered in 
    'ChunkPair'-s.
    """
    canvas = ConsoleUIUI(lina_chunk_list) 
    canvas.interact()

@typechecked
def merge(lina_chunk_list:ChunkPairList, text_offset=0, sort_potpourri_by_subject_line_n_f: bool =False):
    """Displays a comparison of subject and nominal lines clustered in 
    'ChunkPair'-s.
    """
    canvas = ConsoleCanvasMergeUI(lina_chunk_list) 
    canvas.interact()

