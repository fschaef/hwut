"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE LOAD STAGE -- the subject comes to exist from the store.

DESCRIPTION
       One stage of provision (see provision/core.py): what a run
       recorded, read back. The OTHER path -- a provision either runs
       or loads, never both.
______________________________________________________________________________
"""
from   ..result  import E_TestRunResult
from   ..nominal import BytesNominal
from   .core     import (Supply,
                         STDOUT, STDERR)


class StageLoad:
    """THE SUBJECT comes to exist from the STORE: what a run recorded,
    read back. Nothing executes, nothing is contained, there is no
    attribution to make -- and NOTHING IS INVENTED: an absent recording
    is REPORTED, never an empty subject that would be compared and
    called a difference.

    Reads the store keys and NONE of the source, build, place or caps
    keys.
    """

    def __init__(self, store, test_name, choice_name=None,
                 subject_name_list=None):
        self.store             = store
        self.test_name         = test_name
        self.choice_name       = choice_name
        self.subject_name_list = subject_name_list

    async def supply(self, stop_event=None):
        """
        RETURN: Supply, product = readers over the stored candidates;
                product None with 'recording-missing' when NOTHING was
                stored -- an absent recording is REPORTED, never an
                empty subject.
        """
        name_list = self.subject_name_list
        if name_list is None:
            name_list = [STDOUT, STDERR]

        reader_db = {}
        for name in name_list:
            candidate = self.store.candidate(self.test_name,
                                             self.choice_name, name)
            if not candidate.exists():
                continue
            with candidate.open() as reader:
                reader_db[name] = BytesNominal(reader.read(), name=name)

        if not reader_db:
            return Supply(product = None,
                          report  = E_TestRunResult.RECORDING_MISSING)
        return Supply(product=reader_db)
