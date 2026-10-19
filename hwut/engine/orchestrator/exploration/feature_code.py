"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHERE A FEATURE IS EXERCISED IN THE CODE -- the source ranges
         its linked test runs executed, read from the output of a
         'hwut.cov.run'.

    code_db_of(relation, root, output_directory)
        -> {(TEST directory path, feature key): CFeatureCode}

DESCRIPTION
       A coverage output says, for every range of every source file,
       WHICH TEST RUNS executed it. A feature's linked test runs are a
       set of runs; so each range falls, for that feature, into one of

           only     every run that executed it is linked to the feature
           shared   runs linked to the feature executed it, and runs
                    that are not linked to it did so too
           (else)   none of the feature's runs executed it

       'only' is the hint: code nothing else in the measured suite
       reaches. 'shared' is mostly what every run passes through -- the
       start-up, the reading of arguments -- and is counted, not listed.

       A HINT, NOT A PROOF. The ranges say where the feature's runs
       WENT, which is where a reader starts looking; that the feature is
       IMPLEMENTED there is the reader's conclusion.

       THE TEST APPLICATIONS' OWN LINES ARE LEFT OUT: a source file
       standing in a TEST directory is a test, and every test's lines
       are executed by its own runs only.

       A LINKED RUN THE OUTPUT DOES NOT HOLD was not measured -- the
       coverage run did not select it, or it was linked since.
       'unmeasured_n' counts them; with none measured there is no hint.
______________________________________________________________________________
"""
import os
from   dataclasses import dataclass

from ...coverage.api import Output, root_of, union


@dataclass(frozen=True)
class CFeatureCode:
    """Where one feature's linked runs went. 'only_tuple' holds
    (source, tuple of half-open (begin, end) line ranges, measured
    source), path order: 'source' named from the directory the relation
    was asked in, 'measured source' as the coverage output names it --
    from the coverage run's root, which is where its pages stand."""
    only_tuple:    tuple = ()
    shared_file_n: int   = 0
    shared_line_n: int   = 0
    measured_n:    int   = 0       # linked runs the output holds
    unmeasured_n:  int   = 0       # linked runs it does not


def code_db_of(relation, root, output_directory, run_db=None):
    """
    RETURN: dict, (TEST directory path, feature key) -> CFeatureCode,
            for every feature of 'relation' that has a linked run --
            'root' the directory the relation was asked in,
            'output_directory' a coverage run's output
            None, the output names no root it measured

    'run_db' (TEST directory path, feature key) -> the runs of a feature
    where they are more than its own directory's: a link by internal id
    from another one (the book's D-8), the run carrying its 'path'.

    Raises OutputRefused where the output cannot be read.
    """
    coverage_root = root_of(output_directory)
    if coverage_root is None: return None
    output   = Output(output_directory)
    test_set = set(os.path.normpath(os.path.join(root, path))
                   for path in relation.test_directory_db)

    #  THE LINE AXIS, READ ONCE: per source outside every TEST
    #  directory, its ranges by the set of runs that executed them.
    source_list = []
    for source, _, covered in output.source_iterable():
        where = os.path.dirname(os.path.normpath(
                    os.path.join(coverage_root, source)))
        if where in test_set: continue
        #  NAMED AS THE RELATION NAMES ITS DIRECTORIES: from 'root'.
        shown = os.path.relpath(os.path.join(coverage_root, source),
                                root).replace(os.sep, "/")
        source_list.append((shown, [(output.run_set_of(reference), spans)
                                    for reference, spans in covered],
                            source))
    source_list.sort(key=lambda triple: triple[0])

    result = {}
    for path, test_directory in relation.test_directory_db.items():
        directory = os.path.relpath(
            os.path.normpath(os.path.join(root, path)),
            coverage_root).replace(os.sep, "/")
        for state in test_directory.state_tuple:
            run_tuple = state.run_tuple if run_db is None \
                        else run_db.get((path, state.feature.key),
                                        state.run_tuple)
            if not run_tuple: continue
            id_set = set()
            for run in run_tuple:
                where = directory if run.path is None else os.path.relpath(
                    os.path.normpath(os.path.join(root, run.path)),
                    coverage_root).replace(os.sep, "/")
                run_id = output.run_db.get((where, run.test, run.choice))
                if run_id is not None: id_set.add(run_id)
            result[(path, state.feature.key)] = _code_of(
                source_list, id_set, len(run_tuple) - len(id_set))
    return result


def _code_of(source_list, id_set, unmeasured_n):
    """RETURN: CFeatureCode, the ranges of 'source_list' against the run
    ids 'id_set' of one feature."""
    if not id_set: return CFeatureCode(unmeasured_n=unmeasured_n)
    only_list, shared_file_n, shared_line_n = [], 0, 0
    for source, covered, measured in source_list:
        only, shared = (), ()
        for run_set, spans in covered:
            if not run_set & id_set: continue
            if run_set <= id_set: only   = union(only, spans)
            else:                 shared = union(shared, spans)
        if only: only_list.append((source, tuple(only), measured))
        if shared:
            shared_file_n += 1
            shared_line_n += sum(end - begin for begin, end in shared)
    return CFeatureCode(tuple(only_list), shared_file_n, shared_line_n,
                        len(id_set), unmeasured_n)
