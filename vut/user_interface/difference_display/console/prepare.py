"""SPDX-License: MIT; (C) Frank-Rene Schäfer; Project: VUT
_______________________________________________________________________________
PURPOSE: Prepare LinePairDecorated objects for display

Filtering the set of displayed lines helps the user to focus on a specific 
subject. For example, displaying only lines which are concerned with analogy
errors facilitates to spot the reason for mismatches. Displaying only lines
with errors helps to spot erroneous outputs.

The functions of this module receive a sequence of 'ChunkPair'-s and
provide a sub-set of the 'LinePair'-s which are inside them. The return
value of these functions is then used for the line-by-line display.
_______________________________________________________________________________
"""
from   vut.engine.compare.engine.line_pair        import LinePair
from   vut.engine.compare.engine.chunk_pair  import ChunkPair, \
                                                                LinePairList
from   vut.engine.compare.engine.core                    import E_PotpourriBorder
from   vut.engine.compare.engine.input_chunk             import E_Chunk
from   vut.system.helper                                 import Interval
from   vut.external.quex.typed   import typed
from   vut.external.quex.tools   import flatten

from   collections import defaultdict
from   enum import Enum, auto


class E_LinePairSelectionMode(Enum):
    PLAIN                      = auto()
    ERRORS                     = auto()
    ERRORS_AND_TOLERATED       = auto()
    ANALOGIES                  = auto()
    ANALOGIES_ERRORS_ONLY      = auto()
    ANALOGIES_DEFINITIONS_ONLY = auto()

class LinePairDecorated(LinePair):
    def __init__(self, chunk_index, lp_index, lp):
        self.chunk_index   = chunk_index
        self.lp_index    = lp_index
        LinePair.__init__(self, lp.subject, lp.nominal, lp.edit_list, lp.border)
        self.subject_end_f = False
        self.nominal_end_f = False
        self.filler_f      = False

    @staticmethod
    def filler():
        result = LinePairDecorated(0, 0, LinePair(None, None))
        result.filler_f = True
        return result

def plain(lp_chunk_list, verbosity_level=2):
    """RETURNS: sequence of all 'LinePair' objects in the 
                given 'ChunkPair' list.
    """

    return _display_brief_core(lp_chunk_list.plain(), 
                               verbosity_level)

def errors(lp_chunk_list, verbosity_level=2):
    """RETURNS: list of 'LinePairDecorated' objects

    Extracts 'LinePair'-s from the given list of chunks and provides
    a list containing only errors. 
    """
    return _display_brief_core(lp_chunk_list.errors(), 
                               verbosity_level)
            
def errors_and_tolerated(lp_chunk_list, verbosity_level=2):
    """RETURNS: list of 'LinePairDecorated' objects

    Extracts 'LinePair'-s from the given list of chunks and provides
    a list containing only errors. 
    """
    return _display_brief_core(lp_chunk_list.errors_and_tolerated(), 
                               verbosity_level)

def analogy_errors_only(lp_chunk_list, verbosity_level):
    return _analogy_errors(lp_chunk_list, errors_f=True, definitions_f=False, verbosity_level=verbosity_level)

def analogy_errors_and_definitions(lp_chunk_list, verbosity_level):
    return _analogy_errors(lp_chunk_list, errors_f=True, definitions_f=True, verbosity_level=verbosity_level)

def analogy_definitions_only(lp_chunk_list, verbosity_level):
    return _analogy_errors(lp_chunk_list, errors_f=False, definitions_f=True, verbosity_level=verbosity_level)

@typed(errors_f=bool, definitions_f=bool)
def _analogy_errors(lp_chunk_list, 
                    errors_f=True, 
                    definitions_f=True, 
                    verbosity_level=3):

    error_info_list = lp_chunk_list.analogy_errors(errors_f, 
                                                   definitions_f, 
                                                   verbosity_level)
    return _display_brief_core(error_info_list, verbosity_level)

#______________________________________________________________________________
# selection_mode_db: 
#  
#      E_LinePairSelectionMode --> function
#
# with
# 
#      function(line pair chunk list, mode, verbosity_level)
#      -> list of LinePairDecorated
#
# verbosity_level: level of verbosity in diff display
#           0  - only error line associations are displayed
#           1  - add '...' line associtions to show borders
#           2  - add one good line and '...' around error lines
#
# The 'verbosity_level' argument is only used for analogy errors and 
# 'error' display
#______________________________________________________________________________
__selection_mode_db = {
    E_LinePairSelectionMode.PLAIN:                      plain,
    E_LinePairSelectionMode.ANALOGIES:                  analogy_errors_and_definitions,
    E_LinePairSelectionMode.ANALOGIES_ERRORS_ONLY:      analogy_errors_only,
    E_LinePairSelectionMode.ANALOGIES_DEFINITIONS_ONLY: analogy_definitions_only,
    E_LinePairSelectionMode.ERRORS:                     errors, 
    E_LinePairSelectionMode.ERRORS_AND_TOLERATED:       errors_and_tolerated,
}
def select(selection_mode, lp_chunk_list, verbosity_level):
    return __selection_mode_db[selection_mode](lp_chunk_list, verbosity_level)

