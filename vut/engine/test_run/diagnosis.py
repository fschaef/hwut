"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       DIAGNOSIS -- every silent failure names itself (todo-21).

DESCRIPTION
       Earned by a real evening (DISCUSSIONS todo-21): a runner answered
       a broken interview with an empty string, discarding the exit
       code, the containment, and the channel that held the entire
       answer. The framework HOLDS every such fact by construction --
       ProcsitterResult rides in Supply.record_list and
       ProvisionRecord.records even in failure. This module PRESENTS
       them.

       THREE LAWS (todo-21), implemented here:

           (1) an empty answer is never reported empty: it is rendered
               WITH exit code, containment, and the other channel's
               tail;
           (2) diagnosis uses THE SAME facts as the run it diagnoses --
               nothing is re-measured, re-spawned or guessed; the argv
               comes from 'application_argv', the ONE source;
           (3) resolution follows PATH ('shutil.which', the shell's own
               semantics -- never 'whereis'), and the SYMLINK CHAIN is
               shown, because 'nvim' three hops from its binary is
               exactly what a person cannot see.

       A HINT IS NEVER A VERDICT. The wrong-channel hint ('stdout
       empty, stderr full') names a pattern for a human; provision
       judges nothing, and neither does this module.
______________________________________________________________________________
"""
import os
import shutil

from   .provision.core import application_argv


def resolution_chain(command):
    """
    RETURN: list[str], the command's resolution, one hop per line:
            what PATH answers, then each symlink hop to the real file.
            A command PATH cannot answer is SAID so -- never guessed.
    """
    found = shutil.which(command)
    if found is None:
        return ["%s: NOT FOUND on PATH" % command]
    line_list = ["%s -> %s" % (command, found)]
    seen, current = {found}, found
    while os.path.islink(current):
        target = os.readlink(current)
        if not os.path.isabs(target):
            target = os.path.normpath(
                os.path.join(os.path.dirname(current), target))
        line_list.append("   -> %s" % target)
        if target in seen:
            line_list.append("   -> CYCLE")
            break
        seen.add(target)
        current = target
    return line_list


def explain_record(record, label="call"):
    """
    RETURN: list[str], one supervised call's attribution, rendered:
            containment, exit, durations, caps observed, and the stderr
            tail's first line -- the WHY that law (1) refuses to drop.
    """
    line_list = ["%-10s containment %s   exit %s   wall %.3fs"
                 % (label,
                    record.containment.name.lower().replace("_", "-"),
                    record.exit_code, record.wall_clock_sec)]
    if record.unenforced:
        line_list.append("           unenforced caps: %s"
                         % ", ".join(record.unenforced))
    tail = record.stderr_last_100_lines
    if tail.strip():
        text_list = [line for line in tail.splitlines() if line.strip()]
        line_list.append("           stderr tail (%i line(s)) | first: %r"
                         % (len(text_list), text_list[0][:60]))
    return line_list


def explain_channels(raw_db):
    """
    RETURN: list[str], per channel/subject the byte count and first
            line -- and THE WRONG-CHANNEL HINT when stdout is empty
            while stderr is not. A hint for a human, never a verdict.
    """
    line_list = []
    for name in sorted(raw_db):
        text  = raw_db[name] or ""
        first = text.splitlines()[0][:60] if text.strip() else ""
        line_list.append("%-10s %6i bytes%s"
                         % (name, len(text.encode("utf-8")),
                            "   first: %r" % first if first else ""))
    if not (raw_db.get("stdout") or "").strip() \
       and (raw_db.get("stderr") or "").strip():
        line_list.append("HINT: stdout is EMPTY while stderr is not -- "
                         "output on the wrong channel? (a runner may "
                         "route print() to stderr; compare reads stdout)")
    return line_list


def explain(configuration, choice_name, provision_record, raw_db=None):
    """
    RETURN: str, the diagnosis of one provision: the REQUEST (argv, from
            the one source), the interpreter's resolution chain, every
            supervised call's attribution, the report token -- and the
            channels with the wrong-channel hint, when their texts are
            at hand.
    """
    argv      = application_argv(configuration, choice_name)
    line_list = ["EXPLAIN  %s, choice %s"
                 % (configuration.stem, choice_name)]
    line_list.append("  REQUEST    %r" % (argv,))
    line_list += ["  RESOLVED   %s" % line
                  for line in resolution_chain(argv[0])]
    line_list.append("  CWD        %s" % configuration.test_directory)
    for i, record in enumerate(provision_record.records):
        line_list += ["  " + line
                      for line in explain_record(record,
                                                 "call[%i]" % i)]
    line_list.append("  REPORT     %s" % provision_record.report)
    if raw_db is not None:
        line_list += ["  " + line for line in explain_channels(raw_db)]
    return "\n".join(line_list) + "\n"


class DiagnosisObserver:
    """AN OBSERVER (12) that renders the diagnosis when a run FINISHES.
    Hangs on the existing seam: no operation changes, and -- as every
    observer -- it may never change a verdict.

    Construct it with the configuration and choice so the REQUEST can
    be named from the one source; hand it wherever an observer goes.
    """

    def __init__(self, configuration, choice_name=None, write=None):
        self.configuration = configuration
        self.choice_name   = choice_name
        self._write        = write if write is not None else self._stdout

    @staticmethod
    def _stdout(text):
        """RETURN: None. The default sink."""
        import sys
        sys.stdout.write(text)

    def finished(self, result):
        """RETURN: None. The run ended: render its diagnosis."""
        provision_record = getattr(result, "provision", None)
        if provision_record is None: return
        self._write(explain(self.configuration, self.choice_name,
                            provision_record))
