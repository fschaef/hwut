"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CLI -- the same factory as a test's 'create_hub' (README 11).

    python3 -m hwut_remote <transport> [<address>] [--config-file F]
                           [--<key> V ...]
                           flash <image> (<image-id> | --image-id-file F)
                         | reset [<image>]
    python3 -m hwut_remote list [F ...]

'flash' and 'reset' print what happened and exit 0; a refusal or failure
exits 1 with its text; a device that is absent exits 77, its text the last
line of stderr. 'list' writes nothing and opens no link.
______________________________________________________________________________
"""
import sys

from .         import create_hub, ConfigError, HubError, LinkError
from .         import listing
from .entry    import _scalar

USAGE = """\
usage: python3 -m hwut_remote <transport> [<address>] [--config-file F]
                              [--<key> V ...]
                              flash <image> (<image-id> | --image-id-file F)
                            | reset [<image>]
       python3 -m hwut_remote list [F ...]"""


def main(argv):
    """RETURN: int, the exit status of the command 'argv' names."""
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv else 1
    if argv[0] == "list":
        for text in listing.lines(argv[1:]): print(text)
        return 0
    try:
        transport, address, options, verb, rest = _parse(argv)
        hub = create_hub(transport, address, **options)
        if verb == "flash":
            image, image_id = _flash_arguments(rest)
            print(hub.flash(image, image_id))
        else:
            if len(rest) > 1: raise ConfigError("reset takes one <image>")
            print(hub.reset_bench(rest[0] if rest else None))
    except (ConfigError, HubError, LinkError) as error:
        sys.stderr.write("hwut_remote: %s\n" % error)
        return 1
    return 0


def _parse(argv):
    """
    RETURN: (transport, address | None, options dict, verb, rest list) of
            the command line;
            ConfigError, where it names no 'flash' or 'reset'.
    """
    transport, address, options = argv[0], None, {}
    i = 1
    if i < len(argv) and not argv[i].startswith("--") \
       and argv[i] not in ("flash", "reset"):
        address, i = argv[i], i + 1
    while i < len(argv) and argv[i].startswith("--"):
        key = argv[i][2:].replace("-", "_")
        if i + 1 >= len(argv): raise ConfigError("--%s wants a value" % key)
        options[key] = argv[i + 1] if key == "config_file" \
                       else _scalar(argv[i + 1])
        i += 2
    if i >= len(argv) or argv[i] not in ("flash", "reset"):
        raise ConfigError("name 'flash' or 'reset'\n" + USAGE)
    return transport, address, options, argv[i], argv[i + 1:]


def _flash_arguments(rest):
    """RETURN: (image, image_id int) of 'flash <image> (<id> |
    --image-id-file F)'; ConfigError else."""
    if len(rest) == 3 and rest[1] == "--image-id-file":
        try:
            with open(rest[2]) as fh: text = fh.read().strip()
        except OSError as error:
            raise ConfigError("%s: %s" % (rest[2], error.strerror))
        return rest[0], int(text, 16)
    if len(rest) == 2:
        return rest[0], int(rest[1], 16)
    raise ConfigError("flash <image> (<image-id> | --image-id-file F)")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
