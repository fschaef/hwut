"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Artifact identity and per-type handling for the workflow manager.

This package provides the passive record type that the workflow uses to track
milestones, the manager that mints those records, and the per-type handling
machinery that translates between user-facing descriptions and the canonical
forms the workflow operates on.

PUBLIC API:

    Artifact                  frozen record: (type, normalized_description, id)
    ArtifactManager           factory and registry for Artifact instances
    ArtifactHandling          ABC for per-type canonicalise / resolve
    ArtifactHandlingRegistry  type-keyed lookup of ArtifactHandling classes
    E_Artifact                enum of supported artifact types

WORKED EXAMPLE:

    Filepath                  marker subclass of Artifact for FILEPATH type
    FilepathHandling          canonicalise/resolve for filesystem paths
________________________________________________________________________________
"""
from .enums                      import E_Artifact
from .artifact                   import Artifact
from .artifact_manager           import ArtifactManager
from .artifact_handling          import ArtifactHandling, ArtifactHandlingRegistry
from .artifact_handling_filepath import Filepath, FilepathHandling

__all__ = [
    "E_Artifact",
    "Artifact",
    "ArtifactManager",
    "ArtifactHandling",
    "ArtifactHandlingRegistry",
    "Filepath",
    "FilepathHandling",
]
