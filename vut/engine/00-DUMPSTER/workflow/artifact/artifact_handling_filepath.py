"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Filesystem-path artifact and its handler.

This module is the worked example of an ArtifactHandling implementation.
It shows the canonicalise/resolve pattern at the simplest possible level:
a path string with one normalising convention (test_root) and one local
context key (host_root).

CANONICAL FORM:
    {"path": "<relative-to-test-root>"}

The canonical form contains only the path component relative to the
test_root convention. Absolute paths are made relative; relative paths
are normalised (collapsing "..", trailing slashes, redundant separators).

LOCAL HANDLE:
    pathlib.PurePosixPath rooted at local_context["host_root"]

PurePosixPath is used rather than Path so the handler works deterministically
in tests without touching the real filesystem.
________________________________________________________________________________
"""
from pathlib import PurePosixPath

from vut.engine.workflow.artifact.artifact          import Artifact
from vut.engine.workflow.artifact.artifact_handling import ArtifactHandling


class Filepath(Artifact):
    """Marker subclass for filesystem-path artifacts.

    Carries no fields beyond the base. Its purpose is to let recipes and
    tasks pattern-match on the artifact subclass when that is more
    convenient than checking the .type field.
    """
    pass


class FilepathHandling(ArtifactHandling):
    """Handler for FILEPATH-type artifacts.

    Conventions consumed:
        test_root      str   workflow-wide root for path canonicalisation

    local_context consumed:
        host_root      str   host-local root onto which canonical paths
                             are joined at resolve time
    """

    @classmethod
    def canonicalise(cls, description: dict, conventions: dict) -> dict:
        """RETURN: dict, {"path": <canonical-relative-path>}.

        The input description must contain key "path". If conventions
        provides a "test_root" and the path is absolute, the path is made
        relative to that root. In all cases, the result is normalised
        with PurePosixPath rules: redundant separators are collapsed,
        "." segments removed, ".." segments resolved where possible.

        Raises KeyError if "path" is missing from `description`.
        """
        raw_path  = description["path"]
        test_root = conventions.get("test_root", "")

        path = PurePosixPath(raw_path)

        if path.is_absolute() and test_root:
            try:
                path = path.relative_to(test_root)
            except ValueError:
                # Path is absolute but does not lie under test_root.
                # Keep it as-is; the workflow may legitimately reference
                # paths outside the test root (system libraries, etc).
                pass
        # PurePosixPath construction already collapses ".", "//", trailing
        # separators. We canonicalise further by walking ".." segments.
        path = cls._collapse_dotdot(path)

        return {"path": str(path)}

    @classmethod
    def resolve(cls,
                normalized_description: dict,
                local_context:          dict) -> PurePosixPath:
        """RETURN: PurePosixPath, the local-machine path for this artifact.

        The canonical path is joined onto local_context["host_root"] if
        provided, producing an absolute local path. If host_root is not
        given, the canonical path is returned as-is, which is useful for
        in-process tasks that share the workflow's working directory.

        Raises KeyError if "path" is missing from `normalized_description`.
        """
        canon_path = normalized_description["path"]
        host_root  = local_context.get("host_root")

        if host_root is None:
            return PurePosixPath(canon_path)
        return PurePosixPath(host_root) / canon_path

    @staticmethod
    def _collapse_dotdot(path: PurePosixPath) -> PurePosixPath:
        """RETURN: PurePosixPath with leading and interior '..' segments
                   resolved where possible.

        PurePosixPath does not collapse '..' on its own (it cannot, in
        general, since '..' may cross symlinks on a real filesystem).
        For our canonicalisation we treat paths purely lexically and
        eliminate '..' wherever a non-'..' parent precedes it.
        """
        parts = []
        for segment in path.parts:
            if segment == ".." and parts and parts[-1] not in ("..", "/"):
                parts.pop()
            else:
                parts.append(segment)

        if not parts:
            return PurePosixPath(".")
        return PurePosixPath(*parts)
