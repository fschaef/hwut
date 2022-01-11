"""SPDX-License: MIT; (C) Frank-Rene Schäfer; Project: VUT
_______________________________________________________________________________
PURPOSE: Prepare LineAssociationDecorated objects for display

Filtering the set of displayed lines helps the user to focus on a specific 
subject. For example, displaying only lines which are concerned with analogy
errors facilitates to spot the reason for mismatches. Displaying only lines
with errors helps to spot erroneous outputs.

The functions of this module receive a sequence of 'LineAssociationChunk'-s and
provide a sub-set of the 'LineAssociation'-s which are inside them. The return
value of these functions is then used for the line-by-line display.
_______________________________________________________________________________
"""
from   vut.engine.compare.engine.line_association        import LineAssociation
from   vut.engine.compare.engine.line_association_chunk  import LineAssociationChunk, \
                                                                LineAssociationList
from   vut.engine.compare.engine.core                    import E_PotpourriBorder
from   vut.engine.compare.engine.input_chunk             import E_Chunk
from   vut.system.helper                                 import Interval
from   vut.external.quex.typed   import typed
from   vut.external.quex.tools   import flatten

from   collections import defaultdict
from   enum import Enum, auto


class E_DiffMode(Enum):
    PLAIN                = auto()
    ERRORS               = auto()
    ERRORS_AND_TOLERATED = auto()
    ANALOGIES            = auto()

class LineAssociationDecorated(LineAssociation):
    def __init__(self, chunk_index, lina_index, lina):
        self.chunk_index   = chunk_index
        self.lina_index    = lina_index
        LineAssociation.__init__(self, lina.subject, lina.nominal, lina.edit_list, lina.border)
        self.subject_end_f = False
        self.nominal_end_f = False
        self.filler_f      = False

    @staticmethod
    def filler():
        result = LineAssociationDecorated(0, 0, LineAssociation(None, None))
        result.filler_f = True
        return result

def select(lina_chunk_list, mode, analogy_db, verbosity_level):
    if mode == E_DiffMode.PLAIN:
        return plain(lina_chunk_list)
    elif mode == E_DiffMode.ANALOGIES:
        return analogy_errors(lina_chunk_list, analogy_db, 
                              verbosity_level=verbosity_level)
    elif mode == E_DiffMode.ERRORS:
        return errors(lina_chunk_list, 
                      verbosity_level=verbosity_level)

    elif mode == E_DiffMode.ERRORS_AND_TOLERATED:
        return errors_and_tolerated(lina_chunk_list, 
                                    verbosity_level=verbosity_level)

def plain(lina_chunk_list, verbosity_level=2):
    """RETURNS: sequence of all 'LineAssociation' objects in the 
                given 'LineAssociationChunk' list.
    """

    return _display_brief_core(lina_chunk_list.plain(), 
                               verbosity_level)

def errors(lina_chunk_list, verbosity_level=2):
    """RETURNS: list of 'LineAssociationDecorated' objects

    Extracts 'LineAssociation'-s from the given list of chunks and provides
    a list containing only errors. 
    """
    return _display_brief_core(lina_chunk_list.errors(), 
                               verbosity_level)
            
def errors_and_tolerated(lina_chunk_list, verbosity_level=2):
    """RETURNS: list of 'LineAssociationDecorated' objects

    Extracts 'LineAssociation'-s from the given list of chunks and provides
    a list containing only errors. 
    """
    return _display_brief_core(lina_chunk_list.errors_and_tolerated(), 
                               verbosity_level)

@typed(errors_f=bool, definitions_f=bool)
def analogy_errors(lina_chunk_list, 
                   analogy_db,
                   errors_f=True, 
                   definitions_f=True, 
                   verbosity_level=3):

    error_info_list = lina_chunk_list.analogy_errors(analogy_db,
                                                     errors_f, 
                                                     definitions_f, 
                                                     verbosity_level)
    return _display_brief_core(error_info_list, verbosity_level)

def get_Interval_list(lina_list):
    """'chunk_lina_list': list of (chunk, line indices)

    This object is the output of the aforementioned filter functions.
        
    RETURNS: list of 'Interval' objects buildt from line indices in 
             'chunk_lina_list'.
    """
    return list(Interval.iterable_from_integer_list(flatten(
                lina.indices_plain() for lina in lina_list)))

