"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE PROVIDER INTERFACES -- one per stage role.

DESCRIPTION
       A Provision holds its stages by SLOT; what fills a slot is
       anything derived from that slot's OWN interface below. The local
       stages ('stage_<n>.py') derive; so does any PROXY plugged from
       above -- one entangled with a multi-processor -- which acts as
       if it produced its product and merely triggers when told that
       provision is made. Behind the interface the two are
       indistinguishable, and nothing downstream ever asks.

       ONE INTERFACE PER ROLE, NOT ONE FOR ALL. Each role has its own
       amortisation partner and its own natural sharing scope:

           I_ExecuteProvider      the run    -- many choices, one
                                  process (a multi-processor)
           I_CanonicaliseProvider the pype   -- per subject

       and each declares its OWN 'supply' arity out loud:
       canonicalisation is the one role fed by its predecessor, so its
       signature carries 'raw_db'; execution takes only the stop
       event. One interface for both would hide that asymmetry in one
       signature and cover two different bargains with one word.
       Building and acquisition left with the surgery (core.py names
       where they went); loading is 'consume/loaded.py'.

       THE ROLE IS THE TYPE. Provision refuses a provider in the wrong
       slot AT THE DOOR (core.py) -- a canonicaliser in the execute
       slot is a named refusal at construction, never a wrong product
       shape one stage later.

       EVERY PROVIDER ANSWERS IN THE ONE SHAPE, 'Supply(product,
       report, record_list)' (core.py): product None ends provision
       with the report token; the records are the attribution, kept
       even in failure -- for a proxy, they TRAVEL WITH the delivery,
       so the book never goes silent about work done elsewhere.
       No provider raises.

       THE GENERAL SCHEME. 'I_Provider' is the family's root: the one
       law above, and nothing else -- each role keeps declaring its own
       arity. Two shapes stand on that root:

           I_ProxyProvider(I_Provider)   a provider HANDED OUT by a
                                         multi-provider: it acts as if
                                         it produced its product and
                                         triggers when its multi says
                                         the provision is made; it
                                         names that multi ('.multi')
           I_MultiProvider               the holder of ONE shared
                                         in-parallel means -- a
                                         session, a build tool, a
                                         configuration management
                                         transaction -- serving MANY
                                         units of work through the
                                         proxies it sets up

       THE ORCHESTRATOR'S DECISION: queue a plain provider, or
       generate a multi-provider and queue ITS PROXIES -- the queue
       consumes 'I_Provider' uniformly, and never learns which it got.

               plain:    queue <-- StageExecute(cfg)
               multi:    m = MultiExecute(cfg)
                         queue <-- m.provider(c1)
                         queue <-- m.provider(c2)   one shared means,
                         queue <-- m.provider(c3)   N queued proxies
______________________________________________________________________________
"""
from abc import ABC, abstractmethod


class I_Provider(ABC):
    """THE FAMILY'S ROOT: whatever fills a Provision slot -- a local
    stage or a handed-out proxy. It answers in the ONE Supply shape and
    never raises; each ROLE below declares its own 'supply' arity, so
    the root declares none."""
    pass


class I_ProxyProvider(I_Provider):
    """A provider HANDED OUT by an I_MultiProvider: it acts as if it
    produced its product, and triggers when its multi says the
    provision is made. Beside its role interface, it names its
    multi."""

    @property
    @abstractmethod
    def multi(self):
        """RETURN: I_MultiProvider, the holder of the shared means this
        proxy triggers on."""


class I_MultiProvider(ABC):
    """THE HOLDER of one shared in-parallel means, serving many units
    of work through the proxies it sets up. Not itself a provider --
    its PROXIES fill the slots. Use as an async context manager, or
    'start()'/'close()' by hand; '.record' carries the shared means'
    attribution after close."""

    @abstractmethod
    async def start(self):
        """RETURN: None. Brings the shared means up. Idempotent."""

    @abstractmethod
    async def close(self):
        """RETURN: the shared means' attribution record, also kept as
        '.record'; None when it never came up. Idempotent."""

    @abstractmethod
    def provider(self, *key):
        """RETURN: I_ProxyProvider, the proxy of ONE unit of work,
        named by 'key' in the concrete multi's own vocabulary."""

    async def __aenter__(self):
        """RETURN: self, the shared means up."""
        await self.start()
        return self

    async def __aexit__(self, *_):
        """RETURN: False, exceptions propagate."""
        await self.close()
        return False


class I_ExecuteProvider(I_Provider):
    """RAW BEHAVIOR comes to exist -- locally under this provision's
    own procsitter ('StageExecute'), or by a proxy into a
    multi-processor running many choices through one process."""

    @abstractmethod
    async def supply(self, stop_event=None):
        """
        RETURN: Supply, product = (raw_db, timing_db): the raw texts by
                subject name, and the cadence -- a dict where measured,
                None where the provider cannot measure it. Absence is
                DATA: an unmeasured cadence is never an empty one.
                Product None when the launch failed.
        """


class I_CanonicaliseProvider(I_Provider):
    """THE SUBJECT comes to exist from the raw: each stream rewritten
    by its declared pype -- locally ('StageCanonicalise'), or by a
    proxy into a pool. The one role FED BY ITS PREDECESSOR: 'supply'
    carries 'raw_db'."""

    @abstractmethod
    async def supply(self, raw_db, stop_event=None):
        """
        RETURN: Supply, product = readers by subject name, comparable.
        """
