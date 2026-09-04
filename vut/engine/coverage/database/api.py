"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE DOOR into 'engine/coverage/database'. The rest of the
         coverage component -- 'affected.py', 'core.py', the outer
         'api.py', and the sibling 'readers/' package -- reaches the
         homogeneous record and its algebra through this module and
         through no other.

    RecordFault, NotMergeable, CountsNotMergeable, MeasureNotMergeable
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
    index_of, Gathered, record_iterable, rebased
                        the other fold -- who executed this line; the
                        walk that turns stored records into that
                        fold's input, and the path rebasing it needs
    BUNDLE_FILE, GatherFault, bundle_of, gathered_index, read_bundle,
    snapshot_db_of, stale_tuple, write_bundle
                        the cross-directory fold, and the delivery
                        bundle
    measure_of, measure_of_tag, name_tuple, NamedPointMeasure
                        the measurements beside the line axis: branch,
                        mc/dc, and named-point registration
    HtmlPresenter, TexPresenter, html_of, tex_of
                        the two presenters written for people, over
                        the same walk

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
from .gather   import (BUNDLE_FILE, GatherFault, bundle_of,
                       gathered_index, read_bundle, snapshot_db_of,
                       stale_tuple, write_bundle)
from .index    import Gathered, index_of, rebased, record_iterable
from .measure  import (NamedPointMeasure, measure_of, measure_of_tag,
                       name_tuple)
from .present  import HtmlPresenter, TexPresenter, html_of, tex_of
from .record   import (CountsNotMergeable, CoverageRecord, FileCoverage,
                       I_Presenter, MeasureNotMergeable, NotMergeable,
                       RecordFault, TextPresenter, decode, encode,
                       format_record, line_n, merge, parse_record,
                       ranges_of, run_set_of_text, run_text_of, seated,
                       subtract, union, walk)

__all__ = ("BUNDLE_FILE", "CountsNotMergeable", "CoverageRecord",
           "FileCoverage", "Gathered", "GatherFault", "HtmlPresenter",
           "I_Presenter", "MeasureNotMergeable", "NamedPointMeasure",
           "NotMergeable", "RecordFault", "TexPresenter",
           "TextPresenter", "bundle_of", "decode", "encode",
           "format_record", "gathered_index", "html_of", "index_of",
           "line_n", "measure_of", "measure_of_tag", "merge",
           "name_tuple", "pack_record", "parse_record", "ranges_of",
           "read_bundle", "rebased", "record_iterable",
           "run_set_of_text", "run_text_of", "seated",
           "snapshot_db_of", "stale_tuple", "subtract", "tex_of",
           "union", "unpack_record", "walk", "write_bundle")
