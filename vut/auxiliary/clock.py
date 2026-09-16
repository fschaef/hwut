"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE CLOCK -- every 'now' the framework records or reckons
         from is asked here, so that a test may STATE the time.

DESCRIPTION
       A test that investigates behaviour beyond seconds -- '--since',
       '--until', an observation's instant -- must not wait for the wall
       clock, and must not FLIP when a run straddles a second or an hour
       (services E-80). It calls 'state(instant)' once; every reader of
       the clock then sees that instant, until 'release()'. Production
       code never states the clock: 'now()' is the wall clock by default.
______________________________________________________________________________
"""
from datetime import datetime, timezone

_stated = None


def now():
    """RETURN: datetime, the current instant, aware UTC -- the stated
               one where a test stated it, the wall clock else."""
    if _stated is not None: return _stated
    return datetime.now(timezone.utc)


def epoch_second():
    """RETURN: int, the current instant as whole seconds since the
               epoch -- the shape an observation records."""
    return int(now().timestamp())


def state(instant):
    """RETURN: None. From here on every reader sees 'instant' (a
               datetime; naive is taken as UTC)."""
    global _stated
    if instant.tzinfo is None: instant = instant.replace(tzinfo=timezone.utc)
    _stated = instant


def release():
    """RETURN: None. The wall clock again."""
    global _stated
    _stated = None
