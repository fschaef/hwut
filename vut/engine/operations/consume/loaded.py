"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE LOADED SUBJECTS -- a stored run, read back for consumption.

DESCRIPTION
       THE RECORDED-STREAM BRANCH OF PROVISION (disc-2): nothing
       executes, nothing is contained, there is no attribution to
       make. The channel ('subject_provision.provider_of') hands out a
       'Loaded' provider over this reader whenever its decision is
       RECORDED, STALE or ABSENT; the provider reads what a run
       RECORDED, through the Store's candidate paths (the Bookkeeper's
       naming), and delivers the SAME 'Subjects' shape an execution
       delivers, so nothing downstream ever asks which one it got.
       No face calls this module directly.

       A STORED SUBJECT IS ALREADY CANONICAL (run/core.py): pype is
       part of execution; the consumer never canonicalises.

       NOTHING IS INVENTED: an absent recording stands in the delivery
       as a reader that REPORTS its absence when opened
       ('RecordNominal', nominal.py) -- never an empty subject that
       would be compared and called a difference. That law came here
       from the load stage the surgery removed.
______________________________________________________________________________
"""
from ..nominal  import RecordNominal
from ..result   import E_TestRunResult
from ..report   import Provision as ProvisionRecord
from ..run.core import Subjects


def loaded(store, test_name, choice_name=None, subject_name_list=None):
    """
    RETURN: Subjects, the recorded candidates of that key, read back --
            one reader per named subject; where ANY named subject has
            no recording, the delivery is EMPTY and the report says
            'RECORDING_MISSING': absence is reported, never invented
            as an empty subject.

    'subject_name_list' None means: the standard pair, 'stdout' and
    'stderr'.
    """
    if subject_name_list is None:
        subject_name_list = ("stdout", "stderr")
    path_db = {name: store.candidate_path(test_name, choice_name, name)
               for name in subject_name_list}
    if not all(path.exists() for path in path_db.values()):
        return Subjects({}, ProvisionRecord(
                                report=E_TestRunResult.RECORDING_MISSING))
    reader_db = {name: RecordNominal(path)
                 for name, path in path_db.items()}
    return Subjects(reader_db,
                    ProvisionRecord(report=E_TestRunResult.OK))
