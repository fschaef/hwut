"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE GATHERED COVERAGE OF ONE SOURCE FILE -- record version 3,
         what a coverage run leaves in its output directory (RATIONALE
         D-42, D-43; FORMAT.txt sections 9 and 10), in its BINARY
         spelling, which is the file on disk, and in its TEXT spelling,
         which is the presentation.

DESCRIPTION
       ONE CONTENT, TWO SPELLINGS, as the per-case record has (D-20):
       'pack_gathered'/'unpack_gathered' here are the disk form,
       'format_gathered'/'parse_gathered' the text, and
       'parse(format(f))' and 'unpack(pack(f))' are the same file.

       THE LAYOUT (FORMAT.txt 10.3 is the normative statement):

           file      = zlib( "VUTC" u8 3 | str source | str language
                             | str tool | str format | u8 id_width
                             | stream EX | u8 n_universe | universe*
                             | u32 n_ref | ref* )
           universe  = tag[2] | u32 n | spliced: (delta [str name] total)*
           ref       = u32 reference | stream CV | u8 n_measure | items*
           items     = tag[2] | u32 n | spliced: (ordinal delta, mask)*
           str       = u16 length | UTF-8        stream = u32 n | u8*

       THE UNIVERSE of a measure is every point of the source with its
       number of items, once. A REFERENCE lists, per measure, the points
       it took items of: the ordinal of the point in the universe (as a
       delta from the previous listed one) and the MASK of the items,
       ceil(total / 8) bytes. EVERY ITEM STANDS UNDER EXACTLY ONE
       REFERENCE -- the one whose set of runs is exactly the set that
       took it -- so the union over the references is what was taken.

       THE REFERENCE is the NUMBER of a test run id or of a group id;
       'id_width' is the width at which the output writes its
       identifiers, so a file presents itself without its tables.
