"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: A HUB'S CONFIGURATION -- the keys, the factory's checks of the
         common ones, and the default reader of 'key = value' files
         (README 11).

The factory checks the B, D and E keys (time, boot, link_margin; loader and
its keys; power). The producer checks its transport's C keys and refuses
every other key by name. hwut reads none of it (intend o-35).
______________________________________________________________________________
"""
import os

#  The address key of each built-in transport; a plugin's is its own name.
_ADDRESS_KEY_DB = {"serial": "serial", "tcp": "tcp", "udp": "udp",
                   "ssh": "host", "launch": "launch", "can": "can",
                   "visa": "visa"}

#  The transport keys every built-in transport knows beside its address.
TRANSPORT_KEY_DB = {
    "serial": ("baud", "dtr", "rts", "low_latency"),
    "tcp":    ("baud",),
    "udp":    (),
    "ssh":    (),
    "launch": (),
    "can":    ("can_ids",),
    "visa":   ("backend",),
}

LOADER_TUPLE      = ("quartus", "openfpgaloader", "openocd", "esptool",
                     "copy", "none")
LOADER_KEY_DB     = {"quartus": ("cable",), "openfpgaloader": ("board",),
                     "openocd": ("cfg",), "esptool": ("image_offset",),
                     "copy": ("agent",), "none": ()}
COMMON_KEY_TUPLE  = ("time", "boot", "link_margin", "loader", "cable",
                     "board", "cfg", "image_offset", "agent", "power")

#  Seconds added to every deadline, per transport (README 13).
LINK_MARGIN_DB    = {"serial": 0.05, "tcp": 0.2, "udp": 0.2, "ssh": 0.5,
                     "launch": 1.0, "visa": 2.0}


class ConfigError(Exception):
    """A configuration the factory or a producer refuses, by name."""


def address_key(transport):
    """
    RETURN: str, the key whose value is the address of 'transport'
            ('host' for ssh; a plugin's own name).
    """
    return _ADDRESS_KEY_DB.get(transport, transport)


def read(config_file):
    """
    RETURN: dict, the 'key = value' lines of 'config_file', one per line,
            '#' starting a comment, a value 'true'/'false' a bool, an
            integer an int, a decimal or 'inf' a float, else a str (one
            pair of enclosing double quotes removed); {} for None.
            ConfigError, where the file cannot be read or a line is no
            'key = value'.
    """
    if config_file is None: return {}
    try:
        with open(config_file, encoding="utf-8") as fh: text = fh.read()
    except OSError as error:
        raise ConfigError("%s: %s" % (config_file, error.strerror))
    value_db = {}
    for n, line in enumerate(text.split("\n"), 1):
        line = line.split("#", 1)[0].strip() if not _quoted_hash(line) \
               else line.strip()
        if not line: continue
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not key or not value:
            raise ConfigError("%s:%i: not 'key = value': %s"
                              % (config_file, n, line))
        if key in value_db:
            raise ConfigError("%s:%i: '%s' given twice" % (config_file, n, key))
        value_db[key] = _scalar(value)
    return value_db


def _quoted_hash(line):
    """RETURN: bool, True if a '#' of 'line' stands inside double quotes."""
    head = line.split("#", 1)[0]
    return head.count('"') % 2 == 1


def _scalar(text):
    """RETURN: bool | int | float | str, the value 'text' spells."""
    if len(text) >= 2 and text[0] == text[-1] == '"': return text[1:-1]
    if text in ("true", "false"): return text == "true"
    if text == "inf":             return float("inf")
    try:
        return int(text, 0)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def check_common(transport, values):
    """
    RETURN: dict, 'values' with the common keys checked and defaulted:
            'time' wall | virtual; 'boot' a number or inf, mandatory;
            'link_margin' defaulted per transport; under virtual time
            'boot' and 'link_margin' inf; 'loader' one of LOADER_TUPLE,
            default 'none'; a placeholder ('<...>') refused.
            ConfigError, naming the key, else.
    """
    result = dict(values)
    for key, value in result.items():
        if isinstance(value, str) and value.startswith("<") \
           and value.endswith(">"):
            raise ConfigError("%s: fill in '%s'" % (transport, key))
    time_domain = result.setdefault("time", "wall")
    if time_domain not in ("wall", "virtual"):
        raise ConfigError("%s: 'time' is wall or virtual, not '%s'"
                          % (transport, time_domain))
    if "boot" not in result:
        raise ConfigError("%s: 'boot' is mandatory: the seconds the hello "
                          "may take, or inf" % transport)
    for key in ("boot", "link_margin"):
        if key in result and not _number_f(result[key]):
            raise ConfigError("%s: '%s' is seconds or inf, not '%s'"
                              % (transport, key, result[key]))
    result.setdefault("link_margin", LINK_MARGIN_DB.get(transport, 1.0))
    if time_domain == "virtual":
        result["boot"] = result["link_margin"] = float("inf")
    loader = result.setdefault("loader", "none")
    if loader not in LOADER_TUPLE:
        raise ConfigError("%s: unknown loader '%s'; known: %s"
                          % (transport, loader, ", ".join(LOADER_TUPLE)))
    for other, key_tuple in LOADER_KEY_DB.items():
        for key in key_tuple:
            if key in result and other != loader and key != "agent":
                raise ConfigError("%s: '%s' is a key of loader '%s', not "
                                  "of '%s'" % (transport, key, other, loader))
    if loader == "copy" and transport != "ssh":
        raise ConfigError("%s: loader 'copy' requires transport ssh"
                          % transport)
    if transport == "visa" and loader != "none":
        raise ConfigError("visa: requires loader none")
    return result


def check_transport(transport, values):
    """
    RETURN: None, if 'values' holds the address key of 'transport' and,
            beside the common keys, only keys of TRANSPORT_KEY_DB for it
            (a built-in transport);
            ConfigError naming the first other key, else.
    """
    own = address_key(transport)
    if not values.get(own):
        raise ConfigError("%s: no address: give it as the second argument "
                          "or as '%s = ...'" % (transport, own))
    known = set(TRANSPORT_KEY_DB.get(transport, ())) | {own} \
            | set(COMMON_KEY_TUPLE)
    for key in values:
        if key in known: continue
        if key in _ADDRESS_KEY_DB.values():
            raise ConfigError("%s: the configuration names transport key "
                              "'%s'; a hub has exactly one transport"
                              % (transport, key))
        raise ConfigError("%s: unknown key '%s'" % (transport, key))


def _number_f(value):
    """RETURN: bool, True if 'value' is an int or float, not a bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def device_path_f(path):
    """RETURN: bool, True if the device file 'path' exists."""
    return os.path.exists(path)
