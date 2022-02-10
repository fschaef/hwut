"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE:
______________________________________________________________________________
"""
from   vut.user_interface.difference_display.console.ui_diff  import ConsoleCanvasDiffUI
from   vut.user_interface.difference_display.console.ui_merge import ConsoleCanvasMergeUI
from   vut.engine.compare.engine.chunk_pair                   import ChunkPair, \
                                                                     LinePairList
from   vut.engine.compare.engine.chunk_pair_list              import ChunkPairList
from   vut.external.quex.typed                                import typed

@typed(lina_cnunk_list=ChunkPairList, sort_potpourri_by_subject_line_n_f=bool)
def diff(lina_chunk_list, text_offset=0, sort_potpourri_by_subject_line_n_f=False):
    """Displays a comparison of subject and nominal lines clustered in 
    'ChunkPair'-s.
    """
    canvas = ConsoleCanvasDiffUI(lina_chunk_list) 
    canvas.interact()

@typed(lina_cnunk_list=ChunkPairList, sort_potpourri_by_subject_line_n_f=bool)
def merge(lina_chunk_list, text_offset=0, sort_potpourri_by_subject_line_n_f=False):
    """Displays a comparison of subject and nominal lines clustered in 
    'ChunkPair'-s.
    """
    canvas = ConsoleCanvasMergeUI(lina_chunk_list) 
    canvas.interact()

