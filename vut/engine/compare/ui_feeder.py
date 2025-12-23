from vut.engine.compare.main             import associate
from vut.engine.compare.engine.line_pair import SubjectCell, NominalCell
from enum        import Enum, auto
from dataclasses import dataclass, field
from typing      import List, Any

class E_DisplayCmd(Enum):
    SECTION_HEADER = auto()
    ROW_DATA       = auto()
    ROW_GAP        = auto()
    END_OF_STREAM  = auto()

@dataclass
class DisplayCmd:
    kind:       E_DisplayCmd
    text:       str = ""
    line_n_s:   str = ""
    line_n_n:   str = ""
    cells_s:    List[SubjectCell] = field(default_factory=list)
    cells_n:    List[NominalCell] = field(default_factory=list)
    source_ref: Any = None

async def ui_feeder(config, subject_stream, nominal_stream):
    """
    Consumes the engine's associate() generator and yields flat DisplayCmds.
    """
    async for chunk in associate(config, subject_stream, nominal_stream):
        # 1. Yield Header for the Chunk
        # (Identifying if it is a LineSequence or Potpourri)
        yield DisplayCmd(
            kind = E_DisplayCmd.SECTION_HEADER, 
            text = "/".join(ct.name for ct in chunk.types())
        )

        # 2. Yield individual line comparisons
        for line_pair in chunk:
            s_cells, n_cells = line_pair.subject_and_nominal_line_element_lists()

            yield DisplayCmd(kind       = E_DisplayCmd.ROW_DATA,
                             line_n_s   = -1 if line_pair.subject is None else line_pair.subject.line_n,
                             line_n_n   = -1 if line_pair.nominal is None else line_pair.nominal.line_n,
                             cells_s    = s_cells,
                             cells_n    = n_cells,
                             source_ref = line_pair)

        yield DisplayCmd(kind=E_DisplayCmd.ROW_GAP)

    yield DisplayCmd(kind=E_DisplayCmd.END_OF_STREAM)
