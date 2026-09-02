"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE SUMMARY -- a pure fold over the report stream (O-4). The
         stream is the ONE carrier of the run's truth; whoever wants
         the whole at the end folds it, with this function or their
         own.

Any consumer may use it: our exit-status logic, a TUI, a customer
application. It reads the vocabulary and nothing else; an unknown kind
passes through untouched, as the format promises.
______________________________________________________________________________
"""
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CRunSummary:
    """What one run came to, folded from its stream.

    'verdict_db' maps (directory, node) to the verdict word;
    'cause_db' names, for the nodes that have one, the node whose
    breaking failed them. 'good_f' and 'fail_n' are 'tree-done's own
    word -- 'None' where the stream ended without one."""
    directory_tuple: tuple = ()
    verdict_db:      dict  = field(default_factory=dict)
    cause_db:        dict  = field(default_factory=dict)
    detail_db:       dict  = field(default_factory=dict)   # O-19
    frame_db:        dict  = field(default_factory=dict)
    fault_tuple:     tuple = ()
    report_tuple:    tuple = ()
    dir_good_db:     dict  = field(default_factory=dict)
    good_f:          bool | None = None
    fail_n:          int  | None = None

    def failure_db(self):
        """
        RETURN: dict, (directory, node) -> verdict, every run whose
                verdict is not 'ok'.
        """
        return {key: verdict for key, verdict in self.verdict_db.items()
                if verdict != "ok"}


def fold(event_iterable):
    """
    RETURN: CRunSummary, the given events folded in order. Events of
            an unknown kind are ignored, and so is a known kind whose
            required fields are missing -- the vocabulary's promise,
            honoured at the consumer; anything that is not a dict ends
            the fold ('None' does).
    """
    directory_list = []
    verdict_db     = {}
    cause_db       = {}
    detail_db      = {}
    frame_db       = {}
    fault_list     = []
    report_list    = []
    dir_good_db    = {}
    good_f         = None
    fail_n         = None

    def fits(*name_tuple):
        """RETURN: bool, True where 'item' carries every named field
        -- the promise extended: a malformed known kind is ignored
        like an unknown one, never a crash at the consumer."""
        return all(name in item for name in name_tuple)

    for item in event_iterable:
        if not isinstance(item, dict): break
        kind = item.get("kind")
        if   kind == "tree-begun":
            if not fits("directory_list"): continue
            directory_list = list(item["directory_list"])
        elif kind == "run-ended":
            if not fits("directory", "node", "verdict"): continue
            key             = (item["directory"], item["node"])
            verdict_db[key] = item["verdict"]
            if "cause" in item: cause_db[key] = item["cause"]
            if "detail" in item: detail_db[key] = item["detail"]
        elif kind == "frame":
            if not fits("directory", "role", "good"): continue
            frame_db[(item["directory"], item["role"])] = item["good"]
        elif kind == "fault":
            if not fits("directory", "text"): continue
            fault_list.append((item["directory"], item["text"]))
        elif kind == "report":
            if not fits("directory", "text"): continue
            report_list.append((item["directory"], item["text"]))
        elif kind == "dir-done":
            if not fits("directory", "good"): continue
            dir_good_db[item["directory"]] = item["good"]
        elif kind == "tree-done":
            if not fits("good", "fail_n"): continue
            good_f = item["good"]
            fail_n = item["fail_n"]

    return CRunSummary(directory_tuple = tuple(directory_list),
                       verdict_db      = verdict_db,
                       cause_db        = cause_db,
                       detail_db       = detail_db,
                       frame_db        = frame_db,
                       fault_tuple     = tuple(fault_list),
                       report_tuple    = tuple(report_list),
                       dir_good_db     = dir_good_db,
                       good_f          = good_f,
                       fail_n          = fail_n)


async def drain(queue):
    """
    RETURN: CRunSummary, the queue read to its closing 'None' and
            folded.
    """
    event_list = []
    while True:
        item = await queue.get()
        event_list.append(item)
        if item is None: break
    return fold(event_list)
