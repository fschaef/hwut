"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Chunk pipe -- interpretation of input text as 'InputChunk' objects.

A chunk pipe absorbs lines of text from a 'line provider', i.e. an object
hat responds to a function:

                 .readline()

lines are then passed through the 'PatternFinder' to transform text into
'LineElement'-s such as numbers, whitespace or user-defined patterns.  A
sequence of 'LineElement'-s make up for a semantic representation of a text
line.

The stream consists of OUTER text (line sequences, compared in order) and
REGIONS, framed as

    ##! <handler> [<param>|<param>=<value>]*
    ...
    ####

whose interpretation is delegated to the handler registered under the
shebang name ('region/registry.py').

FRAMING RULES (loud 'RegionSyntaxError', propagated by the zip stage):
nesting forbidden; stray '####' forbidden; EOF with an open region
forbidden; unknown handler / malformed parameter forbidden.
_______________________________________________________________________________
"""
from vut.engine.compare.engine.enums             import E_Chunk
from vut.engine.compare.engine.line              import Line
from vut.engine.compare.reading.input_chunk        import InputChunk,         \
                                                        InputChunkTerminal, \
                                                        InputChunkError,    \
                                                        InputChunk_factory
from vut.engine.compare.reading.pattern_finder     import PatternFinder
from vut.engine.compare.reading.line_scanner       import E_LineClass,       \
                                                        INSIGNIFICANT_LINE_CLASS_SET, \
                                                        classify
from vut.engine.compare.region.registry          import RegionSyntaxError,  \
                                                        parse_shebang,      \
                                                        make_region_chunk,  \
                                                        handler_db
from vut.engine.compare.configuration            import Configuration

from itertools import count
from typeguard import typechecked
from typing    import AsyncIterator
import asyncio


class ChunkPipe:
    @typechecked
    def __init__(self, configuration: Configuration, line_provider: AsyncIterator):
        PatternFinder.__init__(self, configuration.pattern_finder)
        self.configuration = configuration
        self.line_provider = line_provider
        self.pf            = PatternFinder(self.configuration.pattern_finder)

    def create_producer_task(self, queue, fetch_gate = None):
        return asyncio.create_task(self._produce(queue, fetch_gate))

    async def _produce(self, queue, fetch_gate: asyncio.Event | None):
        try:
            sentinel = InputChunkTerminal()

            async for item in self.yield_input_chunks():
                await queue.put(item)
                if fetch_gate is not None:  # Pause, if someone stops you
                    await fetch_gate.wait()
            await queue.put(sentinel)

        except RegionSyntaxError as error:
            # Carry the error to the consumer -- the zip stage re-raises it.
            await queue.put(InputChunkError(error))

        except Exception:
            import traceback
            traceback.print_exc()
            await queue.put(sentinel)
            raise


class _RegionFraming:
    """Shared region state machine of both pipes: which handler is open,
    since when, with which parameters. The pipes differ only in what they
    do with the lines (packaging), never in the framing rules.
    """
    __slots__ = ("handler", "params", "begin_line_n", "begin_text")

    def __init__(self):
        self.handler = None            # None <=> outside any region

    def is_open(self):
        return self.handler is not None

    def open_shebang(self, line, line_n):
        if self.is_open():
            raise RegionSyntaxError(line_n,
                "region shebang inside an open region ('##! %s' from line %s)"
                " -- nesting is forbidden"
                % (self.handler.shebang_name, self.begin_line_n))
        self.handler, self.params = parse_shebang(line, line_n, handler_db())
        self.begin_line_n = line_n
        self.begin_text   = line.rstrip("\n")

    def close(self, line, line_n, config, line_list):
        """RETURNS: InputChunk, the completed region chunk."""
        assert self.is_open()
        chunk = make_region_chunk(self.handler, self.begin_line_n, line_n,
                                  line_list, config, self.params)
        chunk.framing = (self.begin_text, line.rstrip("\n"))
        self.handler = None
        return chunk

    def check_stray_end(self, line_n):
        if not self.is_open():
            raise RegionSyntaxError(line_n,
                "'####' without an open region")

    def check_eof(self, line_n):
        if self.is_open():
            raise RegionSyntaxError(line_n,
                "end of stream inside an open region ('##! %s' from line %s)"
                " -- '####' missing"
                % (self.handler.shebang_name, self.begin_line_n))


class EquivalenceCheckChunkPipe(ChunkPipe):
    """PACKAGING POLICY (classification: 'reading/line_scanner.py'):

        REGION_BEGIN/END   open/close a region via the registry; the
                           completed region chunk is yielded, EVEN IF EMPTY
                           (the framing must find its counterpart)
        BLANK / IGNORED    DROP -- the Judge never sees insignificant lines
        CONTENT            outside a region: emit as single-LINE chunk; a
                           whole-line VISIBLE_NOTHING is skipped (equals NO
                           line at all -- see 'Line.is_visible_nothing';
                           the Lawyer's sequence search skips it as
                           GOOD_INSERT/GOOD_DELETE, so the Judge must skip
                           it likewise, THE LAW).
                           inside a region: buffered; regions COUNT their
                           visible-nothing lines (both faces).
    """
    @typechecked
    async def yield_input_chunks(self) -> InputChunk:
        framing   = _RegionFraming()
        line_list = []
        line_n    = 0

        for line_n in count(1):
            line = await self.line_provider.readline()
            if not line:
                break

            line_class = classify(line, self.pf)

            if line_class is E_LineClass.REGION_BEGIN:
                framing.open_shebang(line, line_n)
                line_list = []
            elif line_class is E_LineClass.REGION_END:
                framing.check_stray_end(line_n)
                # Shebang regions are yielded EVEN IF EMPTY: the framing
                # itself must find its counterpart (an empty 'ignore' vs a
                # full one is equivalent; a region vs no region is not).
                yield framing.close(line, line_n, self.configuration, line_list)
                line_list = []
            elif line_class in INSIGNIFICANT_LINE_CLASS_SET:
                continue
            else:
                assert line_class is E_LineClass.CONTENT
                processed_line = Line(line_n, line, self.pf)

                if framing.is_open():
                    line_list.append(processed_line)
                elif processed_line.is_visible_nothing():
                    continue
                else:
                    yield InputChunk_factory(E_Chunk.LINE, line_n, line_n,
                                             [processed_line], self.configuration)

        framing.check_eof(line_n)


class AssociationChunkPipe(ChunkPipe):
    """PACKAGING POLICY (classification: 'reading/line_scanner.py'):

        REGION_BEGIN/END   open/close a region via the registry; the outer
                           block is flushed on open; the region chunk is
                           yielded on close (even if empty)
        BLANK / IGNORED    KEEP -- the Lawyer displays every input line;
                           insignificant lines become neutral filler pairs
                           (see 'LinePair.is_equivalent')
        CONTENT            keep
    """
    @typechecked
    async def yield_input_chunks(self) -> InputChunk:
        """YIELDS: Chunks of input useful for association.
        """
        framing      = _RegionFraming()
        line_list    = []
        start_line_n = 1
        line_n       = 0

        def outer_chunk(end_line_n):
            return InputChunk_factory(E_Chunk.LINE_SEQUENCE, start_line_n,
                                      end_line_n, line_list, self.configuration)

        for line_n in count(1):
            line = await self.line_provider.readline()
            if not line:
                break

            line_class = classify(line, self.pf)

            if line_class is E_LineClass.REGION_BEGIN:
                if line_list:
                    yield outer_chunk(line_n)
                framing.open_shebang(line, line_n)
                line_list = []
            elif line_class is E_LineClass.REGION_END:
                framing.check_stray_end(line_n)
                yield framing.close(line, line_n, self.configuration, line_list)
                line_list    = []
                start_line_n = line_n
            else:
                # BLANK / IGNORED / CONTENT alike: kept for display.
                line_list.append(Line(line_n, line, self.pf))

        framing.check_eof(line_n)
        if line_list:
            yield outer_chunk(line_n)
