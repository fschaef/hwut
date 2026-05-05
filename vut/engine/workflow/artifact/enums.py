"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Enum of artifact types known to the workflow manager.

Each value names a category of milestone the workflow can track. The category
selects which ArtifactHandling class is responsible for canonicalising the
artifact's description and resolving it back to a local handle at execution
time.

Adding a new artifact type is a three-step operation:

    1. Add a value to E_Artifact below.
    2. Define an Artifact subclass (often just a marker) for it.
    3. Define an ArtifactHandling subclass with .canonicalise() and .resolve()
       and register it in an ArtifactHandlingRegistry.

The enum itself carries no behaviour. It is the key into the type-aware
handling machinery.
________________________________________________________________________________
"""
from enum import Enum, auto


class E_Artifact(Enum):
    FILEPATH = auto()
    # Future:  NETWORK_CONNECTION, PROCESS_HANDLE, REPO_CHECKOUT, ...
