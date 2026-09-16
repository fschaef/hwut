"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHAT THIS MACHINE OBSERVED WHILE THIS PERSON WAS WORKING.
         A second database, machine-local, beside the '.cover' records.
         IT IS NOT THE BOOK (services E-22, E-23).

    address     'TMP/store/observations.bin', beside the records
    form        binary, by the tree's one writer and reader
                ('auxiliary/binary_codec'), which the coverage records
                use too
    key         (test, choice, operation) -- STATE NOW, overwritten
    fault       'ObservationFault' on a corrupt read

The book holds DECISIONS: what a verdict was, what was accepted, what
a later reader needs to know what an entry meant. Everything a RUN
merely noticed while producing them is here -- durations, telemetry,
the host that saw it -- because a run can make it again, identically,
and what a run can regenerate is transient (E-20).

CARRIES, per entry:

    when             instant of the record, integer, epoch seconds
    duration_ms      integer milliseconds
    host             '<system>-<machine>/<node>'
    cpu_time_ms      integer milliseconds
    peak_memory_mb   |
    peak_pids        |  the rest of the ProcsitterResult telemetry
    peak_disk_mb     |
    created_tuple    what the call made and did not remove (E-27)
    compare_complete_f
                     the comparison READ BOTH TEXTS TO THE END. False
                     where it aborted at the first difference it could
                     state -- and then the stored candidate may be a
                     PREFIX, so no reader may call the difference
                     'shrank' (E-31).

DURATIONS ARE INTEGER MILLISECONDS, and THE UNIT IS IN THE NAME:
'duration_ms', 'cpu_time_ms'. Not 'time_ms' -- 'time' reads as an
instant, and an instant is a different thing in the same entry. Where
an instant reaches the BOOK it stays an ISO-8601 'Z' string; here, in
a binary local file, it is an integer.

ONE FILE PER DIRECTORY, not one per key: a query asks about every key
at once ('which of these ran faster than two seconds'), and a hundred
tiny files would be a hundred opens to answer it. The whole file is
read, changed and written, as the book is.

ABSENCE IS 'None', never a zero: where a provider could not measure,
the field is absent and says so.
______________________________________________________________________________
"""
import os
from vut.auxiliary import clock

from ...auxiliary.binary_codec import Writer, Reader, CodecFault

OBSERVATION_FILE_NAME = "observations.bin"
MAGIC                 = b"VUTO"
FORMAT_VERSION        = 1

#  Field -> how it is spelt on disk. The ORDER IS THE FORMAT.
_INT_FIELD_TUPLE   = ("when", "duration_ms", "cpu_time_ms", "peak_pids")
_FLOAT_FIELD_TUPLE = ("peak_memory_mb", "peak_disk_mb")
_ABSENT            = 0xFFFFFFFF          # an integer field nobody measured


class ObservationFault(Exception):
    """A local observation file that cannot be read."""
    pass


class Observation:
    """ONE ENTRY: what one operation on one choice was observed to do.

    Every field may be None: absence is data, and a provider that
    cannot measure says so rather than reporting a zero.
    """
    __slots__ = ("when", "duration_ms", "host", "cpu_time_ms",
                 "peak_memory_mb", "peak_pids", "peak_disk_mb",
                 "created_tuple", "compare_complete_f")

    def __init__(self, when=None, duration_ms=None, host=None,
                 cpu_time_ms=None, peak_memory_mb=None, peak_pids=None,
                 peak_disk_mb=None, created_tuple=(),
                 compare_complete_f=None):
        self.when               = when if when is not None else clock.epoch_second()
        self.duration_ms        = duration_ms
        self.host               = host
        self.cpu_time_ms        = cpu_time_ms
        self.peak_memory_mb     = peak_memory_mb
        self.peak_pids          = peak_pids
        self.peak_disk_mb       = peak_disk_mb
        self.created_tuple      = tuple(created_tuple)
        self.compare_complete_f = compare_complete_f

    def __repr__(self):
        """RETURN: str, the entry's fields, absent ones omitted."""
        part_list = ["%s=%r" % (name, getattr(self, name))
                     for name in self.__slots__
                     if getattr(self, name) not in (None, ())]
        return "Observation(%s)" % ", ".join(part_list)


def observation_of(record, duration_ms=None, host=None,
                   compare_complete_f=None):
    """
    RETURN: Observation, a 'ProcsitterResult''s telemetry as one entry;
            every field the result does not carry stays None.

    'record' may be None -- an operation that ran no process observed
    a duration and nothing else.
    """
    if record is None:
        return Observation(duration_ms=duration_ms, host=host,
                           compare_complete_f=compare_complete_f)
    wall = getattr(record, "wall_clock_sec", None)
    cpu  = getattr(record, "cpu_time_sec", None)
    return Observation(
        duration_ms    = duration_ms if duration_ms is not None
                         else (None if wall is None else int(wall * 1000)),
        host           = host,
        cpu_time_ms    = None if cpu is None else int(cpu * 1000),
        peak_memory_mb = getattr(record, "peak_memory_mb", None),
        peak_pids      = getattr(record, "peak_pids", None),
        peak_disk_mb   = getattr(record, "peak_disk_mb", None),
        created_tuple  = tuple(getattr(record, "created_tuple", ()) or ()),
        compare_complete_f = compare_complete_f)


