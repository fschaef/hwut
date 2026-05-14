"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Factory and registry for Artifact instances.

The ArtifactManager is the single point of artifact identity in a workflow.
Every Artifact comes from .generate(); every artifact_id originates here.

This first iteration of the manager handles minting and interning only. The
artifact lifecycle state machine (ABSENT / IN_PRODUCTION / PRESENT /
IMPOSSIBLE), workload tracking, and history are added by the workflow-manager
component when it integrates this one.

INVARIANTS:

    -- Two .generate() calls with the same (type, normalized_description)
       return the very same Artifact instance.
    -- artifact_id values are non-negative integers, monotonically
       increasing in order of first registration.
    -- Once minted, an Artifact is never replaced or removed.
________________________________________________________________________________
"""
from vut.engine.workflow.artifact.artifact import Artifact
from vut.engine.workflow.artifact.enums    import E_Artifact


def _freeze(description: dict) -> tuple:
    """RETURN: tuple of (key, value) pairs sorted by key.

    Produces a canonical, hashable representation of a description dict.
    Two dicts with the same contents in any key order produce the same tuple.
    Values are assumed to be hashable themselves; if a description carries a
    nested mutable object, the caller is responsible for normalising it before
    handing it in.
    """
    return tuple(sorted(description.items()))


class ArtifactManager:
    """Factory and registry for Artifact instances.

    Owns:
        _by_id          artifact_id -> Artifact      (reverse lookup)
        _by_descr       (type, frozen descr) -> Artifact   (forward lookup)
        _next_id        the next artifact_id to assign
    """

    def __init__(self):
        self._by_id    = {}
        self._by_descr = {}
        self._next_id  = 0

    def generate(self, artifact_type: E_Artifact, description: dict) -> Artifact:
        """RETURN: Artifact, the unique instance for (type, description).

        AGAIN: The 'Artifact' is only a placeholder for something useful. 
        It is not the thing itself. '.generate()' does not generate anything,
        it does not accomplish anything. It generates the placeholder, the 
        reference.

        Upon double registration, the same artifact is returned.
        """
        key = (artifact_type, _freeze(description))

        existing = self._by_descr.get(key)
        if existing is not None:
            return existing

        artifact = Artifact(
            type                   = artifact_type,
            normalized_description = dict(description),  # defensive copy
            artifact_id            = self._next_id,
        )
        self._by_descr[key]                  = artifact
        self._by_id[artifact.artifact_id]    = artifact
        self._next_id                       += 1

        return artifact

    def by_id(self, artifact_id: int) -> Artifact | None:
        """RETURN: Artifact, the artifact with the given id.
                   None, if unknown.
        """
        return self._by_id.get(artifact_id)

    def __contains__(self, artifact_id: int) -> bool:
        """RETURN: True if artifact_id has been minted by this manager.
                   False, else.
        """
        return artifact_id in self._by_id

    def __len__(self) -> int:
        """RETURN: int, number of distinct artifacts minted so far."""
        return len(self._by_id)
