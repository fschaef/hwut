#! /usr/bin/env python3
#
# @hwut {
#     title   = "list: what is attached, which file names it"
#     choices = [ "given", "directory", "nothing" ]
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'python3 -m hwut_remote list' against a fake /dev/serial/by-id, a
         fake /sys/class/net and a fake 'jtagconfig' on PATH (README 11;
         intend o-31, o-38; spec/26 delivery step 3).

CHOICES: given, directory, nothing;

    given      files named on the command line: present, absent, not
               probed; the attached named by no file: 'no file'; the tool
               not installed: '## not looked'
    directory  no file given: every file of the directory the default
               reader reads and that names one transport; the others
               skipped (o-38 (a))
    nothing    nothing attached, no file: the header and what was not looked
______________________________________________________________________________
"""
import os
import sys
import tempfile

import config                                          # noqa: F401
from   config      import HwutRunner
from   hwut_remote import listing

JTAGCONFIG = """#! /bin/sh
echo "1) USB-Blaster [1-3]"
echo "  031050DD   10M50DA(.|ES)/10M50DC"
"""


def tree(root, attached_f=True):
    """RETURN: (serial_dir, net_dir), a fake device tree under 'root'; a
    fake 'jtagconfig' first on PATH, 'openFPGALoader' and 'pyvisa' absent."""
    os.chdir(root)                         # paths relative: no machine fact
    serial = os.path.join("dev", "serial", "by-id")
    net    = os.path.join("sys", "class", "net")
    tool   = os.path.join(root, "bin")
    for directory in (serial, net, tool): os.makedirs(directory)
    if attached_f:
        for name in ("usb-Altera_USB-Blaster_91d28408-if00-port0",
                     "usb-FTDI_FT232R_A50285BI-if00-port0"):
            open(os.path.join(serial, name), "w").close()
        for name, kind in (("can0", "280"), ("eth0", "1")):
            os.makedirs(os.path.join(net, name))
            with open(os.path.join(net, name, "type"), "w") as fh:
                fh.write(kind + "\n")
        path = os.path.join(tool, "jtagconfig")
        with open(path, "w") as fh: fh.write(JTAGCONFIG)
        os.chmod(path, 0o755)
    os.environ["PATH"] = tool + ":/usr/bin:/bin"
    return serial, net


def files(root, serial):
    """RETURN: list of str, four configuration files and one that is none."""
    content_db = {
        "max10.conf": "serial = %s/usb-Altera_USB-Blaster_91d28408-if00-port0"
                      "\nboot = 1.0\nloader = quartus\n" % serial,
        "esp.conf":   "serial = %s/usb-Silicon_Labs_CP210x_0001-if00-port0"
                      "\nboot = 2.0\n" % serial,
        "sim.conf":   "launch = vvp -n TMP/uut.vvp\ntime = virtual\n"
                      "boot = inf\n",
        "notes.txt":  "the bench, as wired on 2026-11-06\n",
        "two.conf":   "serial = /dev/x\ntcp = host:1\nboot = 1\n",
    }
    for name, text in content_db.items():
        with open(name, "w") as fh: fh.write(text)
    return ["max10.conf", "esp.conf", "sim.conf"]


def show(text_list, root):
    """RETURN: None. The table; the temporary root never shows in it."""
    for text in text_list:
        assert root not in text
        print(text)


def run_given():
    """RETURN: None. Three files named."""
    with tempfile.TemporaryDirectory() as root:
        serial, net = tree(root)
        show(listing.lines(files(root, serial), serial, net), root)


def run_directory():
    """RETURN: None. No file named: the directory's."""
    with tempfile.TemporaryDirectory() as root:
        serial, net = tree(root)
        files(root, serial)
        show(listing.lines([], serial, net, cwd="."), root)


def run_nothing():
    """RETURN: None. Nothing attached, nothing named."""
    with tempfile.TemporaryDirectory() as root:
        serial, net = tree(root, attached_f=False)
        show(listing.lines([], serial, net, cwd="bin"), root)


HwutRunner(sys.argv, "list: what is attached, which file names it;", {
    "given":     run_given,
    "directory": run_directory,
    "nothing":   run_nothing,
}).run()
