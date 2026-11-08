#! /usr/bin/env python3
#
# @hwut {
#     title   = "The factory: registry, configuration file, plugins"
#     choices = [ "used", "taken", "keys", "file", "refused", "absent" ]
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: create_hub and add_plugin (README 11; intend o-37; spec/26 delivery
         step 1).

CHOICES: used, taken, keys, file, refused, absent;

    used     a plugin's producer makes the hub; the session runs over its
             link exactly as over a built-in one
    taken    a transport registered twice is refused
    keys     a plugin's own keys pass to its producer; the factory checks
             the common ones
    file     a configuration file read by the producer; the options over
             the file; the address over both; the hub NOT opened
    refused  what the factory refuses, by name: an unknown transport, a
             missing 'boot', a second transport key, an unknown key, a
             placeholder, a loader key of another loader
    absent   a serial device that is not there: the stderr line and exit 77
             (a child process, so the exit is seen)
______________________________________________________________________________
"""
import os
import random
import subprocess
import sys
import tempfile

import config                                          # noqa: F401
from   config      import HwutRunner
from   fake_agent  import Agent, FakeLink
import hwut_remote
from   hwut_remote import create_hub, add_plugin, producer, LinkHub, \
                          ConfigError


def note(text):
    """RETURN: None. A '##' line."""
    print("##", text)


def run_used():
    """RETURN: None. A session over a plugin's link."""
    random.seed(3)
    add_plugin("bridge", producer(lambda values, note:
                                  LinkHub(FakeLink(Agent()), values, note)))
    hub = create_hub("bridge", "usb:1-3", boot=0.3, link_margin=0.05,
                     note=note)
    print("hub:", type(hub).__name__, hub.transport, "open:", hub.open_f)
    with hub:
        hub.reset()
        print("0304 %03x" % hub.vector(0x0304))
    print("open:", hub.open_f)


def run_taken():
    """RETURN: None. A transport taken twice; a built-in one taken."""
    add_plugin("bridge", producer(lambda values, note: None))
    for name in ("bridge", "serial"):
        try:
            add_plugin(name, producer(lambda values, note: None))
        except ConfigError as error:
            print("refused:", error)


def run_keys():
    """RETURN: None. A plugin's keys reach its producer as given."""
    seen = {}

    def make(values, note):
        seen.update(values)
        return LinkHub(FakeLink(Agent()), values, note)
    add_plugin("mqtt", producer(make))
    create_hub("mqtt", "broker:1883", boot=2.0, topic="lab/adder", qos=1)
    for key in sorted(seen): print("%-12s %r" % (key, seen[key]))


def run_file():
    """RETURN: None. A file, the options over it, the address over both."""
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "max10.conf")
        with open(path, "w") as fh:
            fh.write("# the board on the author's bench\n"
                     "serial = /dev/serial/by-id/usb-Altera_USB-Blaster\n"
                     "baud = 115200\n"
                     "low_latency = true\n"
                     "boot = 1.0\n"
                     "loader = quartus\n"
                     "cable = \"USB-Blaster [1-3]\"\n")
        hub = create_hub("serial", config_file=path, baud=57600)
        show(hub)
        hub = create_hub("serial", "/dev/serial/by-id/other",
                         config_file=path)
        print("address:", hub.values["serial"])
        print("open:", hub.open_f)


def show(hub):
    """RETURN: None. The hub's checked values, sorted."""
    for key in sorted(hub.values):
        print("%-12s %r" % (key, hub.values[key]))


def run_refused():
    """RETURN: None. Each refusal, by name."""
    case_list = [
        ("unknown transport", lambda: create_hub("bluetooth", "x", boot=1)),
        ("no boot",           lambda: create_hub("serial", "/dev/x")),
        ("two transports",    lambda: create_hub("serial", "/dev/x", boot=1,
                                                 tcp="host:1")),
        ("unknown key",       lambda: create_hub("serial", "/dev/x", boot=1,
                                                 speed=9600)),
        ("placeholder",       lambda: create_hub("serial", "<device>",
                                                 boot=1)),
        ("other loader's",    lambda: create_hub("serial", "/dev/x", boot=1,
                                                 loader="openocd",
                                                 cable="USB-Blaster")),
        ("no address",        lambda: create_hub("tcp", boot=1)),
        ("bad time",          lambda: create_hub("launch", "vvp a", boot=1,
                                                 time="model")),
        ("not built yet",     lambda: create_hub("can", "can0", boot=1)),
    ]
    for name, call in case_list:
        try:
            call()
            print("%-17s accepted (!)" % name)
        except ConfigError as error:
            print("%-17s %s" % (name, error))


def run_absent():
    """RETURN: None. A child opens a hub on a device that is not there."""
    child = ("import sys; sys.path.insert(0, %r)\n"
             "from hwut_remote import create_hub\n"
             "with create_hub('serial', '/dev/serial/by-id/usb-no-such-board',"
             " boot=1.0) as hub:\n"
             "    print('opened (!)')\n"
             % os.path.dirname(os.path.dirname(hwut_remote.__file__)))
    done = subprocess.run([sys.executable, "-c", child], capture_output=True,
                          text=True)
    print("stdout: %r" % done.stdout)
    print("stderr: %r" % done.stderr)
    print("exit:   %i" % done.returncode)


HwutRunner(sys.argv, "The factory: registry, configuration file, plugins;", {
    "used":    run_used,
    "taken":   run_taken,
    "keys":    run_keys,
    "file":    run_file,
    "refused": run_refused,
    "absent":  run_absent,
}).run()
