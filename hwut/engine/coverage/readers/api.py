"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE DOOR into 'engine/coverage/readers'. The rest of the
         coverage component -- 'core.py' and the outer 'api.py' --
         reaches the registry and the reader roles through this module and
         through no other.

    language_of, serving_framework
                            the registry: language stated or derived,
                            the ONE tool a language names (D-46)
    callable_tuple         the tools hwut drives
    format_named           a registered format by its name (D-50)
    CCoverageFormat, CCoverageFramework
                            the two roles a new tool implements: the
                            artefact (reading) and the tool
                            (invocation)
    ARTIFACT_DIRECTORY     where a run's own artefact lands, relative
                            to the test directory
    framework_of, registered_tuple, artifact_directory_of,
    record_of, register
                            the tool -> framework registry, and how an
                            entry becomes a record -- the integration
                            seam for a new reader

IMPORTING 'readers' (the package, via '__init__.py') REGISTERS EVERY
READER; THIS DOOR DOES NOT. A caller that only resolves a tool, without ever
reading an artefact, imports this module and pays for no format's
tooling.

NOT RE-EXPORTED HERE: 'core.py' imports a name 'reader_of' that this
module does not define, because 'reader.py' has never defined one --
'framework_of' is the function the rest of this file's own comments
describe under that name. Pre-existing, found while wiring this door,
not introduced by it; left exactly as it stood rather than silently
corrected. See the session's report.

IT HOLDS NOTHING OF ITS OWN -- imports and '__all__'.

THE RULE IS EXECUTABLE: 'adm/LAYERING.txt' names this module in a
'DOOR' line. The component's own suites are inside the wall.
______________________________________________________________________________
"""
from .reader   import (ARTIFACT_DIRECTORY, CCoverageFormat,
                       CCoverageFramework, artifact_directory_of,
                       callable_tuple, format_named, framework_of,
                       record_of, register, registered_tuple)
from .registry import language_of, serving_framework

__all__ = ("ARTIFACT_DIRECTORY", "CCoverageFormat", "CCoverageFramework",
           "artifact_directory_of", "callable_tuple", "format_named",
           "framework_of",
           "language_of", "record_of", "register", "registered_tuple",
           "serving_framework")
