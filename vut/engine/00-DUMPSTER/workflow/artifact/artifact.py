"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Passive record of an artifact in the workflow.

An Artifact is the workflow's record of a milestone, never the milestone
itself. The real thing - file, socket, event - lives outside the manager;
the Artifact only tracks it.

An Artifact is a frozen record. Instances are not constructed directly by
recipes or tasks; they are minted by an ArtifactManager via .generate(), which
guarantees that:

    -- the artifact_id is unique within that manager's scope
    -- two requests for the same (type, normalized_description) yield the
       same Artifact instance (interning)

The normalized_description is stored as a dict, the natural form for
recipes and tasks that read it. The ArtifactManager handles the transient
sorted-tuple form needed for its lookup table; that detail does not leak
into the record itself.

Artifact intentionally has no auto-generated __hash__ / __eq__: identity
is the artifact_id assigned by the manager, not a hash of the contents.
Asking "are these the same artifact?" is answered by comparing artifact_id.
________________________________________________________________________________
"""
from dataclasses import dataclass

from vut.engine.workflow.artifact.enums import E_Artifact


@dataclass(frozen=True, eq=False)
class Artifact:
    """IMPORTANT: An artifact is the record of something useful, not the
                  thing itself. It may represent the 'test being executed'
                  and 'network connection being established', or a
                  'file being generated'. But it is a placeholder, not the
                  thing itself.
    """
    type:                   E_Artifact
    normalized_description: dict
    artifact_id:            int

    def __repr__(self) -> str:
        """RETURN: str, compact one-line representation suitable for logs."""
        return "Artifact(%s, %s, id=%d)" % (
            self.type.name, self.normalized_description, self.artifact_id
        )
