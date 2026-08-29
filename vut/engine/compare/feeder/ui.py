"""
PURPOSE:   Implementation of feeds for UIs in terms of DisplayInst objects.

SIGNATURE: mmiFiE-j4bsvTLp0iGNZEAJF9GErpfkXjVZc9Xw0yi8

   This signature identifies the structure of the protocol. A receiver 
   may check the ProtocolHeader for this signature in order to be safe
   to be compliant.

NOTE: > python path/to/this/file.py 

        shows the protocol signature.

      > python path/to/this/file.py -w

        writes the protocol signature to "<root>/adm/SIGNATURE_UI_PROTOCOL.txt" in
        the project root directory.
"""
from __future__ import annotations
import sys

import os

# Write code before further imports --> disable E402 code checker error
root_dir = os.path.dirname(__file__) + "/../../../.."
sys.path.insert(0, root_dir)

import vut.adm.version                         as     version         #noqa: E402
import vut.engine.compare.main                 as     main            #noqa: E402
from   vut.engine.compare.core.line_pair       import (LinePair,      #noqa: E402
                                                       LineNumberPair,
                                                       NominalCell,
                                                       SubjectCell)
from   vut.engine.compare.core.chunk_pair      import ChunkPair       #noqa: E402
from   vut.engine.compare.reading.line_element import E_ToleranceId   #noqa: E402

from   inspect     import isclass                   #noqa: E402
from   typing      import List, AsyncIterable  #noqa: E402
from   dataclasses import dataclass                 #noqa: E402
import hashlib                                      #noqa: E402
import base64                                       #noqa: E402
from   bidict      import bidict                    #noqa: E402

