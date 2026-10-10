"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE DOOR into 'engine/coverage'. Everything outside the
         component reaches it through this module and through no other.

    CoverageConfig      WHAT A COVERAGE RUN IS TOLD: what it gathers
                        ('include', 'omit', 'counts'). WHICH TOOL and
                        WHICH LANGUAGE are not here -- they are the
                        root conf's word (D-26)
    CoverageRefused     the run cannot be made: no tool, an empty
                        candidate list, a language nobody can derive
    elect               the first candidate tool this machine has
    framework_of        the reader that speaks a tool's format
    registered_tuple    every tool this build can read
    artifact_directory_of
                        where a run's coverage artefacts land
    pack_record, unpack_record, format_record, seated, RecordFault
                        the record: its binary form, its text form,
                        its seating under a run id, its fault
    GatheredFile, pack_gathered, unpack_gathered, format_gathered,
    parse_gathered, binary_version
                        a coverage file of the output directory, record
                        version 3, in both spellings (D-43)
    prepared, gather, Output, root_of, DEFAULT_DIRECTORY_NAME,
    id_text, measure_db_of, measure_of, name_tuple, subtract, union,
    OutputRefused
                        the output directory of a coverage run: the
                        test run ids, the groups, and one annotated
                        coverage file per source file (D-42)
    CoverageTraceDb, OUTCOME_OK
                        the local trace of the last coverage run (D-41)
    CCoverageFormat, CCoverageFramework, register, record_of
                        what a NEW TOOL implements, how it says so, and
                        how it turns entries into a record -- the
                        integration seam

A CONFIGURATION CONFIGURES A COMPONENT, SO IT STANDS ON THE
COMPONENT'S DOOR. 'CoverageConfig' is that type here; a caller cannot
ask for coverage without building one, and the door owes it to them.

IT HOLDS NOTHING OF ITS OWN -- imports and '__all__'.

SUBSTITUTE AT THE DOOR. A re-export binds its names once, at import.
A test replacing a class must replace it here, since this is what the
product reads; patching the module behind the door leaves the door
holding the original.

THE RULE IS EXECUTABLE: 'adm/LAYERING.txt' names this module in a
'DOOR' line. The component's own suites are inside the wall.
______________________________________________________________________________
"""
from .configuration import CoverageConfig, CoverageRefused
from .database.api  import (GatheredFile, RecordFault, binary_version,
                            format_gathered, format_record, pack_gathered,
                            pack_record, parse_gathered, parse_record,
                            id_text, measure_db_of, measure_of, name_tuple,
                            seated, subtract, unpack_gathered, union,
                            unpack_record)
from .readers.api   import (CCoverageFormat, CCoverageFramework,
                            artifact_directory_of, elect, framework_of,
                            record_of, register, registered_tuple)
from .trace         import OUTCOME_OK, CoverageTraceDb
from .affected      import main as affected_main
from .output        import (DEFAULT_DIRECTORY_NAME, MARKER_FILE, Output,
                            OutputRefused, gather, prepared, root_of)

__all__ = ("affected_main", "DEFAULT_DIRECTORY_NAME", "GatheredFile",
           "MARKER_FILE", "Output",
           "OutputRefused", "binary_version", "format_gathered",
           "pack_gathered", "parse_gathered", "unpack_gathered",
           "id_text", "measure_db_of", "measure_of", "name_tuple",
           "subtract", "union",
           "gather", "prepared", "root_of",
           "CCoverageFormat", "CCoverageFramework", "CoverageConfig",
           "CoverageRefused", "CoverageTraceDb", "OUTCOME_OK",
           "RecordFault", "artifact_directory_of", "elect",
           "format_record", "framework_of", "pack_record",
           "parse_record", "record_of", "register",
           "registered_tuple", "seated", "unpack_record")
