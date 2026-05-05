"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Passive record of an artifact in the workflow.

An Artifact is the workflow's record of a milestone, never the milestone
itself. The real thing - file, socket, event - lives outside the manager;
the Artifact only tracks it.

An Artifact is a frozen record. Instances are not constructed directly by
recipes or tasks; they are minted by an ArtifactManager via .make(), which
guarantees that:

    -- the artifact_id is unique within that manager's scope
    -- two requests for the same (type, normalized_description) yield the
       same Artifact instance (interning)

The normalized_description is stored as a tuple of (key, value) pairs,
sorted by key. This makes the Artifact hashable, comparable, and stable
under dict-key ordering - the same description handed in as
{"a": 1, "b": 2} and {"b": 2, "a": 1} produces the same Artifact.
________________________________________________________________________________
"""
from dataclasses import dataclass

from vut.engine.workflow.artifact.enums import E_Artifact


@dataclass(frozen=True)
class Artifact:
    type:                   E_Artifact
    normalized_description: tuple   # tuple of (key, value) pairs, sorted by key
    artifact_id:            int

    def description_dict(self) -> dict:
        """RETURN: dict, the normalized_description rendered as a fresh dict.

        Convenience for callers that want to read the description in dict
        form without having to reconstruct it themselves. The Artifact
        itself stores the tuple form for hashability.
        """
        return dict(self.normalized_description)

    def __repr__(self) -> str:
        """RETURN: str, compact one-line representation suitable for logs."""
        descr_pairs = ", ".join("%s=%r" % kv for kv in self.normalized_description)
        return "Artifact(%s, {%s}, id=%d)" % (
            self.type.name, descr_pairs, self.artifact_id
        )
