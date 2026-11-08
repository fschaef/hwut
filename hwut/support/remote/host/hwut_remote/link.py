"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE BYTES -- one channel between host and agent (README 12).

    open(transport, values) -> Link     the only constructor of a built-in
                                        channel; the hub and the loaders
                                        both use it
    Link.open()                         DeviceAbsent where the device the
                                        values name is not there
    Link.send(data)
    Link.recv(deadline) -> bytes        b"" when 'deadline' (time.monotonic)
                                        passed; EOFError at end of file
    Link.close()
    Link.datagram_f                     True: one line per datagram (udp)
    Link.repeat_hello_f                 False: the hello is sent once
                                        (ssh, launch)

Built in: serial, tcp, udp, ssh (address key 'host'), launch. 'can' is
delivery step 9:
refused here by name.
______________________________________________________________________________
"""
import os
import select
import shlex
import socket
import subprocess
import time


class DeviceAbsent(Exception):
    """The device the configuration names is not attached: the case's
    infrastructure is absent (exit 77, README 16)."""


class LinkError(Exception):
    """A channel that exists and cannot be used: busy, refused, broken."""


class Link:
    """The base: a channel of bytes. Subclasses give the five members."""
    datagram_f     = False
    repeat_hello_f = True

    def open(self):
        """RETURN: None. The channel opened; DeviceAbsent, LinkError else."""
        raise NotImplementedError

    def send(self, data):
        """RETURN: None. 'data' (bytes) written whole."""
        raise NotImplementedError

    def recv(self, deadline):
        """
        RETURN: bytes, what arrived before 'deadline' (time.monotonic());
                b"" if nothing did.
                EOFError, at end of file.
        """
        raise NotImplementedError

    def close(self):
        """RETURN: None. The channel closed; closing twice is harmless."""
        raise NotImplementedError


def _wait_readable(fd, deadline):
    """
    RETURN: bool, True if 'fd' is readable before 'deadline';
            False, else.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:             remaining = 0
    elif remaining == float("inf"): remaining = None     # virtual time
    readable, _, _ = select.select([fd], [], [], remaining)
    return bool(readable)


class ProcessLink(Link):
    """'launch': a process whose stdio is the link (vvp, qemu -serial
    stdio); 'ssh' is the same over 'ssh -T -o BatchMode=yes'."""
    repeat_hello_f = False

    def __init__(self, argv):
        """RETURN: None. A link that will start 'argv' (list of str)."""
        self.argv    = list(argv)
        self.process = None

    def open(self):
        """RETURN: None. The process started; LinkError if it cannot be."""
        try:
            self.process = subprocess.Popen(self.argv, stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL,
                                            bufsize=0)
        except OSError as error:
            raise LinkError("launch '%s': %s"
                            % (" ".join(self.argv), error.strerror))

    def send(self, data):
        """RETURN: None. 'data' to the process's stdin; EOFError if gone."""
        try:
            self.process.stdin.write(data)
            self.process.stdin.flush()
        except (BrokenPipeError, ValueError):
            raise EOFError("the process ended")

    def recv(self, deadline):
        """RETURN: bytes before 'deadline'; b"" else; EOFError at its end."""
        fd = self.process.stdout.fileno()
        if not _wait_readable(fd, deadline): return b""
        data = os.read(fd, 4096)
        if not data: raise EOFError("the process ended")
        return data

    def close(self):
        """RETURN: None. stdin closed, the process ended (killed if it
        lingers)."""
        if self.process is None: return
        process, self.process = self.process, None
        try:
            process.stdin.close()
        except OSError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdout.close()


