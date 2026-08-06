"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE BUILD STAGE -- the application comes to exist.

DESCRIPTION
       One stage of provision (see provision/core.py). The build tool
       itself lives in build.py; this stage supplies its outcome, once,
       however many Provisions share the instance.
______________________________________________________________________________
"""
import asyncio

from   vut.engine.test_run.build           import build
from   vut.engine.test_run.provision.core  import Supply


class StageBuild:
    """THE APPLICATION comes to exist -- once.

    A build stage REMEMBERS its outcome: however many Provisions share
    this instance, the build tool runs a single time. That memo is what
    'build if necessary' means at suite scale. A fresh stage per
    Provision -- the planners' default -- reproduces per-run building
    exactly.

    Reads the source and build keys of the configuration.
    """

    def __init__(self, configuration, observer=None):
        self.configuration = configuration
        self.observer      = observer
        self._supply       = None
        self._lock         = asyncio.Lock()

    async def supply(self, stop_event=None):
        """
        RETURN: Supply, product = the build outcome; product None with
                the build's own token when the application did not come
                to exist.

        MEMOIZED behind a lock: a second caller -- even a concurrent
        one -- receives the FIRST call's answer, never a second build.
        """
        async with self._lock:
            if self._supply is None:
                outcome = await build(self.configuration,
                                      stop_event=stop_event,
                                      observer=self.observer)
                self._supply = Supply(
                    product     = outcome if outcome.succeeded else None,
                    report      = outcome.report,
                    record_list = (outcome.record,))
            return self._supply
