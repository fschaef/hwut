"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHAT THE LAST COVERAGE RUN CAME TO, PER CASE -- 'TEST/TMP/
         hwut-traces-coverage.csv' (coverage D-41).

    address   '<test directory>/TMP/hwut-traces-coverage.csv' -- under
              'TMP/', where every trace stands (bookkeeper B-28):
              LOCAL to this machine and ignored by git
    form      ';'-separated CSV with a header, as the book is
    key       test;choice
    columns   test;choice;outcome
    outcome   'ok' where the run left a record, else the
              'E_CoverageResult' token naming why it left none
    elision   an empty 'test' means THE ONE ABOVE; the rows are sorted
    growth    a row is REPLACED where its key stands: one row per case,
              of the LAST coverage run that selected it

IT IS A TRACE, NOT A RECORD. The coverage record ('.cover') is the
product of a coverage run and the only thing any measurement reads.
This table exists so that 'hwut.help' can say, after the terminal has
scrolled, WHICH cases were left without a record and WHY. It may be
deleted; a coverage run makes it again. Nothing decides anything by it.
______________________________________________________________________________
"""
import csv
import os

FILE_NAME    = "hwut-traces-coverage.csv"
SEPARATOR    = ";"
COLUMN_TUPLE = ("test", "choice", "outcome")
OUTCOME_OK   = "ok"


class CoverageTraceDb:
    """The coverage trace of one directory: read whole, changed, written
    whole."""

    def __init__(self, directory):
        """RETURN: CoverageTraceDb over the trace file of 'directory'."""
        self.path = os.path.join(str(directory), "TMP", FILE_NAME)

    def read(self):
        """
        RETURN: dict, (test, choice) -> outcome; 'choice' is '' for a
                test without choices. Empty where no file stands or it
                cannot be read: a trace is never worth a fault.
        """
        outcome_db = {}
        test       = None
        try:
            with open(self.path, "r", encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh, delimiter=SEPARATOR):
                    test = row.get("test") or test
                    if test is None: return {}
                    outcome_db[(test, row.get("choice", "") or "")] \
                        = row.get("outcome", "") or ""
        except (OSError, csv.Error, UnicodeDecodeError):
            return {}
        return outcome_db

    def note(self, outcome_db):
        """
        RETURN: None. Every '(test, choice) -> outcome' of 'outcome_db'
                is written, replacing what stood for that key; the
                other rows stay. Nothing is raised: a trace that cannot
                be written is not a fault of the run.
        """
        if not outcome_db: return
        merged_db = self.read()
        for (test, choice), outcome in outcome_db.items():
            merged_db[(test, choice or "")] = str(outcome)
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            temporary = self.path + ".tmp"
            with open(temporary, "w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh, delimiter=SEPARATOR,
                                    lineterminator="\n")
                writer.writerow(COLUMN_TUPLE)
                last_test = None
                for test, choice in sorted(merged_db):
                    writer.writerow(["" if test == last_test else test,
                                     choice, merged_db[(test, choice)]])
                    last_test = test
            os.replace(temporary, self.path)
        except OSError:
            pass
