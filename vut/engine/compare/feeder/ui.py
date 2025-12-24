"""
PURPOSE:   Implementation of feeds for UIs in terms of DisplayInst objects.

SIGNATURE: 45C0FFBC

   This signature identifies the structure of the protocol. A receiver 
   may check the ProtocolHeader for this signature in order to be safe
   to be compliant.

NOTE: > python path/to/this/file.py 

        shows the protocol signature.

      > python path/to/this/file.py -w

        writes the protocol signature to "SIGNATURE_UI_PROTOCOL.txt" in
        the project root directory.
"""
from __future__ import annotations
import sys

import os

# Write code before further imports --> disable E402 code checker error
root_dir = os.path.dirname(__file__) + "/../../../.."
sys.path.insert(0, root_dir)

from   vut.engine.compare.main             import associate                   #noqa: E402
from   vut.engine.compare.engine.line_pair import SubjectCell, NominalCell    #noqa: E402

import zlib                                                                   #noqa: E402
from   inspect     import isclass                                             #noqa: E402
from   typing      import List, Any, AsyncIterable                            #noqa: E402
from   dataclasses import dataclass                                           #noqa: E402


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
    line_n_s: int
    line_n_n: int
    cells_s: List[SubjectCell]
    cells_n: List[NominalCell]
    cost: float
    s_char_n: int
    n_char_n: int
    source_ref: Any

@dataclass(frozen=True)
class EndOfStreamInst(DisplayInst):
    pass

async def feed(config, subject_stream, nominal_stream) -> AsyncIterable[DisplayInst]:
    """YIELDS: DisplayInst representing the line comparions.
    """
    # Associate produces the 'sleeping' Chunks/LinePairs
    raw_chunks = associate(config, subject_stream, nominal_stream)

    # Factory flushes them into 'awake' Instructions
    async for inst in DisplayInst_factory(config, raw_chunks):
        yield inst

@dataclass(frozen=True)
class ProtocolHeader(DisplayInst):
    """This instruction identifies the protocol convention. The signature
    uniquely determines the instructions and their content. As soon as one
    changes, the signature changes.

    This may be used by he receiver of the ProtocolHeader in order to 
    check whether he is setup correctly for receiption.

    NOTE: The current signature is presented on top of this file and can
          be produced by calling this file as script directly.
    """
    signature: str  # Hex representation of the hash (e.g., "1A2B3C4D")
    engine_id: str = "HWUT Version 2.0"

async def DisplayInst_factory(config, chunk_stream: AsyncIterable) -> AsyncIterable[DisplayInst]:
    """Transforms nested engine chunks into a flat sequence of Instructions.
    """

    # Provide information about the API version for the receiver to check
    yield ProtocolHeader(signature=_get_protocol_hash())

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
            yield LinePairInst(line_n_s   = lp.subject_line_n,
                               line_n_n   = lp.nominal_line_n,
                               cells_s    = lp.subject_list(),
                               cells_n    = lp.nominal_list(),
                               cost       = lp.cost,
                               s_char_n   = lp.subject_char_n,
                               n_char_n   = lp.nominal_char_n,
                               source_ref = lp)
            
    # 4. Final Flush
    yield EndOfStreamInst()

def _get_protocol_hash() -> str:
    """RETURNS: 32 hash as hex-string

    As soon as one member of a Inst-class changes, the receiver knows that it is not 
    compatible with the sendings.
    """
    # Collect all subclasses of DisplayInst
    inst_classes = [
        cls 
        for cls in globals().values() 
        if isclass(cls) and issubclass(cls, DisplayInst)
    ]
    
    # Sort by name to ensure deterministic hashing
    inst_classes.sort(key=lambda x: x.__name__)
    
    fingerprint = []
    for cls in inst_classes:
        # Get member names from the dataclass fields
        # DO NOT SORT, SO WE GET THEM IN THE DEFINITION ORDER!
        fields = list(cls.__dataclass_fields__.keys())
        fingerprint.append(f"{cls.__name__}({','.join(fields)})")
    
    protocol_str = "|".join(fingerprint)
    return hex(zlib.crc32(protocol_str.encode('utf-8')) & 0xFFFFFFFF).upper()[2:]


if __name__ == "__main__":
    # helper to provide a protocol hash
    ph = _get_protocol_hash()
    print("Protocol Hash: ", ph)
    if "-w" in sys.argv:
        with open(root_dir + "/vut/SIGNATURE_UI_PROTOCOL.txt", "w") as fh:
            fh.write(ph)
