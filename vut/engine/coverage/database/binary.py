"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE BINARY SPELLING of the coverage record -- the ONE form on
         disk (RATIONALE D-20). The text spelling ('record.py') is the
         presentation, made on demand by 'hwut.run.cov convert'.

DESCRIPTION
       ONE RECORD, TWO CODECS. 'pack_record' and 'unpack_record' here,
       'format_record' and 'parse_record' in 'record.py': both yield
       the same 'CoverageRecord', and the test proves it on every
       witnessed artifact and on a record of a hundred thousand ranges.

       THE NUMBER STREAM. Every delta-coded sequence -- ranges, counts,
       points -- is a stream of unsigned bytes with one ESCAPE:

           0x00..0xFE   the number itself
           0xFF         the number follows as a little-endian uint32

       Measured on a real record of 281 556 numbers, every one lay
       below 255; the escape exists for the rare large gap and costs
       nothing where it is not met. A stream is packed and unpacked in
       ONE 'struct' call, which is what makes this spelling twenty
       times faster to read than the text and no larger than a varint.

       THE LAYOUT (FORMAT.txt section 8 is the normative statement):

           file    = zlib( MAGIC u8 version | header | u32 n | file* )
           header  = run_set | str language | str tool | str format
                     | u8 counts
           run_set = u32 n | (u32 app, u32 choice)*   NO_CHOICE = 2**32-1
           str     = u16 length | UTF-8
           file    = str path | stream EX | stream CV [| stream counts]
                     | u8 n_measures | (tag[2] | stream)*
           stream  = u32 n | u8*

       The run set is FIXED WIDTH so a gather reads who ran without
       decoding the rest. Measure tags are the same two ASCII letters
       as in the text, so the registry dispatches on one key. Named
       points carry their name as 'str' inside the stream's numbers --
       the stream then alternates delta, name, covered, total.

       zlib IS A FIXED LAYER, not an option: measured against the
       compare engine, inflating is 0.3% of the work a judge does, and
       a flag would be a second file format for no gain.
______________________________________________________________________________
"""
import struct
import zlib
from ....auxiliary.binary_codec import Writer, Reader, ESCAPE, CodecFault

from .record  import CoverageRecord, FileCoverage, RecordFault
from .measure import measure_of, measure_of_tag, NamedPointMeasure
from ...bookkeeper.api import TestRunId


MAGIC          = b"VUTC"
FORMAT_VERSION = 1
NO_CHOICE      = 0xFFFFFFFF


#  The writer and the reader are the tree's one binary discipline
#  ('auxiliary/binary_codec'); the record's layout is this module's.
_Writer = Writer
_Reader = Reader


def _numbers_of_ranges(range_tuple):
    """RETURN: list of int, 'd, L' per range (FORMAT.txt 4.2), the
    delta from the previous range's end."""
    out, previous_end = [], 0
    for begin, end in range_tuple:
        out += [begin - previous_end, end - begin]
        previous_end = end
    return out


def _ranges_of_numbers(number_list):
    """RETURN: tuple of (begin, end). Raises RecordFault where a delta
    does not advance or a length covers no line."""
    if len(number_list) % 2:
        raise RecordFault("a range stream of %i numbers is not pairs"
                          % len(number_list))
    out, previous_end = [], 0
    for i in range(0, len(number_list), 2):
        delta, length = number_list[i], number_list[i + 1]
        if delta < 1:
            raise RecordFault("delta %i does not advance: ranges must be "
                              "sorted and disjoint" % delta)
        if length < 1:
            raise RecordFault("length %i covers no line" % length)
        begin = previous_end + delta
        out.append((begin, begin + length))
        previous_end = begin + length
    return tuple(out)


#  ----------------------------------------------------------- the codec

def pack_record(record):
    """
    RETURN: bytes, the record in its binary spelling, zlib-compressed.

    Raises RecordFault where a string does not fit, or where a measure
    holds a point this spelling cannot carry.
    """
    try:
        return _pack_plain(record)
    except CodecFault as fault:
        raise RecordFault(str(fault)) from None


def _pack_plain(record):
    """RETURN: bytes, the record's binary spelling; a 'CodecFault' from
    the writer passes through to the caller."""
    w = _Writer()
    w.part_list.append(MAGIC); w.u8(FORMAT_VERSION)
    run_list = sorted(record.run)
    w.u32(len(run_list))
    for run_id in run_list:
        w.u32(run_id.app_id)
        w.u32(NO_CHOICE if run_id.choice_id is None else run_id.choice_id)
    w.string(record.language); w.string(record.tool); w.string(record.source)
    w.u8(1 if record.counts_f else 0)

    w.u32(len(record.file_db))
    for path in sorted(record.file_db):
        entry = record.file_db[path]
        w.string(path)
        w.stream(_numbers_of_ranges(entry.executable))
        w.stream(_numbers_of_ranges(entry.covered))
        if record.counts_f:
            w.stream(entry.counts if entry.counts is not None else ())
        measure_db = entry.measure_db or {}
        w.u8(len(measure_db))
        for name in sorted(measure_db):
            measure = measure_of(name)
            w.part_list.append(measure.tag.encode("ascii"))
            _pack_points(w, measure, measure_db[name])
    return zlib.compress(w.bytes(), 6)