def get_Interval_list(lp_list):
    """'chunk_lp_list': list of (chunk, line indices)

    This object is the output of the aforementioned filter functions.
        
    RETURNS: list of 'Interval' objects buildt from line indices in 
             'chunk_lp_list'.
    """
    return list(Interval.iterable_from_integer_list(flatten(
                lp.indices_plain() for lp in lp_list)))

def plug_end(lp_list):
    """ADAPTS: lp_list, i.e. prepares the 'end of stream' for 
               subject and nominal.

    In order to mark the end of file/stream in the list of 'LinePair'-s
    this function searches for the last entry that contains a valid subject or
    a valid nominal. The subsequent entry to that, then contains an appropriate
    marker. If the last valid entry appears in the last 'LinePair' of the
    list, then a new 'LinePair' is appended.
    """

    if not lp_list:
        return

    # Iterate over 'lp_list' from the rear and mark with 'end_subject_lp_i'
    # and 'end_nominal_lp_i' the 'LinePair' which contains the first
    # line after end of stream.
    lp_n             = len(lp_list) 
    end_subject_lp_i = None
    end_nominal_lp_i = None
    for lp_i, lp in reversed(list(enumerate(lp_list))):
        if lp.border == E_PotpourriBorder.END: 
            end_subject_lp_i = lp_i + 1
            end_nominal_lp_i = lp_i + 1
            break
        elif lp.filler_f: 
            end_subject_lp_i = lp_i + 1
            end_nominal_lp_i = lp_i + 1
            break
        else:
            if lp.subject is not None and end_subject_lp_i is None:
                end_subject_lp_i = lp_i + 1
            if lp.nominal is not None and end_nominal_lp_i is None:
                end_nominal_lp_i = lp_i + 1
        if end_subject_lp_i is not None and end_nominal_lp_i is not None:
           break

    # One of subject/nominal must have a valid entry in the last 
    # 'LinePair'. Else, there would be invalid 'LinePair'-s.
    assert end_subject_lp_i == lp_n or end_nominal_lp_i == lp_n
    extra = LinePairDecorated(-1, -1, LinePair.empty())
    lp_list.append(extra)

    lp_list[end_subject_lp_i].subject_end_f = True 
    lp_list[end_nominal_lp_i].nominal_end_f = True 

def _display_brief_core(error_info_list, verbosity_level):
    """error_info_list: list of (ChunkPair, set of line indices)

    RETURNS: LinePairList
    """
    result = LinePairList()
    for chunk, index_set in error_info_list:
        if chunk.same_type() == E_Chunk.LINE_SEQUENCE: chunk_verbosity_level = verbosity_level
        else:                                          chunk_verbosity_level = 0
        result.extend(_prepare_display_brief(chunk, 
                                             sorted(index_set), 
                                             chunk_verbosity_level))

    return result

def _prepare_display_brief(lp_list, lp_index_list, verbosity_level=3):
    """RETURNS: list of LinePairDecorated

    to display errors. That is, lines which are equivalent are omitted from
    display, except for those neighbouring error lines.
    """
    def _some_border(prev_lp_i, lp_i, lp_list):
        delta = lp_i - prev_lp_i
        if delta > 4:
            yield LinePairDecorated(0, 0, lp_list[prev_lp_i+1])
            yield LinePairDecorated.filler()
            yield LinePairDecorated(0, 0, lp_list[lp_i - 1])
        elif delta == 4:
            yield LinePairDecorated(0, 0, lp_list[prev_lp_i+1])
            yield LinePairDecorated(0, 0, lp_list[lp_i - 2])
            yield LinePairDecorated(0, 0, lp_list[lp_i - 1])
        elif delta == 3:
            yield LinePairDecorated(0, 0, lp_list[lp_i - 2])
            yield LinePairDecorated(0, 0, lp_list[lp_i - 1])
        elif delta == 2:
            yield LinePairDecorated(0, 0, lp_list[lp_i - 1])

        if lp_i != len(lp_list):
            yield LinePairDecorated(0, 0, lp_list[lp_i])

    def _no_border(prev_lp_i, lp_i, lp_list):
        delta = lp_i - prev_lp_i
        if delta > 2:
            yield LinePairDecorated.filler()
        elif delta == 2:
            yield LinePairDecorated(0, 0, lp_list[lp_i - 1])
        if lp_i != len(lp_list):
            yield LinePairDecorated(0, 0, lp_list[lp_i])

    def _no_filler(prev_lp_i, lp_i, lp_list):
        if lp_i != len(lp_list):
            yield LinePairDecorated(0, 0, lp_list[lp_i])

    if   verbosity_level == 0: _handle = _no_filler
    elif verbosity_level == 1: _handle = _no_border
    elif verbosity_level == 2: _handle = _some_border
    else:                      assert verbosity_level in (0, 1, 2)

    prev_lp_i = -1
    if not lp_index_list:
        return

    lp_index_list.sort()
    prev_lp_i = -1
    for lp_i in lp_index_list:
        yield from _handle(prev_lp_i, lp_i, lp_list)
        prev_lp_i = lp_i

    yield from _handle(prev_lp_i, len(lp_list), lp_list)

