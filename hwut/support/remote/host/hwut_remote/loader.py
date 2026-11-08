"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE LOADER STRATEGIES of a Hub -- 'flash' and the bench 'reset',
         chosen by the configuration's 'loader' (README 14, 15).

    flash(hub, image, image_id) -> str     open; hello: the image running
                                           = image_id: "already on the
                                           board"; else close, flash, reopen,
                                           confirm
    reset(hub, image) -> str               with the link closed

Built here: 'none' (launch: the image is the command's argument). The
vendor loaders arrive in their delivery steps, each as a module of its own
with the same two functions: quartus (4), openocd, esptool, copy (5),
openfpgaloader (8). Until then they are refused by name.
______________________________________________________________________________
"""
from .session import HubError, run_command

_STEP_DB = {"quartus": 4, "openocd": 5, "esptool": 5, "copy": 5,
            "openfpgaloader": 8}


def _strategy(hub):
    """RETURN: module, the loader module the hub's 'loader' names;
    HubError where it is not built yet."""
    name = hub.values.get("loader", "none")
    if name == "none": return None
    raise HubError("loader '%s' is not built yet (spec/26 delivery step %i)"
                   % (name, _STEP_DB[name]))


def flash(hub, image, image_id):
    """
    RETURN: str, what happened, if the image with 'image_id' runs on the
            target afterwards;
            HubError, else; exit 77 where the device is absent.
    """
    module = _strategy(hub)
    expected, hub.image_id = hub.image_id, None     # the hello must not
    try:                                            # refuse a stale image
        with hub: running = _running_image(hub)
    finally:
        hub.image_id = expected
    if image_id is not None and running == image_id:
        return "already on the board: image %08x" % image_id
    if module is not None:
        return module.flash(hub, image, image_id)
    if image_id is None:
        return "nothing to flash: loader none, image %08x running" % running
    raise HubError("stale agent: image %08x running, %08x built; loader "
                   "none cannot flash" % (running, image_id))


def _running_image(hub):
    """RETURN: int, the image id the agent's hello reported."""
    data = hub.read(0x08, 4)
    return int.from_bytes(data, "little")


def reset(hub, image=None):
    """
    RETURN: str, the bench reset done, the hub closed: 'power' first where
            set; then reopen (launch, ssh, and loader none); the vendor
            loaders' reset in their modules.
    """
    hub.close()
    done = []
    if hub.values.get("power"):
        run_command(hub.values["power"])
        done.append("power")
    if hub.transport in ("launch", "ssh") or _strategy(hub) is None:
        done.append("reopen")
        return ", ".join(done)
    module = _strategy(hub)
    done.append(module.reset(hub, image))
    return ", ".join(done)
