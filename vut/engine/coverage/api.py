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
    snapshot_db_of, stale_tuple, gathered_index, bundle_of,
    read_bundle, write_bundle, BUNDLE_FILE, GatherFault
                        the gathered bundle: what a tree's coverage
                        adds up to, and where it is stale
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
from .database.api  import (BUNDLE_FILE, GatherFault, RecordFault,
                            bundle_of, format_record, gathered_index,
                            pack_record, parse_record, read_bundle,
                            seated, snapshot_db_of, stale_tuple,
                            unpack_record, write_bundle)
from .readers.api   import (CCoverageFormat, CCoverageFramework,
                            artifact_directory_of, elect, framework_of,
                            record_of, register, registered_tuple)

__all__ = ("BUNDLE_FILE", "CCoverageFormat", "CCoverageFramework",
           "CoverageConfig", "CoverageRefused", "GatherFault",
           "RecordFault", "artifact_directory_of", "bundle_of", "elect",
           "format_record", "framework_of", "gathered_index",
           "pack_record", "parse_record", "read_bundle", "record_of",
           "register",
           "registered_tuple", "seated", "snapshot_db_of",
           "stale_tuple", "unpack_record", "write_bundle")
