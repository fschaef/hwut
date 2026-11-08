"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'python3 -m hwut_remote list [F ...]' -- what is attached to this
         machine, and which configuration file names it (README 11; intend
         o-31, o-38).

    file        transport  address                                  state
    max10.conf  serial     /dev/serial/by-id/usb-Altera_USB-Blaster_ present
    --          serial     /dev/serial/by-id/usb-FTDI_FT232R_A50285 no file

    state   present, absent: the device path exists (serial), the interface
            exists (can), pyvisa lists it (visa); not probed: the other
            transports; no file: attached, named by no file given

With no file given, every file of the current directory that the default
reader reads and that names one transport (o-38 (a)); a file it cannot
read is skipped, not refused. It looks at /dev/serial/by-id; 'jtagconfig'
and 'openFPGALoader --scan-usb' where on PATH; the CAN interfaces
(/sys/class/net, type 280); pyvisa's resources where pyvisa is installed.
A tool not installed is one '##' line. It writes nothing and opens no link.
______________________________________________________________________________
"""
import os
import re
import shutil
import subprocess

from . import entry

SERIAL_DIR = "/dev/serial/by-id"
NET_DIR    = "/sys/class/net"
_ADDRESS_TRANSPORT_DB = {entry.address_key(t): t
                         for t in entry.TRANSPORT_KEY_DB}


def lines(file_list, serial_dir=SERIAL_DIR, net_dir=NET_DIR, cwd="."):
    """
    RETURN: list of str, the table of what is attached and named, then one
            '##' line per tool not looked with.
    """
    named_list = [row for row in (_named(path, serial_dir, net_dir)
                                  for path in (file_list or _candidates(cwd)))
                  if row is not None]
    named_set  = {(row[1], row[2]) for row in named_list}
    looked, attached_list = _attached(serial_dir, net_dir)
    unnamed = sorted(row for row in attached_list
                     if (row[0], row[1]) not in named_set)
    row_list = sorted(named_list) + [("--",) + row[:2] + ("no file",)
                                     for row in unnamed]
    header = ("file", "transport", "address", "state")
    width  = [max(len(r[k]) for r in [header] + row_list) for k in range(3)]
    result = ["  ".join(r[k].ljust(width[k]) for k in range(3)) + "  " + r[3]
              for r in [header] + row_list]
    return [text.rstrip() for text in result] \
         + ["## not looked: %s" % tool for tool in looked]


def _candidates(cwd):
    """RETURN: list of str, the regular files of 'cwd', sorted."""
    return sorted(os.path.join(cwd, name) for name in os.listdir(cwd)
                  if os.path.isfile(os.path.join(cwd, name)))


def _named(path, serial_dir, net_dir):
    """
    RETURN: (file, transport, address, state) for the configuration file
            'path', if the default reader reads it and it names exactly
            one transport;
            None, else.
    """
    try:
        value_db = entry.read(path)
    except (entry.ConfigError, UnicodeDecodeError):
        return None
    found = [(_ADDRESS_TRANSPORT_DB[key], str(value))
             for key, value in value_db.items()
             if key in _ADDRESS_TRANSPORT_DB]
    if len(found) != 1: return None
    transport, address = found[0]
    return (os.path.basename(path), transport, address,
            _state(transport, address, net_dir))


def _state(transport, address, net_dir):
    """RETURN: str, 'present', 'absent' or 'not probed'."""
    if transport == "serial":
        return "present" if os.path.exists(address) else "absent"
    if transport == "can":
        return "present" if os.path.isdir(os.path.join(net_dir, address)) \
               else "absent"
    if transport == "visa":
        resource_list = _visa_resources()
        if resource_list is None: return "not probed"
        return "present" if address in resource_list else "absent"
    return "not probed"


def _attached(serial_dir, net_dir):
    """
    RETURN: (looked, rows): the tools not installed, and (transport,
            address) of everything attached.
    """
    not_looked, row_list = [], []
    if os.path.isdir(serial_dir):
        row_list += [("serial", os.path.join(serial_dir, name))
                     for name in sorted(os.listdir(serial_dir))]
    for tool, parse in (("jtagconfig", _jtagconfig),
                        ("openFPGALoader", _openfpgaloader)):
        if shutil.which(tool) is None:
            not_looked.append(tool)
            continue
        row_list += [("jtag", address) for address in parse(tool)]
    if os.path.isdir(net_dir):
        for name in sorted(os.listdir(net_dir)):
            try:
                with open(os.path.join(net_dir, name, "type")) as fh:
                    if fh.read().strip() == "280":
                        row_list.append(("can", name))
            except OSError:
                pass
    resource_list = _visa_resources()
    if resource_list is None: not_looked.append("pyvisa")
    else:                     row_list += [("visa", r) for r in resource_list]
    return not_looked, row_list


def _run(argv):
    """RETURN: str, the stdout of 'argv'; '' where it fails."""
    try:
        return subprocess.run(argv, capture_output=True, text=True,
                              timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _jtagconfig(tool):
    """RETURN: list of str, 'cable  device' for each chain jtagconfig
    lists ('1) USB-Blaster [1-3]' and its first device)."""
    result, cable = [], None
    for text in _run([tool]).splitlines():
        match = re.match(r"^\d+\)\s+(.*\S)\s*$", text)
        if match:
            if cable is not None: result.append(cable)
            cable = match.group(1)
        elif cable is not None and text.strip():
            word = text.split()
            result.append("%s  %s" % (cable, word[1].split("(")[0]
                                      if len(word) > 1 else word[0]))
            cable = None
    if cable is not None: result.append(cable)
    return result


def _openfpgaloader(tool):
    """RETURN: list of str, 'vid:pid  product' for each probe
    'openFPGALoader --scan-usb' lists."""
    result = []
    for text in _run([tool, "--scan-usb"]).splitlines():
        match = re.match(r"^\s*\S+\s+\S+\s+(0x[0-9a-f]{4}:0x[0-9a-f]{4})\s+"
                         r"(.*\S)\s*$", text)
        if match: result.append("%s  %s" % (match.group(1), match.group(2)))
    return result


def _visa_resources():
    """RETURN: list of str, pyvisa's resources; None where pyvisa is not
    installed."""
    try:
        import pyvisa
    except ImportError:
        return None
    try:
        return sorted(pyvisa.ResourceManager().list_resources())
    except Exception:                     # noqa: BLE001 -- a backend fault
        return []