class SocketLink(Link):
    """'tcp' (a stream) and 'udp' (one line per datagram, each way)."""

    def __init__(self, address, datagram_f):
        """RETURN: None. A link to 'address' ("host:port")."""
        host, _, port = address.rpartition(":")
        if not host or not port.isdigit():
            raise LinkError("'%s' is no host:port" % address)
        self.address    = (host, int(port))
        self.datagram_f = datagram_f
        self.sock       = None

    def open(self):
        """RETURN: None. Connected; LinkError where refused."""
        kind = socket.SOCK_DGRAM if self.datagram_f else socket.SOCK_STREAM
        try:
            self.sock = socket.socket(socket.AF_INET, kind)
            self.sock.connect(self.address)
        except OSError as error:
            raise LinkError("%s %s:%i: %s"
                            % ("udp" if self.datagram_f else "tcp",
                               self.address[0], self.address[1],
                               error.strerror or error))

    def send(self, data):
        """RETURN: None. 'data' sent; on udp one datagram per line."""
        if not self.datagram_f:
            self.sock.sendall(data)
            return
        for line in data.split(b"\n"):
            if line: self.sock.send(line + b"\n")

    def recv(self, deadline):
        """RETURN: bytes before 'deadline'; b"" else; EOFError at its end."""
        if not _wait_readable(self.sock.fileno(), deadline): return b""
        data = self.sock.recv(4096)
        if not data and not self.datagram_f: raise EOFError("closed by peer")
        return data

    def close(self):
        """RETURN: None."""
        if self.sock is not None: self.sock.close()
        self.sock = None


class SerialLink(Link):
    """'serial': a UART device, raw, exclusive; DTR/RTS set before use."""

    def __init__(self, device, baud, dtr=None, rts=None):
        """RETURN: None. A link to 'device' at 'baud'."""
        self.device = device
        self.baud   = baud
        self.dtr    = dtr
        self.rts    = rts
        self.fd     = None

    def open(self):
        """
        RETURN: None. The port opened raw at 'baud', exclusive, input
                flushed.
                DeviceAbsent, where the device does not exist;
                LinkError, where it is held by another process.
        """
        import fcntl
        import termios
        if not os.path.exists(self.device):
            raise DeviceAbsent("no device %s" % self.device)
        try:
            self.fd = os.open(self.device, os.O_RDWR | os.O_NOCTTY)
        except OSError as error:
            raise LinkError("%s: %s" % (self.device, error.strerror))
        try:
            fcntl.ioctl(self.fd, termios.TIOCEXCL)
        except OSError:
            pass
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self.fd)
            self.fd = None
            raise LinkError("bench busy: %s is held by another process"
                            % self.device)
        attr = termios.tcgetattr(self.fd)
        speed = getattr(termios, "B%i" % self.baud, None)
        if speed is None: raise LinkError("baud %i unknown" % self.baud)
        attr[0] = 0                                       # iflag
        attr[1] = 0                                       # oflag
        attr[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attr[3] = 0                                       # lflag
        attr[4] = attr[5] = speed
        termios.tcsetattr(self.fd, termios.TCSANOW, attr)
        self._lines()
        termios.tcflush(self.fd, termios.TCIFLUSH)

    def _lines(self):
        """RETURN: None. DTR and RTS set where the values name them;
        False = deasserted."""
        import fcntl
        import struct
        import termios
        for level, bit in ((self.dtr, termios.TIOCM_DTR),
                           (self.rts, termios.TIOCM_RTS)):
            if level is None: continue
            request = termios.TIOCMBIS if level else termios.TIOCMBIC
            fcntl.ioctl(self.fd, request, struct.pack("I", bit))

    def send(self, data):
        """RETURN: None. 'data' written whole."""
        view = memoryview(data)
        while view: view = view[os.write(self.fd, view):]

    def recv(self, deadline):
        """RETURN: bytes before 'deadline'; b"" else; EOFError if the port
        vanished."""
        if not _wait_readable(self.fd, deadline): return b""
        try:
            data = os.read(self.fd, 4096)
        except OSError:
            raise EOFError("%s vanished" % self.device)
        if not data: raise EOFError("%s vanished" % self.device)
        return data

    def close(self):
        """RETURN: None."""
        if self.fd is not None: os.close(self.fd)
        self.fd = None


def open(transport, values):
    """
    RETURN: Link, not yet opened, for 'transport' and the checked 'values'
            (dict) if the transport is built in;
            LinkError, else.
    """
    from .entry import address_key
    address = values.get(address_key(transport))
    if transport == "launch":
        return ProcessLink(shlex.split(address))
    if transport == "ssh":
        return ProcessLink(["ssh", "-T", "-o", "BatchMode=yes", address,
                            "exec", values.get("agent", "")])
    if transport in ("tcp", "udp"):
        return SocketLink(address, transport == "udp")
    if transport == "serial":
        return SerialLink(address, int(values.get("baud", 115200)),
                          values.get("dtr"), values.get("rts"))
    raise LinkError("transport '%s' has no built-in link%s"
                    % (transport, " (can: delivery step 9)"
                                  if transport == "can" else ""))
