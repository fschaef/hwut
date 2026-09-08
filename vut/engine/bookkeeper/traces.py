"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE: WHAT A RUN COST, PER MACHINE CLASS -- 'TEST/hwut-traces.csv',
         a table beside the tests, keyed by (system, test, choice,
         operation), holding the LAST run's numbers for each (B-11).

    address   '<test directory>/hwut-traces.csv' -- beside the tests,
              not under 'TMP/': it TRAVELS, so a fresh checkout carries
              the numbers a colleague measured
    form      ';'-separated CSV with a header, as the book is
    key       system;test;choice;operation
    columns   system;test;choice;operation;day;duration_ms;cpu_time_ms;
              peak_memory_mb
    elision   an empty 'system' or 'test' means THE ONE ABOVE (B-12):

                  system;test;choice;operation;day;duration_ms;...
                  linux-i7-13700k-16c-x86_64;test-a.py;one;Run;2026-09-07;142;...
                  ;;two;Run;2026-09-07;141;...
                  ;test-b.py;;Run;2026-09-07;167;...
                  darwin-m1-pro-10c-arm64;test-a.py;one;Run;2026-09-06;98;...

              so a machine class is written once and a test once per
              class. THE ROWS ARE SORTED, which is what makes the
              elision readable and the file's diff small. ONLY THOSE
              TWO ELIDE: an empty 'choice' means a test that HAS no
              choice, and an empty number means the platform did not
              measure it. A first data row with an empty 'system' or
              'test' has nothing above it: the file reads as empty
    growth    an entry is REPLACED where its key stands; a new row
              appears only on a machine class not seen before, so the
              file does not overflow -- a hundred CI containers of one
              instance type are ONE row

TRACES MAY BE DELETED. Nothing reads them to decide anything; a run
makes them again. The name says so.

THE SYSTEM KEY names a machine CLASS, not a speed:

    <os>-<cpu>-<n>c-<arch>        linux-i7-13700k-16c-x86_64
                                  darwin-m1-pro-10c-arm64
                                  linux-xeon-platinum-8375c-4c-x86_64

