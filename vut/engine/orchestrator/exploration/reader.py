"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: One file through the reading pipeline:

    detect -> unwrap -> parse -> validate -> plain record

The parser is test-writing support and lives in 'language_support'; it
states its own faults. They are converted here into the engine's, one for
one, positions carried.

Faults are values; both a record and faults may come back from one file --
a header that parses but names an unknown key yields the record for the
keys that were good and a fault for the one that was not. Whether such a
record is usable is the explorer's call, not this reader's.
______________________________________________________________________________
"""
from vut.language_support.python import hwut_hocon

from .      import source_file_detector
from .      import unwrapper
from .      import validator
from .fault import Fault, E_FaultKind, Position


def read_header(text, file):
    """
    RETURN: [0] TestAppSpec | None, the file's specification; None where
                the file carries no region or nothing usable.
            [1] list[Fault], every fault found; empty for a file that is
                simply not a test application.
    """
    region = source_file_detector.detect(text)
    if region is None: return None, []

    line_list             = unwrapper.unwrap(text, region)
    document, parse_faults = hwut_hocon.parse(line_list, file)
    fault_list             = [_converted(f) for f in parse_faults]

    hwut_node = validator.document_hwut_node(document, file, fault_list)
    if hwut_node is None: return None, fault_list

    spec, more = validator.validate_header(hwut_node, file)
    fault_list.extend(more)
    return spec, fault_list


def read_conf(text, file):
    """
    RETURN: [0] DirectorySpec | None, the directory's own keys.
            [1] dict, source file name -> TestAppSpec (origin CONF).
            [2] list[Fault], every fault found.
    """
    line_list             = unwrapper.plain_lines(text)
    document, parse_faults = hwut_hocon.parse(line_list, file)
    fault_list             = [_converted(f) for f in parse_faults]

    hwut_node = validator.document_hwut_node(document, file, fault_list)
    if hwut_node is None: return None, {}, fault_list

    spec, app_db, more = validator.validate_conf(hwut_node, file)
    fault_list.extend(more)
    return spec, app_db, fault_list


def _converted(parse_fault):
    """
    RETURN: Fault, the parser's own fault record said in the engine's
            vocabulary; kind, file, position and message carried over.
    """
    return Fault(kind     = E_FaultKind[parse_fault.kind.name],
                 file     = parse_fault.file,
                 position = Position(parse_fault.position.line,
                                     parse_fault.position.column),
                 message  = parse_fault.message)