class ObservationDb:
    """THE LOCAL DATABASE of one test directory.

    Read whole, changed in memory, written whole -- state now, one
    entry per (test, choice, operation), overwritten. No history:
    history is the configuration management system's task, and it
    holds 'GOOD/', which is exactly the durable set.
    """

    def __init__(self, directory, store_directory_name="TMP/store"):
        """RETURN: ObservationDb, not yet read."""
        self.path      = os.path.join(str(directory), store_directory_name,
                                      OBSERVATION_FILE_NAME)
        self.entry_db  = None            # (test, choice, operation) -> entry

    def read(self):
        """
        RETURN: dict, every entry, keyed '(test, choice, operation)'.
                THE EMPTY DICT where no file stands: a fresh checkout
                has observed nothing here, which is an answer.

        Raises ObservationFault where a file stands and cannot be read:
        a corrupt local file is said, never silently treated as
        emptiness.
        """
        if self.entry_db is not None: return self.entry_db
        if not os.path.isfile(self.path):
            self.entry_db = {}
            return self.entry_db
        try:
            self.entry_db = _unpack(open(self.path, "rb").read())
        except (OSError, CodecFault, ObservationFault) as fault:
            raise ObservationFault("'%s' cannot be read: %s"
                                   % (self.path, fault)) from None
        return self.entry_db

    def get(self, test, choice, operation):
        """
        RETURN: Observation | None -- None where this machine has not
                observed that key. SILENCE IS NOT SELECTED: a test
                this machine never ran satisfies no observation query.
        """
        return self.read().get((test, choice, operation))

    def note(self, test, choice, operation, observation):
        """
        RETURN: None. The entry replaces whatever stood under that key,
                and the file is written.
        """
        self.read()[(test, choice, operation)] = observation
        directory = os.path.dirname(self.path)
        if directory: os.makedirs(directory, exist_ok=True)
        with open(self.path, "wb") as handle:
            handle.write(_pack(self.entry_db))


def _pack(entry_db):
    """
    RETURN: bytes, every entry in the local spelling.

        file  = MAGIC | u8 version | u32 n | entry*
        entry = str test | str choice | str operation
                | u32 when | u32 duration_ms | u32 cpu_time_ms
                | u32 peak_pids | str host
                | str peak_memory_mb | str peak_disk_mb
                | u8 compare_complete (0 no, 1 yes, 2 not stated)
                | u32 n | str created*

    An integer nobody measured is 0xFFFFFFFF; a float is written as a
    string, empty where absent, since the numbers here are for a
    person to read and not to compute with.
    """
    w = Writer()
    w.part_list.append(MAGIC)
    w.u8(FORMAT_VERSION)
    w.u32(len(entry_db))
    for key in sorted(entry_db, key=lambda k: tuple(str(x) for x in k)):
        test, choice, operation = key
        entry = entry_db[key]
        w.string(test)
        w.string("" if choice is None else choice)
        w.string(operation)
        for name in _INT_FIELD_TUPLE:
            value = getattr(entry, name)
            w.u32(_ABSENT if value is None else int(value))
        w.string(entry.host or "")
        for name in _FLOAT_FIELD_TUPLE:
            value = getattr(entry, name)
            w.string("" if value is None else repr(float(value)))
        w.u8(2 if entry.compare_complete_f is None
             else (1 if entry.compare_complete_f else 0))
        w.u32(len(entry.created_tuple))
        for name in entry.created_tuple: w.string(name)
    return b"".join(w.part_list)


def _unpack(data):
    """
    RETURN: dict, what the bytes spell, keyed '(test, choice,
            operation)'.

    Raises ObservationFault naming the first fault: no magic, or a version
    this build does not read -- it does not pretend to read it.
    """
    r = Reader(data)
    if r.raw(len(MAGIC)) != MAGIC:
        raise ObservationFault("the file does not begin with %r" % MAGIC)
    version = r.u8()
    if version != FORMAT_VERSION:
        raise ObservationFault("observation version %i is not %i"
                          % (version, FORMAT_VERSION))
    entry_db = {}
    for _ in range(r.u32()):
        test      = r.string()
        choice    = r.string() or None
        operation = r.string()
        field_db  = {}
        for name in _INT_FIELD_TUPLE:
            value = r.u32()
            field_db[name] = None if value == _ABSENT else value
        field_db["host"] = r.string() or None
        for name in _FLOAT_FIELD_TUPLE:
            text = r.string()
            field_db[name] = float(text) if text else None
        complete = r.u8()
        field_db["compare_complete_f"] = None if complete == 2 \
                                         else bool(complete)
        field_db["created_tuple"] = tuple(r.string()
                                          for _ in range(r.u32()))
        entry_db[(test, choice, operation)] = Observation(**field_db)
    return entry_db
