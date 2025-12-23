
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Any, AsyncIterable, Iterator
from vut.engine.compare.main import associate
from vut.engine.compare.engine.line_pair import SubjectCell, NominalCell

@dataclass(frozen=True)
class DisplayInst:
    """Base class for the immutable UI protocol."""
    pass

@dataclass(frozen=True)
class ConfigInst(DisplayInst):
    strip_whitespace_f: bool
    analogy_f: bool
    whitespace_f: bool
    backslash_f: bool
    numeric_tolerance_ratio: float
    ignored_line_begin_marker: str
    ignored_line_end_marker: str
    potpourri_begin_end_marker: str
    analogy_begin_marker: str
    analogy_end_marker: str

@dataclass(frozen=True)
class SectionBeginInst(DisplayInst):
    title: str
    chunk_type: str

@dataclass(frozen=True)
class LinePairInst(DisplayInst):
    line_n_s: str
    line_n_n: str
    cells_s: List[SubjectCell]
    cells_n: List[NominalCell]
    cost: float
    s_char_n: int
    n_char_n: int
    source_ref: Any

@dataclass(frozen=True)
class EndOfStreamInst(DisplayInst):
    pass

async def ui_feeder(config, subject_stream, nominal_stream) -> AsyncIterable[DisplayInst]:
    """Connects the engine to the factory.
    """
    # Associate produces the 'sleeping' Chunks/LinePairs
    raw_chunks = associate(config, subject_stream, nominal_stream)

    # Factory flushes them into 'awake' Instructions
    async for inst in DisplayInst_factory(config, raw_chunks):
        yield inst

async def DisplayInst_factory(config, chunk_stream: AsyncIterable) -> AsyncIterable[DisplayInst]:
    """Transforms nested engine chunks into a flat sequence of Instructions.
    """
    # 1. Flush the Configuration first (Snapshotting)
    pf = config.pattern_finder
    yield ConfigInst(
        strip_whitespace_f=pf.strip_whitespace_f,
        analogy_f=pf.analogy_f,
        whitespace_f=pf.whitespace_f,
        backslash_f=pf.backslash_f,
        numeric_tolerance_ratio=pf.numeric_tolerance_ratio,
        ignored_line_begin_marker=pf.ignored_line_begin_marker,
        ignored_line_end_marker=pf.ignored_line_end_marker,
        potpourri_begin_end_marker=pf.potpourri_begin_end_marker,
        analogy_begin_marker=pf.analogy_begin_marker,
        analogy_end_marker=pf.analogy_end_marker
    )

    async for chunk in chunk_stream:
        # 2. Flush the Section Header
        yield SectionBeginInst(
            title="/".join(ct.name for ct in chunk.types()),
            chunk_type=type(chunk).__name__
        )

        # 3. Flush the Content
        for lp in chunk:
            # Waking up the math: Tokenization happens HERE
            s_cells, n_cells = lp.subject_and_nominal_line_element_lists()

            yield LinePairInst(line_n_s   = -1 if lp.subject is None else lp.subject.line_n,
                               line_n_n   = -1 if lp.nominal is None else lp.nominal.line_n,
                               cells_s    = s_cells,
                               cells_n    = n_cells,
                               cost       = lp.cost,
                               s_char_n   = 0 if lp.subject is None else lp.subject.character_n(),
                               n_char_n   = 0 if lp.nominal is None else lp.nominal.character_n(),
                               source_ref = lp)
            
    # 4. Final Flush
    yield EndOfStreamInst()

