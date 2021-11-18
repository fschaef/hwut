from   vut.user_interface.difference_display.console.ui      import ConsoleCanvasDiffUI
from   vut.engine.compare.engine.line_association_chunk      import LineAssociationChunk, \
                                                                    LineAssociationList
from   vut.engine.compare.engine.line_association_chunk_list import LineAssociationChunkList
from   vut.external.quex.typed                               import typed

@typed(lina_cnunk_list=LineAssociationChunkList, sort_potpourri_by_subject_line_n_f=bool)
def do(lina_chunk_list, text_offset=0, sort_potpourri_by_subject_line_n_f=False):
    """Displays a comparison of subject and nominal lines clustered in 
    'LineAssociationChunk'-s.
    """

    canvas = ConsoleCanvasDiffUI(lina_chunk_list) 
    canvas.interact()