class AnalogyProvenanceDb(bidict):
    """Bidirectional mapping for analogies that also tracks the line numbers 
    where each relationship was first established.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Internal map: (subject, nominal) -> (s_line_n, n_line_n)
        self._provenance = {}

    def update(self, chunk_pair: ChunkPair):
        """
        Scans a ChunkPair for analogy cells and records new sightings.
        """
        for lp in chunk_pair:
            if lp.subject_line_n == -1 or lp.nominal_line_n == -1: 
                continue
            cells_s, cells_n = lp.subject_list(), lp.nominal_list()
            for sc, nc in zip(cells_s, cells_n, strict=False):
                if sc.tolerance_id is not E_ToleranceId.ANALOGY: 
                    continue
                s_val, n_val = sc.subject, nc.nominal
                if s_val is None or n_val is None:                    # no anology claimed
                    continue
                elif (s_val, n_val) in self._provenance:              # already recorded
                    continue
                elif s_val not in self and n_val not in self.inverse: # 1:1 check
                    self[s_val] = n_val
                    self._provenance[(s_val, n_val)] = (lp.subject_line_n, lp.nominal_line_n)

    def get_origin(self, s_val, n_val):
        """Returns (s_line, n_line) if known, else (None, None)."""
        return self._provenance.get((s_val, n_val), (None, None))

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

@dataclass(frozen=True)
class EndOfStreamInst(DisplayInst):
    pass

@dataclass(frozen=True)
class ProtocolHeader(DisplayInst):
    signature:    str
    hwut_version: str = version.string

async def feed(config, subject_stream, nominal_stream) -> AsyncIterable[DisplayInst]:
    """YIELDS: DisplayInst for display of the line comparison."""

    yield ProtocolHeader(signature=_get_protocol_hash())

    pf = config.pattern_finder
    yield ConfigInst(strip_whitespace_f         = pf.strip_whitespace_f,
                     analogy_f                  = pf.analogy_f,
                     whitespace_f               = pf.whitespace_f,
                     backslash_f                = pf.backslash_f,
                     numeric_tolerance_ratio    = pf.numeric_tolerance_ratio,
                     ignored_line_begin_marker  = pf.ignored_line_begin_marker,
                     ignored_line_end_marker    = pf.ignored_line_end_marker,
                     analogy_begin_marker       = pf.analogy_begin_marker,
                     analogy_end_marker         = pf.analogy_end_marker)

    prov_db = AnalogyProvenanceDb()

    async for chunk in main.associate(config, subject_stream, nominal_stream):
        # 1. Update global provenance with current chunk data
        prov_db.update(chunk)

        yield SectionBeginInst(title      = "/".join(ct.name for ct in chunk.types()),
                               chunk_type = type(chunk).__name__)

        for line_pair in chunk:
            # 2. Bake provenance info into the instruction cells
            baked_lp_inst = bake_line_pair_inst(line_pair, prov_db)
            yield baked_lp_inst
            
    yield EndOfStreamInst()

def bake_line_pair_inst(lp: LinePair, prov_db: AnalogyProvenanceDb) -> LinePairInst:
    """Transforms an engine LinePair into a protocol LinePairInst with baked info."""
    engine_cells_s = lp.subject_list()
    engine_cells_n = lp.nominal_list()
    
    baked_s = []
    baked_n = []

    # Process Subject Cells
    for sc in engine_cells_s:
        lnp = None
        if sc.tolerance_id == E_ToleranceId.ANALOGY and sc.subject:
            # Look up current mapping in this specific line pair
            current_n = engine_cells_n[sc.nominal_ref_i].nominal
            
            # Case A: Perfect match found in provenance
            s_orig, n_orig = prov_db.get_origin(sc.subject, current_n)
            
            if s_orig is not None:
                lnp = LineNumberPair(s_orig, n_orig)
            elif n_orig is not None:
                # Conflict case: subject is mapped to something else in prov_db
                established_n = prov_db.get(sc.subject)
                if established_n is not None:
                    s_orig_c, n_orig_c = prov_db.get_origin(sc.subject, established_n)
                    lnp = LineNumberPair(s_orig_c, n_orig_c)

        baked_s.append(SubjectCell(
            relation_id   = sc.relation_id,
            tolerance_id  = sc.tolerance_id,
            subject       = sc.subject,
            nominal_ref_i = sc.nominal_ref_i,
            analogy_origin_line_number_pair = lnp
        ))

    # Process Nominal Cells
    for nc in engine_cells_n:
        lnp = None
        if nc.tolerance_id == E_ToleranceId.ANALOGY and nc.nominal:
            current_s = engine_cells_s[nc.subject_ref_i].subject
            
            # Case A: Perfect match
            s_orig, n_orig = prov_db.get_origin(current_s, nc.nominal)
            
            if s_orig is not None:
                lnp = LineNumberPair(s_orig, n_orig)
            else:
                # Case B: Nominal was established with a DIFFERENT subject (Reverse Conflict)
                established_s = prov_db.inverse.get(nc.nominal)
                if established_s is not None:
                    s_orig_c, n_orig_c = prov_db.get_origin(established_s, nc.nominal)
                    lnp = LineNumberPair(s_orig_c, n_orig_c)

        baked_n.append(NominalCell(
            relation_id   = nc.relation_id,
            tolerance_id  = nc.tolerance_id,
            nominal       = nc.nominal,
            subject_ref_i = nc.subject_ref_i,
            analogy_origin_line_number_pair = lnp
        ))

    return LinePairInst(
        line_n_s   = lp.subject_line_n,
        line_n_n   = lp.nominal_line_n,
        cells_s    = baked_s,
        cells_n    = baked_n,
        cost       = lp.cost,
    )

def _get_protocol_hash() -> str:
    """RETURNS: 256-bit SHA-256 hash of the protocol structure as base64"""
    inst_classes = [
        obj for obj in globals().values() 
        if isclass(obj) and issubclass(obj, (DisplayInst, SubjectCell, NominalCell)) 
        and obj not in (DisplayInst, SubjectCell, NominalCell)
    ]
    # We explicitly add the baked cells to the hash calculation
    inst_classes.extend([SubjectCell, NominalCell])
    inst_classes = list(set(inst_classes))
    inst_classes.sort(key=lambda x: x.__name__)

    protocol_strs = []
    for cls in inst_classes:
        fields = cls.__dataclass_fields__.keys()
        protocol_strs.append(f"{cls.__name__}({','.join(fields)})")
    
    fingerprint = "|".join(protocol_strs).encode('utf-8')
    raw_hash = hashlib.sha256(fingerprint).digest()
    return base64.urlsafe_b64encode(raw_hash).decode('utf-8').rstrip('=')

# BEGIN: DO NOT REMOVE THIS!
#
# This code is used to produce a 'protocol hash', i.e. something that allows the 
# receiver to verify that it is parsing content of a compliant version.
#
if __name__ == "__main__":
    # helper to provide a protocol hash
    ph = _get_protocol_hash()
    print("Protocol Hash: ", ph)
    repo_root_dir = os.path.dirname(__file__) + "/../../.."
    if "-w" in sys.argv:
        with open(repo_root_dir + "/adm/SIGNATURE_UI_PROTOCOL.txt", "w") as fh:
            fh.write(ph)
# END: DO NOT REMOVE THIS!