'<n>' is what the process MAY USE ('sched_getaffinity' where the
platform has it, else 'os.cpu_count'), so a container with a quota
does not wear its host's number. The CPU tag is the vendor string
with its noise removed -- the clause from '@' on (a clock the model
already implies), the vendor words, the punctuation -- cut at a token
boundary. Same key, different thermals or background load, different
milliseconds: A ROW IS A HINT, NOT A PROMISE.
______________________________________________________________________________
"""
import csv
import os
import platform
import re
import subprocess
from   datetime import date

FILE_NAME    = "hwut-traces.csv"
SEPARATOR    = ";"
COLUMN_TUPLE = ("system", "test", "choice", "operation", "day",
                "duration_ms", "cpu_time_ms", "peak_memory_mb")
TAG_MAX_N    = 32

_NOISE = re.compile(r"\((?:r|tm)\)"
                    r"|\b(?:intel|amd|apple|processor|cpu|core|genuine"
                    r"|authentic|with|radeon|graphics|\d+-core|\d+th"
                    r"|gen)\b", re.IGNORECASE)
_CLOCK = re.compile(r"@.*$")
_SYSTEM_KEY = None                      # computed once per process


def system_key():
    """
    RETURN: str, this machine's CLASS -- '<os>-<cpu>-<n>c-<arch>',
            lower case, '[a-z0-9-]' only. Computed once per process:
            on Windows the vendor string may cost a subprocess.
    """
    global _SYSTEM_KEY
    if _SYSTEM_KEY is None:
        _SYSTEM_KEY = "%s-%s-%dc-%s" % (_tag(platform.system()),
                                        cpu_tag(_raw_cpu()),
                                        _usable_core_n(),
                                        _tag(platform.machine()))
    return _SYSTEM_KEY


def _usable_core_n():
    """RETURN: int, how many CPUs this process may use -- the affinity
    where the platform has it (a container's quota shows there), else
    what the machine reports; 1 where neither answers."""
    if hasattr(os, "sched_getaffinity"):
        try:               return len(os.sched_getaffinity(0)) or 1
        except OSError:    pass
    return os.cpu_count() or 1


def _raw_cpu():
    """RETURN: str, the vendor's own description of this CPU; '' where
    the platform does not give one."""
    name = platform.system().lower()
    if name == "linux":
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8",
                      errors="replace") as fh:
                for line in fh:
                    if "model name" in line:
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass
    elif name == "windows":
        #  THE ENVIRONMENT FIRST: it is free and carries family, model
        #  and stepping; PowerShell costs a subprocess and is asked
        #  only where the variable is absent.
        raw = os.environ.get("PROCESSOR_IDENTIFIER", "")
        if raw: return raw
        try:
            return subprocess.check_output(
                       ["powershell", "-NoProfile", "-Command",
                        "(Get-CimInstance Win32_Processor).Name"],
                       stderr=subprocess.DEVNULL,
                       timeout=10).decode("utf-8", "replace").strip()
        except (OSError, subprocess.SubprocessError):
            pass
    elif name == "darwin":
        try:
            return subprocess.check_output(
                       ["sysctl", "-n", "machdep.cpu.brand_string"],
                       stderr=subprocess.DEVNULL,
                       timeout=10).decode("utf-8", "replace").strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return platform.processor() or ""


def cpu_tag(raw_cpu, limit=TAG_MAX_N):
    """
    RETURN: str, the vendor string as a tag: the clause from '@' on
            dropped, the vendor's noise words removed, everything but
            letters and digits turned to '-', cut at a TOKEN boundary
            where it is longer than 'limit'; 'cpu' where nothing is
            left.

    'Intel(R) Xeon(R) Platinum 8375C CPU @ 2.90GHz' -> 'xeon-platinum-8375c'
    'AMD Ryzen 7 5800X 8-Core Processor'            -> 'ryzen-7-5800x'
    'Apple M1 Pro'                                  -> 'm1-pro'

    The MODEL NUMBER is what distinguishes two machines of one family,
    so it must survive the cut: a whitelist of vendors would keep
    'intel-xeon-platinum' for two Xeons that differ by a factor of
    two.
    """
    text = _tag(_NOISE.sub(" ", _CLOCK.sub("", raw_cpu)))
    if not text:            return "cpu"
    if len(text) <= limit:  return text
    cut = text[:limit]
    return (cut.rsplit("-", 1)[0] if "-" in cut else cut).strip("-") or "cpu"


def _tag(text):
    """RETURN: str, the text as '[a-z0-9-]', no leading or trailing
    '-'."""
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()


class TraceDb:
    """The traces of one directory: read whole, changed, written whole
    -- as the book is."""

    def __init__(self, directory):
        self.path = os.path.join(str(directory), FILE_NAME)

    def read(self):
        """
        RETURN: dict, (system, test, choice, operation) -> dict of the
                remaining columns. Empty where no file stands or it
                cannot be read: a trace is never worth failing a run.
        """
        row_db = {}
        system = test = None
        try:
            with open(self.path, "r", encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh, delimiter=SEPARATOR):
                    #  AN EMPTY 'system' OR 'test' IS THE ONE ABOVE
                    #  (B-12). Nothing above it is a fault in the file,
                    #  and a trace is never worth guessing at.
                    system = row.get("system") or system
                    test   = row.get("test")   or test
                    if system is None or test is None: return {}
                    key = (system, test, row.get("choice", "") or "",
                           row.get("operation", "") or "")
                    row_db[key] = {name: row.get(name, "") or ""
                                   for name in COLUMN_TUPLE[4:]}
        except (OSError, csv.Error, UnicodeDecodeError):
            return {}
        return row_db

    def note(self, test, choice, operation, duration_ms=None,
             cpu_time_ms=None, peak_memory_mb=None):
        """
        RETURN: None. This machine class's row for that key is written,
                replacing what stood. Nothing is raised: a trace that
                cannot be written is not a fault of the run.
        """
        key = (system_key(), test, choice or "", operation or "")
        row_db = self.read()
        row_db[key] = {"day":            date.today().isoformat(),
                       "duration_ms":    "" if duration_ms is None
                                         else str(int(duration_ms)),
                       "cpu_time_ms":    "" if cpu_time_ms is None
                                         else str(int(cpu_time_ms)),
                       "peak_memory_mb": "" if peak_memory_mb is None
                                         else str(peak_memory_mb)}
        try:
            temporary = self.path + ".tmp"
            with open(temporary, "w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh, delimiter=SEPARATOR,
                                    lineterminator="\n")
                writer.writerow(COLUMN_TUPLE)
                #  SORTED, so that 'the one above' means what the eye
                #  reads; the repeated system and test are elided.
                system = test = None
                for key in sorted(row_db):
                    cell_list = list(key)
                    if key[0] == system: cell_list[0] = ""
                    else:                system, test = key[0], None
                    if key[1] == test:   cell_list[1] = ""
                    else:                test = key[1]
                    writer.writerow(cell_list
                                    + [row_db[key].get(name, "")
                                       for name in COLUMN_TUPLE[4:]])
            os.replace(temporary, self.path)
        except OSError:
            pass
