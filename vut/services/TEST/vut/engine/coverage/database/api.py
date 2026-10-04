"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE DOOR into 'engine/coverage/database'. The rest of the
         coverage component -- 'affected.py', 'core.py', the outer
         'api.py', and the sibling 'readers/' package -- reaches the
         homogeneous record and its algebra through this module and
         through no other.

    RecordFault, NotMergeable, CountsNotMergeable, MeasureNotMergeable,
    MeasureFault
                        the faults a record or a merge can name
    ranges_of, line_n, union, subtract, encode, decode
                        the interval algebra beneath EX/CV
    FileCoverage, CoverageRecord, seated, run_text_of, run_set_of_text
                        the record itself, and its run-id seating
    format_record, parse_record, merge
                        the record's text spelling, and its algebra
                        across runs
    I_Presenter, TextPresenter, walk
                        the ONE traversal, and the storage-form
                        presenter that walks it
    pack_record, unpack_record
                        the binary spelling (D-20)
    GatheredFile, pack_gathered, unpack_gathered, format_gathered,
    parse_gathered, binary_version, measure_db_of
                        the gathered coverage of one source file, record
                        version 3, in both spellings (D-42, D-43)
    id_text, id_number, group_id_start, DIGITS
                        the base-64 identifiers of an output
    index_of, Gathered, record_iterable, rebased
                        the other fold -- who executed this line; the
                        walk that turns stored records into that
                        fold's input, and the path rebasing it needs
    measure_of, measure_of_tag, name_tuple, NamedPointMeasure
                        the measurements beside the line axis: branch,
                        mc/dc, and named-point registration

A CONSUMER OF THE RECORD DOES NOT NEED TO KNOW WHICH FILE DEFINES IT.
That is what a door is for: 'database/record.py' may split, or gain a
sibling, without a single import outside this package moving -- a
rearrangement that WOULD move one is visible as a change to this file.

IT HOLDS NOTHING OF ITS OWN -- imports and '__all__'.

THE RULE IS EXECUTABLE: 'adm/LAYERING.txt' names this module in a
'DOOR' line; 'readers/' and the coverage component's own 'affected.py'
and 'core.py' reach the record through it, never through
'database.record' or a sibling module directly.

THE COMPONENT'S OWN SUITES ARE INSIDE THE WALL and reach whatever they
test directly: a door is for callers, and a test of the interval
algebra is not a caller.
______________________________________________________________________________
"""
from .binary   import pack_record, unpack_record
from .gathered import (GatheredFile, binary_version, format_gathered,
                       measure_db_of, pack_gathered, parse_gathered,
                       unpack_gathered)
from .identifier import (DIGITS, group_id_start, id_number, id_text)
from .index    import Gathered, index_of, rebased, record_iterable
from .measure  import (MeasureFault, NamedPointMeasure, measure_of,
                       measure_of_tag, name_tuple)
from .record   import (CountsNotMergeable, CoverageRecord, FileCoverage,
                       I_Presenter, MeasureNotMergeable, NotMergeable,
                       RecordFault, TextPresenter, decode, encode,
                       format_record, line_n, merge, parse_record,
                       ranges_of, run_set_of_text, run_text_of, seated,
                       subtract, union, walk)

__all__ = ("CountsNotMergeable", "CoverageRecord", "DIGITS",
           "FileCoverage", "GatheredFile", "Gathered",
           "I_Presenter", "MeasureFault", "MeasureNotMergeable",
           "NamedPointMeasure",
           "NotMergeable", "RecordFault",
           "TextPresenter", "decode", "encode", "format_record",
           "binary_version", "format_gathered", "group_id_start",
           "measure_db_of",
           "id_number", "id_text", "index_of", "pack_gathered",
           "parse_gathered", "unpack_gathered",
           "line_n", "measure_of", "measure_of_tag", "merge",
           "name_tuple", "pack_record", "parse_record", "ranges_of",
           "rebased", "record_iterable", "run_set_of_text",
           "run_text_of", "seated", "subtract", "union",
           "unpack_record", "walk")
