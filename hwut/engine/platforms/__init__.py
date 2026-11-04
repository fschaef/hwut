"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE PLATFORMS HELPER (intend/42, rulings 14, 16, 20) -- where a
         bubble runs, asked of the platform's KIND.

    is_available(name, spec)              may the platform run a bubble now
    start(name, spec, write)              made ready (an image built)
    run(name, spec, bubble, wish, sink)   the bubble run there, its events
                                          into 'sink'
    relay(name, spec, bubble_path, directory, argv, write)
                                          a face run there, its lines into
                                          'write' ('hwut.play')
    stop(name, spec)                      left as found
    keys(kind)                            the keys a kind knows
    check(name, spec)                     the faults of an entry's own keys
    kind_tuple()                          the kinds a conf may name

'spec' is the platform's entry in a 'hwut-root.conf', as read: hwut
knows 'name' and 'kind'; every other key is the kind's (ruling 14).
'local' is the reserved platform (ruling 16): no entry, no keys, always
available -- the machine this hwut runs on.

THE ENGINE IMPORTS NOTHING OF THE FACES: this package imports only the
engine and the standard library (spec/42 section 4).
______________________________________________________________________________
"""
from . import container
from . import local

LOCAL = "local"

#  THE KINDS A CONF MAY NAME (ruling 15: built in, no plugins). 'local' is
#  no kind: it is the reserved name, and has no entry to carry one.
_KIND_DB = {
    "container": container,
}


def kind_tuple():
    """
    RETURN: tuple of str, the kinds a 'platform' entry may name, sorted
            -- the list a fault for an unknown kind shows.
    """
    return tuple(sorted(_KIND_DB))


def keys(kind):
    """
    RETURN: tuple of str, the keys the kind knows beside 'name' and
            'kind', in the order its documentation gives them, if 'kind'
            is one of 'kind_tuple()'.
            None, else.
    """
    module = _KIND_DB.get(kind)
    return None if module is None else module.KEY_TUPLE


def check(name, spec):
    """
    RETURN: tuple of (str, str), one (key, text) per fault of the entry's
            own keys -- the keys beside 'name' and 'kind', which only the
            kind knows (ruling 14): a key it does not know, a key it
            needs and does not find, a value it cannot take. 'key' is the
            key the fault stands at; 'text' one line naming the platform.
            Empty, where the kind takes the entry as it stands.

    'spec["kind"]' must be one of 'kind_tuple()': the conf's reader
    refuses an unknown kind before it asks.
    """
    return _module_of(name, spec).check(name, spec)


def is_available(name, spec):
    """
    RETURN: (True, ""), the platform 'name' can run a bubble now.
            (False, why), else -- 'why' one line, the text of the NOTE
            beside '[PLATFORM not reachable]'.
    """
    return _module_of(name, spec).is_available(name, spec)


def start(name, spec, write, log=None):
    """
    RETURN: (True, ""), the platform is ready to run a bubble.
            (False, why), else -- what went wrong already said by
            'write' where it is more than 'why'.

    'write' takes one console line; 'log' one line for the run's log
    (dropped where None).
    """
    return _module_of(name, spec).start(name, spec, write, log)


def run(name, spec, bubble, wish, sink, root=None):
    """
    RETURN: int, the far run's exit status. Every far event reached
            'sink' as it happened, a local event's shape, its
            'directory' relative to the near root (ruling 20).

    'bubble' is the bubble's directory relative to 'root', the near
    run's root (the working directory where None); 'wish' the list of
    words the far 'hwut.run' takes for it.
    """
    return _module_of(name, spec).run(name, spec, bubble, wish, sink,
                                      root=root)


def relay(name, spec, bubble_path, directory, argv, write):
    """
    RETURN: int, the far face's exit status. 'argv' -- the face's path
            first, under the hwut's own 'bin/' -- ran there in
            'directory', inside the bubble at 'bubble_path' (both
            absolute); each line it printed reached 'write' as it came.

    A face that RUNS a test and shows what it read ('hwut.play', ruling 7)
    dives to the platform as 'hwut.run' does; what it shows is text, not
    events, so it is relayed, not translated.
    """
    return _module_of(name, spec).relay(name, spec, bubble_path, directory,
                                        argv, write)


def stop(name, spec):
    """
    RETURN: None. The platform left as it was found; called in a
            'finally', a signal included (E-55).
    """
    _module_of(name, spec).stop(name, spec)


def _module_of(name, spec):
    """
    RETURN: module, the one that serves platform 'name' -- 'local' for
            the reserved name, else the module of 'spec["kind"]'.

    Raises KeyError where the kind is not known: the conf's reader
    refuses that before any service is asked.
    """
    if name == LOCAL: return local
    return _KIND_DB[spec["kind"]]
