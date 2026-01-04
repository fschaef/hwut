"""
PURPOSE:   Implementation of feeds for UIs in terms of DisplayInst objects.

SIGNATURE: PINlmBykR6RHn-GsYqZNbDJpcdYgmese_FAukpt54bc

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

import vut.version                                     as     version                            #noqa: E402
import vut.engine.compare.main                         as     main                               #noqa: E402
from   vut.engine.compare.engine.association.line_pair import LinePair, SubjectCell, NominalCell #noqa: E402

from   inspect     import isclass                                             #noqa: E402
from   typing      import List, Any, AsyncIterable                            #noqa: E402
from   dataclasses import dataclass                                           #noqa: E402
import hashlib                                                                #noqa: E402
import base64                                                                 #noqa: E402

@dataclass(frozen=True)
class DisplayInst:
    """Base class for the immutable UI protocol."""
    pass

@dataclass(frozen=True)
class ConfigInst(DisplayInst):
    strip_whitespace_f:         bool
    analogy_f:                  bool
    whitespace_f:               bool
    backslash_f:                bool
    numeric_tolerance_ratio:    float
    ignored_line_begin_marker:  str
    ignored_line_end_marker:    str
    potpourri_begin_end_marker: str
    analogy_begin_marker:       str
    analogy_end_marker:         str

@dataclass(frozen=True)
class SectionBeginInst(DisplayInst):
    title:      str
    chunk_type: str

@dataclass(frozen=True)
class LinePairInst(DisplayInst):
    line_n_s:   int
    line_n_n:   int
    cells_s:    List[SubjectCell]
    cells_n:    List[NominalCell]
    cost:       float
    s_char_n:   int
    n_char_n:   int
    source_ref: Any

    @classmethod
    def from_LinePair(cls, lp: LinePair):
        return cls(line_n_s   = lp.subject_line_n,
                   line_n_n   = lp.nominal_line_n,
                   cells_s    = lp.subject_list(),
                   cells_n    = lp.nominal_list(),
                   cost       = lp.cost,
                   s_char_n   = lp.subject_char_n,
                   n_char_n   = lp.nominal_char_n,
                   source_ref = lp)

@dataclass(frozen=True)
class EndOfStreamInst(DisplayInst):
    pass

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
    signature:    str  # Hex representation of the hash (e.g., "1A2B3C4D")
    hwut_version: str = version.string

async def feed(config, subject_stream, nominal_stream) -> AsyncIterable[DisplayInst]:
    """YIELDS: DisplayInst for display of the line comparison.

    Transforms nested engine chunks into a flat sequence of Instructions.
    """

    # Provide information about the API version for the receiver to check
    yield ProtocolHeader(signature=_get_protocol_hash())

    # Configuration first (Snapshotting)
    pf = config.pattern_finder
    yield ConfigInst(strip_whitespace_f         = pf.strip_whitespace_f,
                     analogy_f                  = pf.analogy_f,
                     whitespace_f               = pf.whitespace_f,
                     backslash_f                = pf.backslash_f,
                     numeric_tolerance_ratio    = pf.numeric_tolerance_ratio,
                     ignored_line_begin_marker  = pf.ignored_line_begin_marker,
                     ignored_line_end_marker    = pf.ignored_line_end_marker,
                     potpourri_begin_end_marker = pf.potpourri_begin_end_marker,
                     analogy_begin_marker       = pf.analogy_begin_marker,
                     analogy_end_marker         = pf.analogy_end_marker)

    # Associate produces the 'sleeping' Chunks/LinePairs
    async for chunk in main.associate(config, subject_stream, nominal_stream):
        # Flush the Section Header
        yield SectionBeginInst(title      = "/".join(ct.name for ct in chunk.types()),
                               chunk_type = type(chunk).__name__)

        # Flush the Content
        for line_pair in chunk:
            yield LinePairInst.from_LinePair(line_pair)
            
    # Notify Termination
    yield EndOfStreamInst()

def _get_protocol_hash() -> str:
    """RETURNS: 256-bit SHA-256 hash of the protocol structure as base64
    """
    # 1. Gather the instruction classes as before
    inst_classes = [
        obj for obj in globals().values() 
        if isclass(obj) and issubclass(obj, DisplayInst) and obj is not DisplayInst
    ]
    inst_classes.sort(key=lambda x: x.__name__)

    # 2. Build the structural fingerprint
    protocol_strs = []
    for cls in inst_classes:
        fields = cls.__dataclass_fields__.keys()
        protocol_strs.append(f"{cls.__name__}({','.join(fields)})")
    
    fingerprint = "|".join(protocol_strs).encode('utf-8')

    # 3. Hash to 256-bit (32 bytes)
    raw_hash = hashlib.sha256(fingerprint).digest()

    # 4. Encode to Base64
    # We use urlsafe_b64encode to avoid '+' and '/' which can be annoying in URIs/logs
    b64_signature = base64.urlsafe_b64encode(raw_hash).decode('utf-8').rstrip('=')
    
    return b64_signature

# BEGIN: DO NOT REMOVE THIS!
#
# This code is used to produce a 'protocol hash', i.e. something that allows the 
# receiver to verify that it is parsing content of a compliant version.
#
if __name__ == "__main__":
    # helper to provide a protocol hash
    ph = _get_protocol_hash()
    print("Protocol Hash: ", ph)
    if "-w" in sys.argv:
        with open(root_dir + "/vut/SIGNATURE_UI_PROTOCOL.txt", "w") as fh:
# END: DO NOT REMOVE THIS!
            fh.write(ph)