______________________________________________________________________________
"""
import re
import zlib
from   dataclasses import dataclass

from ....auxiliary.binary_codec import Writer, Reader, CodecFault

from .binary     import (MAGIC, SpliceReader, numbers_of_ranges,
                         ranges_of_numbers, splice_bytes)
from .identifier import DIGITS, id_number, id_text
from .measure    import measure_of, measure_of_tag
from .record     import RecordFault, decode, encode

GATHERED_VERSION = 3
VERSION_LINE     = "##VUT-COVERAGE 3"
HEADER_KEY_TUPLE = ("source", "language", "tool", "format", "id-width")


@dataclass(frozen=True)
class GatheredFile:
    """The gathered coverage of ONE source file.

    source          str, its path from the run's root
    language, tool, format
                    str, as a record's header (FORMAT.txt 2)
    id_width        int, digits of every identifier of the output
    executable      tuple of (begin, end), the lines that could execute
    universe_tuple  tuple of (measure name, tuple of (line, name,
                    total)), by measure name: every point with the
                    number of its items; 'name' is '' for a decision
                    point. Ascending by (line, name); a repeated
                    (line, name) is another point of the same line
    reference_list  tuple of (reference, spans, item_tuple), ascending
                    by reference.
                      reference   int, the number of a test run id or of
                                  a group id
                      spans       tuple of (begin, end), the lines it
                                  executed; disjoint from every other
                                  reference's
                      item_tuple  tuple of (measure name, tuple of
                                  (ordinal, mask)): per point it took
                                  items of, the ordinal (from 1) in the
                                  universe and the mask of the items
    """
    source:         str
    language:       str
    tool:           str
    format:         str
    id_width:       int
    executable:     tuple
    reference_list: tuple
    universe_tuple: tuple = ()


def measure_db_of(gathered, reference_set):
    """
    RETURN: dict, measure name -> the entry (the measure's own shape,
            measure.py) of the runs the references in 'reference_set'
            stand for: EVERY point of the universe, its mask the OR of
            the masks those references hold. A measure with no point
            is absent.

    'reference_set' holds reference numbers; a caller that has a run
    resolves it to the references that include the run first.
    """
    result = {}
    for name, point_tuple in gathered.universe_tuple:
        mask_list = [0] * len(point_tuple)
        for reference, _, item_tuple in gathered.reference_list:
            if reference not in reference_set: continue
            for item_name, entry_tuple in item_tuple:
                if item_name != name: continue
                for ordinal, mask in entry_tuple:
                    mask_list[ordinal - 1] |= mask
        measure = measure_of(name)
        result[name] = measure.entry_of(
            [(line, point_name, total, mask)
             for (line, point_name, total), mask
             in zip(point_tuple, mask_list)])
    return result


def pack_gathered(gathered):
    """
    RETURN: bytes, 'gathered' in its binary spelling, zlib-compressed.

    Raises RecordFault where a string does not fit, the references do
    not ascend, or the universe and the item lists do not agree
    ('_assert_measures').
    """
    _assert_ascending(gathered.reference_list)
    _assert_measures(gathered)
    w = Writer()
    try:
        w.part_list.append(MAGIC); w.u8(GATHERED_VERSION)
        for text in (gathered.source, gathered.language, gathered.tool,
                     gathered.format):
            w.string(text)
        w.u8(gathered.id_width)
        w.stream(numbers_of_ranges(gathered.executable))
        w.u8(len(gathered.universe_tuple))
        for name, point_tuple in gathered.universe_tuple:
            measure = measure_of(name)
            w.part_list.append(measure.tag.encode("ascii"))
            piece_list, previous = [], 0
            for line, point_name, total in point_tuple:
                piece_list.append(("n", line - previous)); previous = line
                if measure.named_f: piece_list.append(("s", point_name))
                piece_list.append(("n", total))
            data = splice_bytes(piece_list)
            w.u32(len(data)); w.part_list.append(data)
        total_db = _total_db_of(gathered.universe_tuple)
        w.u32(len(gathered.reference_list))
        for reference, span_tuple, item_tuple in gathered.reference_list:
            w.u32(reference)
            w.stream(numbers_of_ranges(span_tuple))
            w.u8(len(item_tuple))
            for name, entry_tuple in item_tuple:
                w.part_list.append(measure_of(name).tag.encode("ascii"))
                piece_list, previous = [], 0
                for ordinal, mask in entry_tuple:
                    piece_list.append(("n", ordinal - previous))
                    piece_list.append(("m", (mask, total_db[name][ordinal - 1])))
                    previous = ordinal
                data = splice_bytes(piece_list)
                w.u32(len(data)); w.part_list.append(data)
        return zlib.compress(w.bytes(), 6)
    except CodecFault as fault:
        raise RecordFault(str(fault)) from None


def binary_version(data):
    """
    RETURN: int, the version byte of a record in its binary spelling.
            None, where the bytes are no zlib stream or do not begin
            with the magic.
    """
    try:
        plain = zlib.decompress(data)
    except zlib.error:
        return None
    if plain[:len(MAGIC)] != MAGIC or len(plain) <= len(MAGIC):
        return None
    return plain[len(MAGIC)]


def unpack_gathered(data):
    """
    RETURN: GatheredFile, what the bytes spell.

    Raises RecordFault naming the first fault: not a zlib stream, no
    magic, a version this build does not read, a truncated buffer, a
    stream that does not advance, references that do not ascend, a
    measure tag no measure claims, an item list that names a point the
    universe lacks or an item a point does not have, bytes after the
    last reference.
    """
    try:
        plain = zlib.decompress(data)
    except zlib.error as fault:
        raise RecordFault("the file is not a zlib stream: %s" % fault) \
              from None
    try:
        return _unpack_plain(plain)
    except CodecFault as fault:
        raise RecordFault(str(fault)) from None


def _measure_of_tag(r, place):
    """RETURN: I_Measure of the two ASCII letters next in 'r'. Raises
    RecordFault where no measure claims them."""
    tag     = r.raw(2).decode("ascii", "replace")
    measure = measure_of_tag(tag)
    if measure is None:
        raise RecordFault("the %s carries a measure under tag '%s', which "
                          "no measure claims" % (place, tag))
    return measure


def _unpack_plain(plain):
    """RETURN: GatheredFile; a 'CodecFault' passes through."""
    r = Reader(plain)
    if r.raw(len(MAGIC)) != MAGIC:
        raise RecordFault("the file does not begin with %r" % MAGIC)
    version = r.u8()
    if version != GATHERED_VERSION:
        raise RecordFault("binary version %i is not %i -- this reader "
                          "reads the gathered coverage of a source file "
                          "only" % (version, GATHERED_VERSION))
    source, language, tool, format_ = (r.string(), r.string(), r.string(),
                                       r.string())
    id_width   = r.u8()
    executable = ranges_of_numbers(r.stream())
    universe_list = []
    for _ in range(r.u8()):
        measure = _measure_of_tag(r, "universe")
        splice  = SpliceReader(r.raw(r.u32()))
        point_list, previous = [], 0
        while splice.more():
            line = previous + splice.number(); previous = line
            point_name = splice.string() if measure.named_f else ""
            point_list.append((line, point_name, splice.number()))
        universe_list.append((measure.name, tuple(point_list)))
    universe_tuple = tuple(universe_list)
    total_db = _total_db_of(universe_tuple)
    reference_list = []
    for _ in range(r.u32()):
        reference  = r.u32()
        span_tuple = ranges_of_numbers(r.stream())
        item_list  = []
        for _ in range(r.u8()):
            measure = _measure_of_tag(r, "reference")
            splice  = SpliceReader(r.raw(r.u32()))
            total_list = total_db.get(measure.name)
            if total_list is None:
                raise RecordFault("a reference lists items of measure "
                                  "'%s', which the universe lacks"
                                  % measure.name)
            entry_list, ordinal = [], 0
            while splice.more():
                ordinal += splice.number()
                if not 1 <= ordinal <= len(total_list):
                    raise RecordFault(
                        "ordinal %i is no point of the %i of measure '%s'"
                        % (ordinal, len(total_list), measure.name))
                entry_list.append((ordinal,
                                   splice.mask(total_list[ordinal - 1])))
            item_list.append((measure.name, tuple(entry_list)))
        reference_list.append((reference, span_tuple, tuple(item_list)))
    if r.at != len(plain):
        raise RecordFault("%i byte(s) follow the last reference"
                          % (len(plain) - r.at))
    gathered = GatheredFile(source, language, tool, format_, id_width,
                            executable, tuple(reference_list),
                            universe_tuple)
    _assert_ascending(gathered.reference_list)
    _assert_measures(gathered)
    return gathered


def _total_db_of(universe_tuple):
    """RETURN: dict, measure name -> list of int, the number of items of
    each point of its universe, in order."""
    return {name: [total for _, _, total in point_tuple]
            for name, point_tuple in universe_tuple}


def _assert_ascending(reference_list):
    """RETURN: None. Raises RecordFault where the references do not
    strictly ascend."""
    previous = -1
    for entry in reference_list:
        if entry[0] <= previous:
            raise RecordFault("reference %i does not ascend from %i"
                              % (entry[0], previous))
        previous = entry[0]


def _assert_measures(gathered):
    """
    RETURN: None. Raises RecordFault naming the first fault of the
            measures: a measure no registry knows or listed twice or out
            of name order; a point with nothing to take, a name where
            there should be none or none where there should be one; a
            universe not in (line, name) order; an item list of a
            measure the universe lacks, with ordinals that do not
            strictly ascend or name no point, with a mask of no item or
            of an item the point does not have; and an item that stands
            under two references.
    """
    previous_name = None
    for name, point_tuple in gathered.universe_tuple:
        measure = measure_of(name)
        if measure is None:
            raise RecordFault("measure '%s' is not registered" % name)
        if previous_name is not None and name <= previous_name:
            raise RecordFault("measure '%s' does not ascend from '%s'"
                              % (name, previous_name))
        previous_name = name
        previous = (0, "")
        for line, point_name, total in point_tuple:
            if total < 1:
                raise RecordFault("a point of '%s' at line %i has nothing "
                                  "to take" % (name, line))
            if bool(point_name) != measure.named_f:
                raise RecordFault(
                    "a point of '%s' at line %i %s" % (
                        name, line, "has no name" if measure.named_f
                        else "has a name: '%s'" % point_name))
            if measure.named_f and ("*" in point_name or "," in point_name):
                raise RecordFault("point name '%s' carries a separator of "
                                  "the encoding itself" % point_name)
            if line < 1 or (line, point_name) < previous:
                raise RecordFault("the points of '%s' do not ascend at "
                                  "line %i" % (name, line))
            previous = (line, point_name)
    total_db = _total_db_of(gathered.universe_tuple)
    taken_db = {}                      # (measure, ordinal) -> mask
    for reference, _, item_tuple in gathered.reference_list:
        previous_name = None
        for name, entry_tuple in item_tuple:
            if name not in total_db:
                raise RecordFault("reference %i lists items of measure "
                                  "'%s', which the universe lacks"
                                  % (reference, name))
            if previous_name is not None and name <= previous_name:
                raise RecordFault("reference %i lists '%s' after '%s'"
                                  % (reference, name, previous_name))
            previous_name = name
            if not entry_tuple:
                raise RecordFault("reference %i lists no point of '%s'"
                                  % (reference, name))
            previous = 0
            for ordinal, mask in entry_tuple:
                if ordinal <= previous:
                    raise RecordFault("ordinal %i does not ascend from %i"
                                      % (ordinal, previous))
                previous = ordinal
                if ordinal > len(total_db[name]):
                    raise RecordFault(
                        "ordinal %i is no point of the %i of measure '%s'"
                        % (ordinal, len(total_db[name]), name))
                total = total_db[name][ordinal - 1]
                if mask < 1 or mask >> total:
                    raise RecordFault(
                        "mask %x names no item, or one the point (%i "
                        "item(s)) does not have" % (mask, total))
                if taken_db.get((name, ordinal), 0) & mask:
                    raise RecordFault(
                        "an item of point %i of '%s' stands under two "
                        "references" % (ordinal, name))
                taken_db[(name, ordinal)] = taken_db.get((name, ordinal),
                                                         0) | mask


#  -------------------------------------------------------- the text

def format_gathered(gathered):
    """
    RETURN: str, the text spelling of 'gathered' (FORMAT.txt 9, 10.2):
            the version line, the header, 'EX', one '<TAG>:' universe
            line per measure, one 'CV@' line per reference with lines,
            one '<TAG>@' item line per reference and measure. LF
            terminated.
    """
    line_list = [VERSION_LINE]
    for key, value in (("source", gathered.source),
                       ("language", gathered.language),
                       ("tool", gathered.tool),
                       ("format", gathered.format),
                       ("id-width", gathered.id_width)):
        line_list.append("##%-9s %s" % (key + ":", value))
    line_list.append("EX:%s" % encode(gathered.executable))
    for name, point_tuple in gathered.universe_tuple:
        measure = measure_of(name)
        piece_list, previous = [], 0
        for line, point_name, total in point_tuple:
            if measure.named_f:
                piece_list.append("%i*%s*%i" % (line - previous,
                                                point_name, total))
            else:
                piece_list.append("%i*%i" % (line - previous, total))
            previous = line
        line_list.append("%s:%s" % (measure.tag, ",".join(piece_list)))
    for reference, span_tuple, _ in gathered.reference_list:
        if span_tuple:
            line_list.append("CV@%s:%s"
                             % (id_text(reference, gathered.id_width),
                                encode(span_tuple)))
    for name, _ in gathered.universe_tuple:
        tag = measure_of(name).tag
        for reference, _, item_tuple in gathered.reference_list:
            for item_name, entry_tuple in item_tuple:
                if item_name != name: continue
                previous, piece_list = 0, []
                for ordinal, mask in entry_tuple:
                    piece_list.append("%i*%x" % (ordinal - previous, mask))
                    previous = ordinal
                line_list.append("%s@%s:%s"
                                 % (tag, id_text(reference,
                                                 gathered.id_width),
                                    ",".join(piece_list)))
    return "\n".join(line_list) + "\n"


def _universe_of_text(measure, text):
    """RETURN: tuple of (line, name, total), what a '<TAG>:' line
    spells. Raises RecordFault on a piece that is no point."""
    result, previous = [], 0
    for piece in (text.split(",") if text.strip() else ()):
        part_list = piece.split("*")
        if len(part_list) != (3 if measure.named_f else 2):
            raise RecordFault("'%s' spells no %s point" % (
                piece, "'<delta>*<name>*<total>'" if measure.named_f
                else "'<delta>*<total>'"))
        try:
            delta, total = int(part_list[0]), int(part_list[-1])
        except ValueError:
            raise RecordFault("'%s' spells no number where one belongs"
                              % piece) from None
        if delta < 0 or (delta == 0 and not result):
            raise RecordFault("delta %i in '%s' does not advance"
                              % (delta, piece))
        previous += delta
        result.append((previous, part_list[1] if measure.named_f else "",
                       total))
    return tuple(result)


def _items_of_text(text):
    """RETURN: tuple of (ordinal, mask), what a '<TAG>@' line spells.
    Raises RecordFault on a piece that is no item."""
    result, ordinal = [], 0
    for piece in (text.split(",") if text.strip() else ()):
        head, star, mask_text = piece.partition("*")
        try:
            delta, mask = int(head), int(mask_text, 16)
        except ValueError:
            raise RecordFault("'%s' spells no '<delta>*<mask>' item"
                              % piece) from None
        if not star or delta < 1:
            raise RecordFault("'%s' does not advance to a point" % piece)
        ordinal += delta
        result.append((ordinal, mask))
    return tuple(result)


def parse_gathered(text):
    """
    RETURN: GatheredFile, what the text spells.

    Raises RecordFault naming the first fault: no version line or
    another version, a header key missing, an 'EX' missing or twice, a
    universe of a measure twice or no measure claims, an item list
    before its universe, a reference that is no identifier of the stated
    width or does not ascend, a line of no known kind; and every fault
    the binary spelling names for the same content.
    """
    line_list = [line.rstrip() for line in text.split("\n")
                 if line.strip()]
    if not line_list or line_list[0] != VERSION_LINE:
        raise RecordFault("the text does not begin with '%s'"
                          % VERSION_LINE)
    header_db, executable = {}, None
    cover_list, universe_db, item_db = [], {}, {}
    width, last_db = None, {}

    def reference_of(word):
        """RETURN: int, the number of the identifier 'word'. Raises
        RecordFault where it is none of the stated width."""
        if len(word) != width \
           or not re.fullmatch("[%s]+" % re.escape(DIGITS), word):
            raise RecordFault("'%s' is no identifier of %i digit(s)"
                              % (word, width))
        return id_number(word)

    def ascend(kind, reference):
        """RETURN: None. Raises RecordFault where the references of one
        kind of line do not strictly ascend."""
        if reference <= last_db.get(kind, -1):
            raise RecordFault("reference %i does not ascend from %i"
                              % (reference, last_db[kind]))
        last_db[kind] = reference

    for line in line_list[1:]:
        if line.startswith("##"):
            key, _, value = line[2:].partition(":")
            header_db[key.strip()] = value.strip()
            continue
        if width is None:
            missing = [k for k in HEADER_KEY_TUPLE if k not in header_db]
            if missing:
                raise RecordFault("header key '%s' is missing" % missing[0])
            if not header_db["id-width"].isdigit():
                raise RecordFault("'id-width' spells no number: '%s'"
                                  % header_db["id-width"])
            width = int(header_db["id-width"])
        if line.startswith("EX:"):
            if executable is not None:
                raise RecordFault("'EX' stands twice")
            executable = decode(line[3:])[0]
        elif line.startswith("CV@"):
            if executable is None:
                raise RecordFault("'CV@' before 'EX'")
            word, _, ranges = line[3:].partition(":")
            reference = reference_of(word)
            ascend("CV", reference)
            cover_list.append((reference, decode(ranges)[0]))
        elif re.match("[A-Z]{2}:", line):
            measure = measure_of_tag(line[:2])
            if measure is None:
                raise RecordFault("'%s' is a universe under a tag no "
                                  "measure claims" % line[:2])
            if measure.name in universe_db:
                raise RecordFault("the universe of '%s' stands twice"
                                  % measure.name)
            universe_db[measure.name] = _universe_of_text(measure, line[3:])
        elif re.match("[A-Z]{2}@", line):
            measure = measure_of_tag(line[:2])
            if measure is None:
                raise RecordFault("'%s' lists items under a tag no "
                                  "measure claims" % line[:2])
            if measure.name not in universe_db:
                raise RecordFault("'%s@' before the universe '%s:'"
                                  % (line[:2], line[:2]))
            word, _, items = line[3:].partition(":")
            reference = reference_of(word)
            ascend(measure.name, reference)
            item_db.setdefault(reference, []).append(
                (measure.name, _items_of_text(items)))
        else:
            raise RecordFault("a line of no known kind: '%s'" % line)
    if width is None:
        missing = [k for k in HEADER_KEY_TUPLE if k not in header_db]
        raise RecordFault("header key '%s' is missing"
                          % (missing[0] if missing else "id-width"))
    if executable is None:
        raise RecordFault("'EX' is missing")
    span_db = dict(cover_list)
    reference_list = tuple(
        (reference, span_db.get(reference, ()),
         tuple(sorted(item_db.get(reference, ()))))
        for reference in sorted(set(span_db) | set(item_db)))
    gathered = GatheredFile(header_db["source"], header_db["language"],
                            header_db["tool"], header_db["format"], width,
                            executable, reference_list,
                            tuple(sorted(
                                (name, point_tuple)
                                for name, point_tuple in universe_db.items())))
    _assert_measures(gathered)
    return gathered