def _pack_points(w, measure, entry):
    """RETURN: None. A measure's points as one stream: named points
    carry the name as a 'str' inside the stream, via the escape."""
    previous  = 0
    named_f   = _named_f(measure)
    byte_list = []
    for point in sorted(entry):
        if named_f:
            line, name, covered, total = point
        else:
            line, covered, total = point
        byte_list.append(("n", line - previous)); previous = line
        if named_f: byte_list.append(("s", name))
        byte_list.append(("n", covered)); byte_list.append(("n", total))
    #  One stream: names are spliced as 'str' between the numbers. A
    #  reader knows from the measure whether a name stands there.
    out = []
    for kind, value in byte_list:
        if kind == "n":
            if value < ESCAPE: out.append(value)
            else: out.append(ESCAPE); out += struct.pack("<I", value)
        else:
            data = value.encode("utf-8")
            out += struct.pack("<H", len(data)); out += data
    w.u32(len(out))
    w.part_list.append(bytes(out))


def _named_f(measure):
    """RETURN: True, the measure's points carry a NAME (FORMAT.txt 5.3);
    False, they are anonymous decision points (5.2)."""
    return isinstance(measure, NamedPointMeasure)


def unpack_record(data):
    """
    RETURN: CoverageRecord, what the bytes spell.

    Raises RecordFault naming the first fault: no magic, a version this
    build does not read, a truncated buffer, a stream that does not
    advance, a measure tag no measure claims.
    """
    try:
        plain = zlib.decompress(data)
    except zlib.error as fault:
        raise RecordFault("the record is not a zlib stream: %s" % fault) from None
    try:
        return _unpack_plain(plain)
    except CodecFault as fault:
        raise RecordFault(str(fault)) from None


def _unpack_plain(plain):
    """RETURN: CoverageRecord, what the inflated bytes spell; a
    'CodecFault' from the reader passes through to the caller."""
    r = _Reader(plain)
    if r.raw(len(MAGIC)) != MAGIC:
        raise RecordFault("the record does not begin with %r" % MAGIC)
    version = r.u8()
    if version != FORMAT_VERSION:
        raise RecordFault("binary version %i is not %i -- this reader "
                          "does not pretend to read it"
                          % (version, FORMAT_VERSION))
    run_set = set()
    for _ in range(r.u32()):
        app_id, choice_id = r.u32(), r.u32()
        run_set.add(TestRunId(app_id,
                              None if choice_id == NO_CHOICE else choice_id))
    language, tool, source = r.string(), r.string(), r.string()
    counts_f = r.u8() == 1

    file_db = {}
    for _ in range(r.u32()):
        path       = r.string()
        executable = _ranges_of_numbers(r.stream())
        covered    = _ranges_of_numbers(r.stream())
        counts     = None
        if counts_f:
            counts = tuple(r.stream())
            if len(counts) != len(covered):
                raise RecordFault("'%s' carries %i counts for %i covered "
                                  "ranges" % (path, len(counts),
                                              len(covered)))
        measure_db = {}
        for _ in range(r.u8()):
            tag     = r.raw(2).decode("ascii", "replace")
            measure = measure_of_tag(tag)
            if measure is None:
                raise RecordFault("'%s' carries a measure under tag '%s', "
                                  "which no measure claims" % (path, tag))
            measure_db[measure.name] = _unpack_points(r, measure)
        file_db[path] = FileCoverage(path, executable, covered, counts,
                                     measure_db)
    if r.at != len(plain):
        raise RecordFault("%i byte(s) follow the last file"
                          % (len(plain) - r.at))
    return CoverageRecord(language=language, tool=tool, source=source,
                          counts_f=counts_f, file_db=file_db,
                          run=frozenset(run_set))


def _unpack_points(r, measure):
    """RETURN: tuple of points, the measure's own shape."""
    n        = r.u32()
    byte_seq = r.raw(n)
    named_f  = _named_f(measure)
    at, previous, out = 0, 0, []

    def number():
        nonlocal at
        if at >= n: raise RecordFault("a point stream ends mid-point")
        b = byte_seq[at]; at += 1
        if b != ESCAPE: return b
        if at + 4 > n: raise RecordFault("an escaped number is cut short")
        value = struct.unpack_from("<I", byte_seq, at)[0]; at += 4
        return value

    def string():
        nonlocal at
        if at + 2 > n: raise RecordFault("a point name is cut short")
        length = struct.unpack_from("<H", byte_seq, at)[0]; at += 2
        if at + length > n: raise RecordFault("a point name is cut short")
        value = byte_seq[at:at + length].decode("utf-8"); at += length
        return value

    while at < n:
        line = previous + number(); previous = line
        if named_f:
            name = string()
            covered, total = number(), number()
            out.append((line, name, covered, total))
        else:
            covered, total = number(), number()
            out.append((line, covered, total))
    return tuple(out)
