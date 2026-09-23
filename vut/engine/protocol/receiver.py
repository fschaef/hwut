"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE RECEIVER -- the convenience class a consumer derives from
         (O-5). It owns the queue-draining loop and the wire
         validation; the user overrides the 'on_<kind>' methods he
         cares about, with NAMED parameters, and the wire protocol
         stays ours to change underneath.

Every handler is a concrete NO-OP: a vocabulary that grows never
breaks a standing receiver. Three catch-alls take '**fields':

    on_any(kind, **fields)      every event, raw, before its handler
    on_unknown(kind, **fields)  a kind the vocabulary does not carry
    on_misfit(kind, **fields)   a KNOWN kind whose structure does not
                                fit -- a required field missing or
                                badly typed, or no dict at all

A specific handler receives exactly the vocabulary's fields of its
format -- required ones always, optional ones defaulting to 'None';
fields a NEWER stream adds are dropped before the call, which is how
named parameters survive growth.
______________________________________________________________________________
"""
from .vocabulary import KIND_DB


class CRunReportReceiver:
    """Derive, override what you care about, hand 'receive' the
    queue."""

    async def receive(self, queue):
        """
        RETURN: None. Reads the queue to its closing 'None', validates
                every event against the vocabulary, and dispatches:
                'on_any' first, then the event's own handler --
                'on_unknown' or 'on_misfit' where it has none or does
                not fit.
        """
        while True:
            item = await queue.get()
            if item is None: return
            self._dispatch(item)

    def _dispatch(self, item):
        """
        RETURN: None. One event routed (see 'receive').
        """
        if not isinstance(item, dict) or "kind" not in item:
            self.on_misfit("?", raw=item)
            return
        field_db = {name: value for name, value in item.items()
                    if name not in ("kind", "format")}
        kind = item["kind"]
        self.on_any(kind, **field_db)

        entry = KIND_DB.get(kind)
        if entry is None:
            self.on_unknown(kind, **field_db)
            return
        required_db, optional_db = entry
        for name, field_type in required_db.items():
            if name not in field_db \
               or not isinstance(field_db[name], field_type):
                self.on_misfit(kind, **field_db)
                return
        if "when" not in field_db:
            self.on_misfit(kind, **field_db)
            return

        handler  = getattr(self, "on_%s" % kind.replace("-", "_"))
        argument_db = {"when": field_db["when"]}
        argument_db.update({name: field_db[name]
                            for name in required_db})
        argument_db.update({name: field_db.get(name)
                            for name in optional_db})
        handler(**argument_db)

    # -- the catch-alls, '**fields' ------------------------------------
    def on_any(self, kind, **fields):
        """RETURN: None. Every event, raw, before its handler -- the
        tap for logging or relaying."""

    def on_unknown(self, kind, **fields):
        """RETURN: None. A kind this vocabulary does not carry -- a
        NEWER stream at an OLDER receiver."""

    def on_misfit(self, kind, **fields):
        """RETURN: None. A known kind whose structure does not fit the
        vocabulary: a required field missing or badly typed, or no
        dict at all (then 'kind' is '?' and 'raw' carries the item)."""

    # -- one handler per kind, NAMED parameters, concrete no-ops -------
    def on_tree_begun(self, when, directory_list):
        """RETURN: None. The run begins; the test directories in walk
        order."""

    def on_dir_begun(self, when, directory, node_n):
        """RETURN: None. One directory's run begins."""

    def on_frame(self, when, directory, role, good):
        """RETURN: None. 'on_entry' or 'on_exit' ran."""

    def on_run_begun(self, when, directory, node, node_kind):
        """RETURN: None. One node's work was dispatched."""

    def on_run_ended(self, when, directory, node, node_kind, good,
                     verdict, cause=None, report=None, detail=None):
        """RETURN: None. One node's work ended; 'verdict' says WHY
        coarsely, 'report' is the operation's own finer word where one
        is known, 'detail' the report's numbers where it has them
        (O-19), and 'cause' names the node whose breaking failed this
        one, where one did."""

    def on_fault(self, when, directory, text):
        """RETURN: None. A fault of exploration or the walk."""

    def on_report(self, when, directory, text):
        """RETURN: None. A report of determination -- e.g. an empty
        selection."""

    def on_warning(self, when, text):
        """RETURN: None. A finding of determination about the wish
        that decides nothing -- a glob that met only silenced runs;
        tree-level, before any run."""

    def on_refused(self, when, directory, node, text):
        """RETURN: None. A file or test NOT RUN, by name and reason
        (E-41): a backup-shaped candidate, a test with no nominal."""


    def on_silent(self, when, directory, node):
        """RETURN: None. A candidate carrying no 'hwut { }' and named
        under no 'apps' (X-SILENT): no application, no fault, no
        refusal. A receiver that does not care ignores it."""
        pass

    def on_dir_done(self, when, directory, good, fail_db):
        """RETURN: None. One directory's run ended."""

    def on_tree_done(self, when, good, fail_n, meta_n=0, skip_n=0):
        """RETURN: None. The run ended; 'None' follows on the
        queue."""
