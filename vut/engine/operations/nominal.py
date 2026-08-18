"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE NOMINAL -- what a subject is held against.

DESCRIPTION
       A nominal is the canonicalised subject stream of a run whose
       behaviour was ACCEPTED. It is the "accepted" role of the one
       artifact (README 2.3): subject and nominal are the same kind of
       thing, and a comparison merely aligns two readers.

       A Nominal is therefore a READER, not a file path and not a
       comparator. Three kinds differ only in where the bytes come from:

           RecordNominal(path)     the accepted record on storage
           StreamNominal(reader)   an existing reader
           BytesNominal(data)      in memory

       Opened LAZILY: constructing a Nominal touches nothing, so a
       configuration may name a record that does not exist yet, and the
       absence is reported by the operation that needed it rather than by
       the object that named it.
______________________________________________________________________________
"""
import io
from   pathlib import Path


class NominalNotAvailable(Exception):
    """The nominal was named but cannot be read. Carries the name so a
    report can say WHICH one, and the underlying cause so a reader can
    say why."""

    def __init__(self, name, cause=None):
        self.name  = name
        self.cause = cause
        super().__init__("nominal not available: %s%s"
                         % (name, "" if cause is None else " (%s)" % cause))


class Nominal:
    """The reference production of one subject, as a reader.

    Subclasses differ ONLY in 'open()'. Nothing else about a nominal
    depends on where it lives.
    """

    def open(self):
        """
        RETURN: a text reader positioned at the first line.

        Raises NominalNotAvailable if the bytes cannot be had. The caller
        closes what it opens; a Nominal holds no handle of its own, so it
        may be opened more than once.
        """
        raise NotImplementedError

    @property
    def name(self):
        """
        RETURN: str, what to call this nominal in a report.
        """
        raise NotImplementedError

    def exists(self):
        """
        RETURN: True,  'open()' would succeed now.
                False, it would raise.

        A QUESTION, never a promise: between this call and 'open()' the
        world may change. Use it to report, not to guard.
        """
        try:
            reader = self.open()
        except NominalNotAvailable:
            return False
        close = getattr(reader, "close", None)
        if close is not None: close()
        return True


class RecordNominal(Nominal):
    """The accepted record on storage -- the everyday case, HWUT's GOOD."""

    def __init__(self, path):
        self.path = Path(path)

    def open(self):
        """
        RETURN: a text reader over the record file.

        Raises NominalNotAvailable if the file is absent or unreadable.
        """
        try:
            return open(self.path, "r", encoding="utf-8", newline="")
        except OSError as error:
            raise NominalNotAvailable(self.name, error.strerror)

    @property
    def name(self):
        """RETURN: str, the record's path."""
        return str(self.path)


class StreamNominal(Nominal):
    """An existing reader. The reader is CONSUMED on first open, so this
    kind cannot be opened twice -- which is why it serves tests and
    pipes, not stored records."""

    def __init__(self, reader, name="<stream>"):
        self._reader = reader
        self._name   = name
        self._spent  = False

    def open(self):
        """
        RETURN: the reader given at construction.

        Raises NominalNotAvailable on a second open: a stream has one
        pass, and silently handing back an exhausted reader would compare
        a subject against nothing and call it equal.
        """
        if self._spent:
            raise NominalNotAvailable(self._name, "stream already consumed")
        self._spent = True
        return self._reader

    @property
    def name(self):
        """RETURN: str, the name given at construction."""
        return self._name


class BytesNominal(Nominal):
    """In memory. Re-openable, since the bytes are kept."""

    def __init__(self, data, name="<bytes>"):
        self._text = data.decode("utf-8") if isinstance(data, bytes) else data
        self._name = name

    def open(self):
        """RETURN: a text reader over the in-memory content."""
        return io.StringIO(self._text)

    @property
    def name(self):
        """RETURN: str, the name given at construction."""
        return self._name