def plug_end(lina_list):
    """ADAPTS: lina_list, i.e. prepares the 'end of stream' for 
               subject and nominal.

    In order to mark the end of file/stream in the list of 'LineAssociation'-s
    this function searches for the last entry that contains a valid subject or
    a valid nominal. The subsequent entry to that, then contains an appropriate
    marker. If the last valid entry appears in the last 'LineAssociation' of the
    list, then a new 'LineAssociation' is appended.
    """

    if not lina_list:
        return

    # Iterate over 'lina_list' from the rear and mark with 'end_subject_lina_i'
    # and 'end_nominal_lina_i' the 'LineAssociation' which contains the first
    # line after end of stream.
    lina_n             = len(lina_list) 
    end_subject_lina_i = None
    end_nominal_lina_i = None
    for lina_i, lina in reversed(list(enumerate(lina_list))):
        if lina.border == E_PotpourriBorder.END: 
            end_subject_lina_i = lina_i + 1
            end_nominal_lina_i = lina_i + 1
            break
        elif lina.filler_f: 
            end_subject_lina_i = lina_i + 1
            end_nominal_lina_i = lina_i + 1
            break
        else:
            if lina.subject is not None and end_subject_lina_i is None:
                end_subject_lina_i = lina_i + 1
            if lina.nominal is not None and end_nominal_lina_i is None:
                end_nominal_lina_i = lina_i + 1
        if end_subject_lina_i is not None and end_nominal_lina_i is not None:
           break

    # One of subject/nominal must have a valid entry in the last 
    # 'LineAssociation'. Else, there would be invalid 'LineAssociation'-s.
    assert end_subject_lina_i == lina_n or end_nominal_lina_i == lina_n
    extra = LineAssociationDecorated(-1, -1, LineAssociation.empty())
    lina_list.append(extra)

    lina_list[end_subject_lina_i].subject_end_f = True 
    lina_list[end_nominal_lina_i].nominal_end_f = True 

def _display_brief_core(error_info_list, verbosity_level):
    """error_info_list: list of (LineAssociationChunk, set of line indices)

    RETURNS: LineAssociationList
    """
    result = LineAssociationList()
    for chunk, index_set in error_info_list:
        if chunk.type() == E_Chunk.LINE_SEQUENCE: buffer_verbosity_level = verbosity_level
        else:                                     buffer_verbosity_level = 0
        result.extend(_prepare_display_brief(chunk, 
                                             sorted(index_set), 
                                             verbosity_level))

    return result

def _prepare_display_brief(lina_list, lina_index_list, verbosity_level=3):
    """RETURNS: list of LineAssociationDecorated

    to display errors. That is, lines which are equivalent are omitted from
    display, except for those neighbouring error lines.
    """
    def _some_border(prev_lina_i, lina_i, lina_list):
        delta = lina_i - prev_lina_i
        if delta > 4:
            yield LineAssociationDecorated(0, 0, lina_list[prev_lina_i+1])
            yield LineAssociationDecorated.filler()
            yield LineAssociationDecorated(0, 0, lina_list[lina_i - 1])
        elif delta == 4:
            yield LineAssociationDecorated(0, 0, lina_list[prev_lina_i+1])
            yield LineAssociationDecorated(0, 0, lina_list[lina_i - 2])
            yield LineAssociationDecorated(0, 0, lina_list[lina_i - 1])
        elif delta == 3:
            yield LineAssociationDecorated(0, 0, lina_list[lina_i - 2])
            yield LineAssociationDecorated(0, 0, lina_list[lina_i - 1])
        elif delta == 2:
            yield LineAssociationDecorated(0, 0, lina_list[lina_i - 1])

        if lina_i != len(lina_list):
            yield LineAssociationDecorated(0, 0, lina_list[lina_i])

    def _no_border(prev_lina_i, lina_i, lina_list):
        delta = lina_i - prev_lina_i
        if delta > 2:
            yield LineAssociationDecorated.filler()
        elif delta == 2:
            yield LineAssociationDecorated(0, 0, lina_list[lina_i - 1])
        if lina_i != len(lina_list):
            yield LineAssociationDecorated(0, 0, lina_list[lina_i])

    def _no_filler(prev_lina_i, lina_i, lina_list):
        if lina_i != len(lina_list):
            yield LineAssociationDecorated(0, 0, lina_list[lina_i])

    if   verbosity_level == 0: _handle = _no_filler
    elif verbosity_level == 1: _handle = _no_border
    elif verbosity_level == 2: _handle = _some_border
    else:                      assert verbosity_level in (0, 1, 2)

    prev_lina_i = -1
    if not lina_index_list:
        return

    lina_index_list.sort()
    prev_lina_i = -1
    for lina_i in lina_index_list:
        yield from _handle(prev_lina_i, lina_i, lina_list)
        prev_lina_i = lina_i

    yield from _handle(prev_lina_i, len(lina_list), lina_list)

