"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Per-type translation between user descriptions, canonical descriptions,
         and local execution handles.

An ArtifactHandling class encapsulates the type-specific knowledge of how to
move between three representations of the same artifact:

    raw description   <--canonicalise--   normalised description   --resolve-->   local handle
    (recipe input)                        (workflow-internal id)                  (task input)

The two operations are duals. Canonicalisation strips local surface detail
to produce a universal form that the workflow can use for identity.
Resolution recovers local detail appropriate to a particular execution
context.

Handlers are registered per E_Artifact value in an ArtifactHandlingRegistry.
The workflow manager owns one registry; recipes call into it during workload
construction to canonicalise; task launchers call into it at execution time
to resolve. Multiple Task classes that work with the same artifact type
share the same handler.
________________________________________________________________________________
"""
from abc import ABC, abstractmethod

from vut.engine.workflow.artifact.enums import E_Artifact


class ArtifactHandling(ABC):
    """Abstract base for per-type artifact handling.

    Subclasses implement two classmethods. They carry no state; all state
    is supplied through the conventions / local_context arguments. The
    methods are classmethods rather than staticmethods so that subclasses
    can be passed around as types and inherited from cleanly.
    """

    @classmethod
    @abstractmethod
    def canonicalise(cls, description: dict, conventions: dict) -> dict:
        """RETURN: dict, the canonical form of `description` under
                         `conventions`.

        Strips locally-varying surface detail. Two descriptions that
        denote the same underlying artifact must produce the same
        canonical dict under the same conventions.

        Conventions provide workflow-wide context the canonicaliser may
        consult (e.g. test_root for filesystem paths, dns_resolver for
        network endpoints). Keys not used by this handler are ignored.

        The returned dict is the input to ArtifactManager.generate().
        """
        ...

    @classmethod
    @abstractmethod
    def resolve(cls, normalized_description: dict, local_context: dict):
        """RETURN: object, a local handle suitable for the executing task.

        Recovers a usable representation of the artifact appropriate to
        the local execution context: a pathlib.Path, a connected socket,
        a process handle, etc. The exact return type is specific to the
        artifact type.

        local_context provides runtime information about the executing
        host (host_root, user, machine_id, ...). Different launchers
        supply different contexts; the resolver returns appropriately
        different handles for the same canonical artifact.
        """
        ...

class ArtifactHandlingRegistry:
    """Type-keyed registry of ArtifactHandling classes.

    The workflow manager owns one instance. Recipes and task launchers
    look up the appropriate handler via .get(artifact_type).

    Registration is one-shot: once a handler is registered for a type,
    further registration attempts for that type are refused. The caller
    is informed via the return value of .register() and decides how to
    react. The registry itself never raises and never overwrites: it is
    pure mechanism, no policy.
    """

    def __init__(self):
        self._db: dict[E_Artifact, type[ArtifactHandling]] = {}

    def register(self,
                 artifact_type: E_Artifact,
                 handling:      type[ArtifactHandling]) -> bool:
        """RETURN: True,  if accepted.
                   False, if refused due to previous registration.

        Associates a handler class with an artifact type if and only
        if no handler was previously registered for that type.

        The handling argument is the class itself, not an instance;
        ArtifactHandling carries no instance state.
        """
        if artifact_type in self._db:
            return False
        else:
            self._db[artifact_type] = handling
            return True

    def get(self, artifact_type: E_Artifact) -> type[ArtifactHandling] | None:
        """RETURN: ArtifactHandling subclass registered for `artifact_type`.
                   None, if no handler is registered.

        The caller is responsible for handling the None case
        (typically: report it as a configuration error).
        """
        try:
            return self._db[artifact_type]
        except KeyError:
            return None

    def __contains__(self, artifact_type: E_Artifact) -> bool:
        """RETURN: True if a handler is registered for `artifact_type`.
                   False, else.
        """
        return artifact_type in self._db
