"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: hwut_remote -- the host's end of a link to an agent (README 11).

    REGISTRY   add_plugin(transport, producer)
    FACTORY    create_hub(transport, address=None, *, config_file=None,
                          note=None, image_id=None, image=None, failures=3,
                          **options) -> Hub, NOT opened
    PRODUCT    Hub: 'with hub:' opens and greets; flash; reset_bench;
               LinkHub: reset, vector, read, write, contract
    CLI        python3 -m hwut_remote ... (__main__.py)

    from hwut_remote import create_hub
    with create_hub("serial", config_file="max10.conf", note=note) as hub:
        hub.reset()
        print(hub.contract())
        print("%03x" % hub.vector(0x0304))

hwut imports nothing of it; it imports nothing of hwut.
______________________________________________________________________________
"""
from .         import entry
from .entry    import ConfigError
from .link     import DeviceAbsent, LinkError
from .session  import (Hub, LinkHub, TIMEOUT, HubError, NoAgent,
                       AgentRestarted, AgentSilent, Refused, Expired)

__all__ = ["create_hub", "add_plugin", "producer", "Hub", "LinkHub",
           "TIMEOUT", "HubError", "NoAgent", "AgentRestarted", "AgentSilent",
           "Refused", "Expired", "ConfigError", "DeviceAbsent", "LinkError"]


class _Producer:
    """A producer: 'read(config_file) -> dict' and '(values, note) -> Hub'.
    'make' takes (transport, values, note) and returns the Hub."""

    def __init__(self, transport, make, reader=entry.read, check=None):
        """RETURN: None."""
        self.transport = transport
        self._make     = make
        self._reader   = reader
        self._check    = check

    def read(self, config_file):
        """RETURN: dict, the values 'config_file' holds, in the producer's
        format; {} for None."""
        return self._reader(config_file)

    def check(self, values):
        """RETURN: None; ConfigError where a transport key is refused."""
        if self._check is not None: self._check(self.transport, values)

    def __call__(self, values, note):
        """RETURN: Hub, produced from the checked 'values'."""
        return self._make(self.transport, values, note)


def producer(make, reader=entry.read, check=None):
    """
    RETURN: callable, transport -> producer, for add_plugin: 'make'
            (values, note) -> Hub wrapped with the default reader of
            'key = value' files (or 'reader'), and 'check' (transport,
            values) -> None for its own keys (none: every key passes).
    """
    return lambda transport: _Producer(transport,
                                       lambda t, values, note:
                                           make(values, note),
                                       reader, check)


_REGISTRY_DB = {}


def add_plugin(transport, plugin):
    """
    RETURN: None. 'plugin' (a producer, or what 'producer()' returns)
            registered under 'transport'.
            ConfigError, where the transport is taken.
    """
    if transport in _REGISTRY_DB:
        raise ConfigError("transport '%s' is taken" % transport)
    if not hasattr(plugin, "read"): plugin = plugin(transport)
    _REGISTRY_DB[transport] = plugin


def create_hub(transport, address=None, *, config_file=None, note=None,
               image_id=None, image=None, failures=3, **options):
    """
    RETURN: Hub, not opened, of 'transport', if its producer is registered
            and the configuration passes: the file read by the producer,
            the options over it, the address over both; the common keys
            checked by the factory, the transport's by the producer.
            ConfigError, naming what is refused, else.
    """
    plugin = _REGISTRY_DB.get(transport)
    if plugin is None:
        raise ConfigError("unknown transport '%s'; known: %s"
                          % (transport, ", ".join(sorted(_REGISTRY_DB))))
    values = dict(plugin.read(config_file))
    values.update(options)
    if address is not None: values[entry.address_key(transport)] = address
    values = entry.check_common(transport, values)
    plugin.check(values)
    hub = plugin(values, note)
    if hub.transport is None: hub.transport = transport
    return hub.expect(image_id=image_id, image=image, failures=failures)


def _link_hub(transport, values, note):
    """RETURN: LinkHub over the built-in link of 'transport'."""
    from . import link
    return LinkHub(link.open(transport, values), values, note, transport)


def _not_built(step):
    """RETURN: callable, a producer body refusing until delivery 'step'."""
    def make(transport, values, note):
        raise ConfigError("transport '%s' is not built yet (spec/26 "
                          "delivery step %i)" % (transport, step))
    return make


for _transport in ("serial", "tcp", "udp", "ssh", "launch"):
    add_plugin(_transport, _Producer(_transport, _link_hub,
                                     check=entry.check_transport))
add_plugin("can",  _Producer("can",  _not_built(9),  check=entry.check_transport))
add_plugin("visa", _Producer("visa", _not_built(12), check=entry.check_transport))
