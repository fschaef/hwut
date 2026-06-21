"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

ModuleProxy  (pass 2, disc-4 SETTLED 6 KEPT half / RATIONALE D-31)

A local stand-in for an imported file: a MOUNTED VIEW of that file's symbol
table, addressed under a mount prefix. ONE proxy per import, shared by every
reference that resolves through the mount: the references do LOCAL lookups
against a scope chain that INCLUDES the proxy's mounted view, so there is no
per-reference cross-file logic and no walk into the imported module.

THE VIEW IS NOT A COPY (disc-4 SETTLED 2 -- binding is a LINK, not a copied
entry). The imported module is analysed ONCE into its own table; mounting is
ADDRESSING, not duplication. A proxy mounted at 'NS' answers the head 'NS.tick'
by stripping the mount prefix and asking the imported module's REAL table for
'tick'. The imported file is placement-agnostic; the importer chooses the mount
(Import's own contract). Two importers mounting the same file at different points
share its table through two proxies, no entries copied.

STATIC (RATIONALE D-31). Resolution is static and total: at link the imported
table is ALWAYS present, so there is no presence state, no lazy load, no
unload. The proxy is purely a prefix-router over an already-present table. The
single place SETTLED 2's 'viewed, not absorbed' is named.

VERIFICATION facts (which file, the id this importer was built against) ride on
'path' and 'expected_hash' for a one-time static link check (missing-library /
hash-mismatch), should pre-analysed library tables ever arrive without source
(open question; relocation.py / UnitHeader gate on it). No live state machine.
______________________________________________________________________________
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleProxy:
    """The shared mounted view of one imported file's symbol table.

    'path' names the imported file. 'mount' is the dotted prefix the file's
    names are addressed under in the importing module (Import.mount); a head must
    match this prefix to resolve through the proxy. 'table' is the imported
    module's REAL symbol table (its sealed ground scope's 'symbols' dict, name ->
    Symbol), referenced not copied. 'expected_hash' is the target id this
    importer was built against, for a one-time static link check.

    Frozen: a static proxy has no dynamic surface. Shared by reference -- every
    importer through this mount holds the SAME proxy over the SAME table.
    """
    path:          str
    table:         dict
    mount:         "tuple[str, ...]"   = ()
    expected_hash: "str | None"        = None

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

    def lookup(self, segments):
        """RETURN: the Symbol the imported file declares under the post-mount
                  name; None if the head is not covered by this proxy's mount,
                  or is covered but not declared by the imported file ('absent
                  name' -> the caller's missing-export link error).

        The mounted-view answer. 'segments' is the reference's full dotted head;
        the mount prefix is stripped and the remainder looked up in the imported
        module's real table (no copy). Only the FIRST post-mount segment is
        resolved here (a head); any TYPE/SCOPE tail descent is the resolver's,
        against the returned Symbol.
        """
        if not self.covers(segments):
            return None
        local = segments[len(self.mount):]
        if not local:
            return None                    # bare mount path names no symbol
        return self.table.get(local[0])    # Symbol, or None = absent name
