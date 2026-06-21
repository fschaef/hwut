"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

ModuleProxy  (pass 2, disc-4 SETTLED 6 -- supersedes the Relocation carrier)

A local stand-in for an imported file, holding a MOUNTED VIEW of that file's
symbol table. ONE proxy per import, shared by every reference that resolves
through the mount: the references do LOCAL lookups against a scope chain that
INCLUDES the proxy's mounted view, so there is no per-reference cross-file logic
and no walk into the imported module.

THE VIEW IS NOT A COPY (disc-4 SETTLED 2 -- binding is a LINK, not a copied
entry). The imported module is analysed ONCE into its own table; mounting is
ADDRESSING, not duplication. A proxy mounted at 'NS' answers the head 'NS.tick'
by stripping the mount prefix and asking the imported module's REAL table for
'tick'. The imported file is placement-agnostic; the importer chooses the mount
(Import's own contract). Two importers mounting the same file at different points
share its table through two proxies, no entries copied.

PRESENCE (E_Presence). ABSENT = the imported module's table is not yet available
(not loaded). PRESENT = available; lookups answer. Eager link makes every proxy
PRESENT up front; lazy link makes one PRESENT on first lookup. ONE mechanism;
SETTLED 3's "lazy by design, eager by default" unchanged -- the carrier moved
here from the per-reference Relocation. unmanifest() drops the proxy to ABSENT
(the table reference is released); every referrer reverts together, while a
module's permanent local_resolutions -- which never consult a proxy -- stand.

VERIFICATION facts the old Relocation held per reference live here ONCE per
import: 'path' (which file) and 'expected_hash' (the id this importer was built
against, compared with the loaded table's UnitHeader at manifest -- the missing-
library / hash-mismatch link errors, STEP 4). The six link errors stay
attributable: a proxy that cannot become PRESENT names the failing file; the
referencing site names where it was needed.
______________________________________________________________________________
"""
from dataclasses import dataclass, field
from enum        import Enum


class E_Presence(Enum):
    """Whether a ModuleProxy's imported table is available.

    ABSENT  the imported module's table is not loaded; lookups cannot answer.
    PRESENT the table is mounted and reachable; lookups answer.
    """
    ABSENT  = 0
    PRESENT = 1


@dataclass
class ModuleProxy:
    """The shared mounted view of one imported file's symbol table.

    'path' names the imported file. 'mount' is the dotted prefix the file's
    names are addressed under in the importing module (Import.mount); a head must
    match this prefix to resolve through the proxy. 'expected_hash' is the target
    id this importer was built against, checked when the proxy becomes PRESENT.
    'presence' is the load state. 'table' is the imported module's REAL symbol
    table (its sealed ground scope's 'symbols' dict, name -> Symbol), referenced
    not copied; set when PRESENT, released on unmanifest.

    Not frozen: 'presence' and 'table' are the dynamic surface a load/unload
    flips. Identity facts (path, mount, expected_hash) are set once. Shared by
    reference -- every importer through this mount holds the SAME proxy, so one
    state flip is seen by all.
    """
    path:          str
    mount:         "tuple[str, ...]"   = ()
    expected_hash: "str | None"        = None
    presence:      E_Presence          = E_Presence.ABSENT
    table:         "dict | None"       = None

    def covers(self, segments) -> bool:
        """RETURN: True,  if 'segments' (a reference's dotted head list) lie
                         under this proxy's mount prefix.
                  False, otherwise.

        The routing test: a reference resolves THROUGH this proxy only if its
        leading segments equal the mount path. An empty mount (current-scope
        import, todo-7) covers every head -- the file's names sit directly in
        the importing scope.
        """
        if not self.mount:
            return True
        return tuple(segments[:len(self.mount)]) == tuple(self.mount)

    def lookup(self, segments, loader=None, reporter=None):
        """RETURN: the Symbol the imported file declares under the post-mount
                  name; None if the file is loaded but does not declare it
                  ('absent name'); None ALSO if the file could not be loaded
                  ('absent file', a link error then reported through 'reporter').

        The mounted-view answer. 'segments' is the reference's full dotted head;
        the mount prefix is stripped and the remainder looked up in the imported
        module's real table (no copy). An ABSENT proxy is made PRESENT first
        (lazy load via 'loader'). The two None results are DISTINCT causes --
        'absent name' (loaded, not declared) vs 'absent file' (load failed) --
        distinguished by the proxy's presence after the call and by the reporter.
        Only the FIRST post-mount segment is resolved here (a head); any TYPE/
        SCOPE tail descent is the resolver's, against the returned Symbol.
        """
        if not self.covers(segments):
            return None
        if self.presence is E_Presence.ABSENT:
            if not self.manifest(loader, reporter):
                return None                # absent file
        local = segments[len(self.mount):]
        if not local:
            return None                    # bare mount path names no symbol
        return self.table.get(local[0])    # Symbol, or None = absent name

    def manifest(self, loader, reporter=None):
        """RETURN: True,  if the table is now available (already PRESENT, or
                          loaded and verified just now).
                  False, if the load failed (a link error is reported through
                          'reporter'); the proxy stays ABSENT.

        Make-present. The eager-link startup loop calls this on every proxy;
        lazy link calls it from lookup() on first miss. An already-PRESENT proxy
        is a no-op True. A 'loader' returning the imported module's table makes
        the proxy PRESENT; hash verification against expected_hash rides here in
        the full build (STEP 4: missing-library / hash-mismatch).
        """
        if self.presence is E_Presence.PRESENT:
            return True
        if loader is None:
            return False
        table = loader(self.path)
        if table is None:
            return False
        self.table    = table
        self.presence = E_Presence.PRESENT
        return True

    def unmanifest(self):
        """RETURN: None. Drops the proxy to ABSENT and releases the table
                  reference, reverting every referrer's cross-file binding.

        The lazy-unload step. Only cross-file bindings (which all run through
        proxies) revert; a module's permanent local_resolutions are untouched
        because they never consulted a proxy.
        """
        self.table    = None
        self.presence = E_Presence.ABSENT
