"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE: KCOV, DRIVEN -- a tool hwut CALLS (coverage D-46), first for
         bash. It writes Cobertura, which 'cobertura.py' reads.
DESCRIPTION
       KCOV SITS BEFORE THE APPLICATION, as coverage.py does:

           kcov --include-path=<include> --exclude-pattern=/OUT/COVERAGE/
                OUT/COVERAGE  ./test-x.sh <choice>

       It traces a bash script through bash's own debug trap (a compiled
       program through its DWARF information) and leaves, under the
       output directory it is given, one directory per run and one merged
       one:

           OUT/COVERAGE/
             test-x.sh.<hash>/   cobertura.xml  <- what is read
             kcov-merged/        cobertura.xml  (not always written;
                                                 the same counts again)

       THE ARTEFACT IS ONE LEVEL DOWN. The Cobertura reader reads the
       '.xml' standing in 'OUT/COVERAGE' itself; 'harvest' therefore
       copies each run's 'cobertura.xml' up beside it before reading --
       the tool's own file, unchanged, in the place the format looks.

       KCOV READS THE WHOLE SCRIPT DIRECTORY unless told not to: by
       default it parses every file beside the script for shell code and
       reports each -- 44 'sources' for one test of 'demo/bash', the
       '.err' witnesses and GOOD files among them (measured 2026-11-26).
       '--bash-dont-parse-binary-dir' reports what ran.

       KCOV MEASURES ITS OWN HELPERS. Its bash helper scripts
       ('bash-helper.sh', 'bash-helper-debug-trap.sh') are written into
       the output directory and reported as 0% classes (witnessed
       2026-08-24 and 2026-11-26). '--exclude-pattern=/OUT/COVERAGE/'
       keeps them out of the measurement.

       WHAT ARRIVES: lines. kcov reports 'branches-valid="0"' for bash,
       and the Cobertura reader keeps no branch data (D-43) -- so the
       format's 'measure_tuple' stays (), and the menu marker (D-50)
       says so at every bash file of a page that has a branch column.

       WITNESSED 2026-11-26: kcov 'bbaa197' (built from source; Ubuntu
       24.04 packages none), over 'REAL_PARSING_INPUT/cobertura/
       kcov-shell.xml'-shaped output, and through 'hwut.cov.run' on
       'support/demo/bash'.
______________________________________________________________________________
"""
import os
import shutil

from .cobertura import CoberturaFormat
from .reader    import (ARTIFACT_DIRECTORY, CCoverageFramework,
                        artifact_directory_of, register)

#  WHERE KCOV WRITES: the artefact directory itself, which hwut makes
#  and empties before each run (D-22); kcov does not make a nested
#  output path (measured: "Can't open directory OUT/COVERAGE/kcov/").
#  The call runs in the test directory, so the path is relative.


class KcovFramework(CCoverageFramework):
    """kcov: invocation (call scheme); reads CoberturaFormat (module
    header)."""
    name   = "kcov"
    format = CoberturaFormat()
    offered_format_tuple = (format.name,)          # D-49

    #  KCOV RUNS THE SCRIPT ITSELF: no interpreter before '{test}'; the
    #  script is executable, as every hwut test application is.
    call_scheme = ("kcov --bash-dont-parse-binary-dir "
                   "--include-path={include} --exclude-path={omit} "
                   "--exclude-pattern=/%s/ %s {test} {choice}"
                   % (ARTIFACT_DIRECTORY, ARTIFACT_DIRECTORY))

    def specify_command_line(self, included_paths, omitted_paths,
                             test_app, choice, format_name=None):
        """
        RETURN: list[str], the call (base), with a bare script name made
                a path: kcov STARTS the program it is given, and a word
                without a '/' it looks up on PATH -- 'chamber.sh' is not
                found there, './chamber.sh' is (measured 2026-11-26:
                "Can't start/attach to chamber.sh").
        """
        if test_app is not None and "/" not in str(test_app) \
           and " " not in str(test_app):
            test_app = "./%s" % test_app
        return CCoverageFramework.specify_command_line(
                   self, included_paths, omitted_paths, test_app, choice,
                   format_name)

    def harvest(self, work_dir, source_root, config=None):
        """
        RETURN: CoverageRecord, the Cobertura document(s) kcov left for
                its run(s), read by the format with 'kcov' stamped as
                its tool
                None, where kcov left none -- ABSENT.

        Each '<program>.<hash>/cobertura.xml' is copied, unchanged, into
        'OUT/COVERAGE/' where the format reads (module header);
        'kcov-merged/' is not, being the same counts again.
        """
        directory = artifact_directory_of(work_dir)
        found     = 0
        for name in sorted(os.listdir(directory)) \
                    if os.path.isdir(directory) else ():
            source = os.path.join(directory, name, "cobertura.xml")
            if name == "kcov-merged" or not os.path.isfile(source):
                continue
            found += 1
            shutil.copyfile(source, os.path.join(directory,
                                                 "kcov-%i.xml" % found))
        if not found: return None
        return CCoverageFramework.harvest(self, work_dir, source_root,
                                          config)


register(KcovFramework())
