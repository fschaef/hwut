"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: EventChannelParameter - everything needed to construct a Channel.

ONE class, with classmethod factories per transport flavour. The flat
design is deliberate (vs. an ABC with per-transport subclasses): keeping
the API surface minimal at the cost of less type-checking inside.

USAGE

The factory creates an ECP PAIR - one for each side of the connection.
The 'A' side and 'B' side ECPs are mirror images: A's send-queue is
B's receive-queue and vice versa.

    a_ecp, b_ecp = EventChannelParameter.for_async()
    a_ecp, b_ecp = EventChannelParameter.for_thread()
    a_ecp, b_ecp = EventChannelParameter.for_process()
    a_ecp, b_ecp = EventChannelParameter.for_remote(host=..., port=...)

For PROCESS and REMOTE, the ECPs are designed to survive being passed
through the spawning mechanism (pickling for multiprocessing; manual
hand-off for remote). For ASYNC and THREAD, the ECPs are NOT passable
across a process boundary - but they do not need to be, since async
and thread spawning share memory.


ENCRYPTION: THE CipherSpec

The serialising transports (PROCESS, REMOTE) may carry a CipherSpec -
a small, picklable, SECRET-FREE description of which Cipher to use and
where its key material lives. The ECP NEVER carries key bytes:

  -- A secret inside a pickled ECP leaks (pipe buffers, swap, logs).
  -- For for_remote(), an ECP carrying the key would be sending the
     key over the very channel it secures.

So the CipherSpec carries a key REFERENCE (an environment-variable
name, or a file path), never the key. make_channel() resolves the
reference locally - on whichever side is building the channel - and
constructs the real Cipher there.

    a_ecp, b_ecp = EventChannelParameter.for_remote(
        host = "10.0.0.5", port = 9000,
        cipher_spec = CipherSpec.fernet_env("VUT_FERNET_KEY"),
    )

In-process transports (ASYNC, THREAD) never serialise and ignore any
CipherSpec - they always use IdentityCipher.

See cipher.py for the secrecy-vs-identity discussion: an ephemeral
exchange gives encryption but NOT peer authentication; a pre-shared
key or pinned peer key is what authenticates.


make_channel()

EventTerminal.start() calls ecp.make_channel() to build the actual
EventChannel. For PROCESS and REMOTE, make_channel() also runs the
Cipher handshake (channel.connect()) so the returned channel is fully
secured before the Terminal uses it.
________________________________________________________________________________
"""
import asyncio
import os
import queue as _queue
import multiprocessing

from enum        import Enum, auto

from vut.engine.event.channel.channel import (AsyncChannel,
                                              ThreadChannel,
                                              ProcessChannel,
                                              RemoteChannel,
                                              EventChannel)
from vut.engine.event.channel.cipher  import (Cipher,
                                              IdentityCipher,
                                              FernetCipher,
                                              NaClBoxCipher,
                                              TLSCipher)


# ============================================================================
# CipherSpec - a picklable, secret-free recipe for building a Cipher
# ============================================================================

class E_CipherKind(Enum):
    """Discriminator for CipherSpec."""
    IDENTITY = auto()       # no encryption (the default)
    FERNET   = auto()       # symmetric, cryptography.fernet
    NACL_BOX = auto()       # public-key, PyNaCl Box
    TLS      = auto()       # TLS via ssl.SSLContext


class CipherSpec:
    """A picklable, SECRET-FREE description of a Cipher to construct.

    Carries the cipher kind plus REFERENCES to key material (env-var
    names, file paths) - never the key bytes themselves. build()
    resolves the references locally and returns a live Cipher.

    Construct via the classmethod factories, not directly.
    """

    def __init__(self, kind: E_CipherKind, params: dict):
        """RETURN: a new CipherSpec. Use the factories instead."""
        self.kind   = kind
        self.params = params

    # ----- factories ----------------------------------------------------

    @classmethod
    def identity(cls) -> "CipherSpec":
        """RETURN: CipherSpec, the no-encryption pass-through spec."""
        return cls(E_CipherKind.IDENTITY, {})

    @classmethod
    def fernet_ephemeral(cls) -> "CipherSpec":
        """RETURN: CipherSpec, a FernetCipher using ephemeral X25519 exchange.

        ENCRYPTED but NOT AUTHENTICATED - no shared anchor. Safe only
        where a man-in-the-middle is impossible. See cipher.py.
        """
        return cls(E_CipherKind.FERNET, {"mode": "ephemeral"})

    @classmethod
    def fernet_env(cls, env_var: str) -> "CipherSpec":
        """RETURN: CipherSpec, a FernetCipher keyed from an environment variable.

        env_var names the environment variable holding the urlsafe-
        base64 Fernet key. The key is read on the side that calls
        build(), never carried in the spec. This mode is AUTHENTICATED
        (the shared key is the anchor).
        """
        return cls(E_CipherKind.FERNET, {"mode": "env", "env_var": env_var})

    @classmethod
    def fernet_file(cls, key_path: str) -> "CipherSpec":
        """RETURN: CipherSpec, a FernetCipher keyed from a file.

        key_path names a file whose contents are the Fernet key. Read
        locally at build() time. AUTHENTICATED.
        """
        return cls(E_CipherKind.FERNET, {"mode": "file", "key_path": key_path})

    @classmethod
    def nacl_box_env(cls,
                     private_env:      str,
                     peer_public_env:  "str | None" = None) -> "CipherSpec":
        """RETURN: CipherSpec, a NaClBoxCipher keyed from environment variables.

        private_env      names the env var with this side's raw 32-byte
                         Curve25519 private key (hex-encoded).
        peer_public_env  optionally names the env var with the peer's
                         expected public key (hex-encoded) for pinning.
                         If given, the channel is AUTHENTICATED; if
                         omitted, ENCRYPTED but not authenticated.
        """
        return cls(E_CipherKind.NACL_BOX, {
            "mode":            "env",
            "private_env":     private_env,
            "peer_public_env": peer_public_env,
        })

    @classmethod
    def tls(cls,
            certfile:           "str | None" = None,
            keyfile:            "str | None" = None,
            cafile:             "str | None" = None,
            server_side:        bool         = False,
            verify:             bool         = True) -> "CipherSpec":
        """RETURN: CipherSpec, a TLSCipher.

        certfile / keyfile  paths to this side's certificate and
                            private key (server end needs these; a
                            client may need them for mutual TLS).
        cafile              path to the CA bundle used to verify the
                            peer's certificate.
        server_side         True for the TLS server end.
        verify              if True (default), the peer certificate is
                            verified - the channel is AUTHENTICATED.
                            If False, encryption only.

        All of certfile/keyfile/cafile are PATHS, resolved locally at
        build() time. No certificate or key bytes travel in the spec.
        """
        return cls(E_CipherKind.TLS, {
            "certfile":    certfile,
            "keyfile":     keyfile,
            "cafile":      cafile,
            "server_side": server_side,
            "verify":      verify,
        })

    # ----- build --------------------------------------------------------

    def build(self) -> Cipher:
        """RETURN: Cipher, a live Cipher built from this spec.

        Resolves any key references (environment variables, files)
        LOCALLY - on whichever side calls this. Called by
        make_channel() on the side constructing the channel.
        """
        k = self.kind
        p = self.params

        if k is E_CipherKind.IDENTITY:
            return IdentityCipher()

        if k is E_CipherKind.FERNET:
            mode = p["mode"]
            if mode == "ephemeral":
                return FernetCipher(key=None)
            if mode == "env":
                key = os.environ.get(p["env_var"])
                if key is None:
                    raise ValueError(
                        "CipherSpec.build: environment variable %r not set "
                        "(Fernet key)." % p["env_var"]
                    )
                return FernetCipher(key=key.encode("ascii"))
            if mode == "file":
                with open(p["key_path"], "rb") as fh:
                    return FernetCipher(key=fh.read().strip())
            raise ValueError("CipherSpec.build: unknown fernet mode %r" % mode)

        if k is E_CipherKind.NACL_BOX:
            priv_hex = os.environ.get(p["private_env"])
            if priv_hex is None:
                raise ValueError(
                    "CipherSpec.build: environment variable %r not set "
                    "(NaCl private key)." % p["private_env"]
                )
            private = bytes.fromhex(priv_hex)
            peer_public = None
            if p.get("peer_public_env"):
                pub_hex = os.environ.get(p["peer_public_env"])
                if pub_hex is not None:
                    peer_public = bytes.fromhex(pub_hex)
            return NaClBoxCipher(private_key=private,
                                 expected_peer_public=peer_public)

        if k is E_CipherKind.TLS:
            import ssl
            if p["server_side"]:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                if p["certfile"]:
                    ctx.load_cert_chain(certfile=p["certfile"],
                                        keyfile=p["keyfile"])
            else:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                if p["certfile"]:
                    ctx.load_cert_chain(certfile=p["certfile"],
                                        keyfile=p["keyfile"])
            if p["cafile"]:
                ctx.load_verify_locations(cafile=p["cafile"])
            if not p["verify"]:
                ctx.check_hostname = False
                ctx.verify_mode    = ssl.CERT_NONE
            return TLSCipher(ssl_context=ctx, server_side=p["server_side"])

        raise ValueError("CipherSpec.build: unknown cipher kind %r" % k)


# ============================================================================
# E_TransportKind
# ============================================================================

class E_TransportKind(Enum):
    """Discriminator for EventChannelParameter."""
    ASYNC   = auto()
    THREAD  = auto()
    PROCESS = auto()
    REMOTE  = auto()


# ============================================================================
# EventChannelParameter
# ============================================================================

class EventChannelParameter:
    """Everything needed to construct an EventChannel.

    Single class, switched internally on .kind. The kind discriminates
    the .params dict, whose keys depend on the kind:

        ASYNC    -> { in_q:  asyncio.Queue, out_q:  asyncio.Queue }
        THREAD   -> { in_q:  queue.Queue,   out_q:  queue.Queue   }
        PROCESS  -> { in_q:  mp.Queue,      out_q:  mp.Queue      }
        REMOTE   -> { host:  str, port: int, mode:  "listen" | "connect" }

    .cipher_spec is a CipherSpec (default: identity). It is meaningful
    only for PROCESS and REMOTE; ASYNC and THREAD ignore it.

    Validation of params is done inside make_channel(), not at
    construction.
    """

    def __init__(self, kind: E_TransportKind, params: dict,
                       cipher_spec: "CipherSpec | None" = None):
        """RETURN: a new EventChannelParameter.

        Direct construction is allowed but discouraged. Use the
        for_* classmethods instead.
        """
        self.kind        = kind
        self.params      = params
        self.cipher_spec = cipher_spec if cipher_spec is not None \
                           else CipherSpec.identity()

    # ----------------------------------------------------------------
    # Factories - each returns (a_ecp, b_ecp) as mirror images.
    # ----------------------------------------------------------------

    @classmethod
    def for_async(cls) -> "tuple[EventChannelParameter, EventChannelParameter]":
        """RETURN: (a_ecp, b_ecp), a pair connected by asyncio.Queues.

        Both sides must be used on the SAME asyncio event loop.
        In-process: no CipherSpec (always IdentityCipher).
        """
        q_ab = asyncio.Queue()                          # A sends, B receives
        q_ba = asyncio.Queue()                          # B sends, A receives
        a = cls(E_TransportKind.ASYNC, {"in_q": q_ba, "out_q": q_ab})
        b = cls(E_TransportKind.ASYNC, {"in_q": q_ab, "out_q": q_ba})
        return a, b

    @classmethod
    def for_thread(cls) -> "tuple[EventChannelParameter, EventChannelParameter]":
        """RETURN: (a_ecp, b_ecp), a pair connected by thread queues.

        In-process: no CipherSpec (always IdentityCipher).
        """
        q_ab = _queue.Queue()
        q_ba = _queue.Queue()
        a = cls(E_TransportKind.THREAD, {"in_q": q_ba, "out_q": q_ab})
        b = cls(E_TransportKind.THREAD, {"in_q": q_ab, "out_q": q_ba})
        return a, b

    @classmethod
    def for_process(cls,
                    cipher_spec: "CipherSpec | None" = None) \
            -> "tuple[EventChannelParameter, EventChannelParameter]":
        """RETURN: (a_ecp, b_ecp), a pair connected by multiprocessing.Queue.

        Either ECP may be passed (via multiprocessing args) to the
        spawned process. The ECP is picklable; the queues are picklable
        by design; the CipherSpec is picklable (it holds no secrets).

        cipher_spec defaults to identity (no encryption). A non-identity
        spec is carried on BOTH ECPs so both sides build the same
        Cipher.
        """
        q_ab = multiprocessing.Queue()
        q_ba = multiprocessing.Queue()
        a = cls(E_TransportKind.PROCESS, {"in_q": q_ba, "out_q": q_ab},
                cipher_spec=cipher_spec)
        b = cls(E_TransportKind.PROCESS, {"in_q": q_ab, "out_q": q_ba},
                cipher_spec=cipher_spec)
        return a, b

    @classmethod
    def for_remote(cls, host: str, port: int,
                   cipher_spec: "CipherSpec | None" = None) \
            -> "tuple[EventChannelParameter, EventChannelParameter]":
        """RETURN: (a_ecp, b_ecp), a pair for cross-machine connection.

        a_ecp is the LISTEN end; b_ecp is the CONNECT end. Only b_ecp
        travels to the remote machine in a real deployment.

        cipher_spec defaults to identity. For a REMOTE channel, an
        identity cipher means PLAINTEXT on the network - a real
        deployment should pass a real CipherSpec. Note for TLS: the
        listen end needs server_side=True and the connect end
        server_side=False, so the two ends generally need DIFFERENT
        TLS specs; pass them by constructing the pair's ECPs
        individually, or use a symmetric cipher (Fernet / NaCl) whose
        spec is identical on both ends.
        """
        a = cls(E_TransportKind.REMOTE,
                {"host": host, "port": port, "mode": "listen"},
                cipher_spec=cipher_spec)
        b = cls(E_TransportKind.REMOTE,
                {"host": host, "port": port, "mode": "connect"},
                cipher_spec=cipher_spec)
        return a, b

    # ----------------------------------------------------------------
    # Channel construction
    # ----------------------------------------------------------------

    async def make_channel(self) -> EventChannel:
        """RETURN: EventChannel, constructed from this ECP, cipher handshake done.

        Called by EventTerminal at start-up. For PROCESS and REMOTE,
        the Cipher is built from cipher_spec and its handshake is run
        (channel.connect()) so the returned channel is fully secured
        before the Terminal uses it.
        """
        k = self.kind
        p = self.params

        if k is E_TransportKind.ASYNC:
            return AsyncChannel(in_q=p["in_q"], out_q=p["out_q"])

        if k is E_TransportKind.THREAD:
            return ThreadChannel(in_q=p["in_q"], out_q=p["out_q"])

        if k is E_TransportKind.PROCESS:
            cipher  = self.cipher_spec.build()
            channel = ProcessChannel(in_q=p["in_q"], out_q=p["out_q"],
                                          cipher=cipher)
            await channel.connect()             # runs cipher handshake
            return channel

        if k is E_TransportKind.REMOTE:
            host = p["host"]
            port = p["port"]
            mode = p["mode"]
            if mode == "listen":
                ready_q: asyncio.Queue = asyncio.Queue(maxsize=1)
                async def _on_conn(reader, writer):
                    await ready_q.put((reader, writer))
                server = await asyncio.start_server(_on_conn, host, port)
                reader, writer = await ready_q.get()
                server.close()
                await server.wait_closed()
                cipher  = self.cipher_spec.build()
                channel = RemoteChannel(reader=reader, writer=writer,
                                        cipher=cipher)
                await channel.connect()
                return channel
            elif mode == "connect":
                reader, writer = await asyncio.open_connection(host, port)
                cipher  = self.cipher_spec.build()
                channel = RemoteChannel(reader=reader, writer=writer,
                                        cipher=cipher)
                await channel.connect()
                return channel
            raise ValueError("EventChannelParameter: unknown remote mode %r" % mode)

        raise ValueError("EventChannelParameter: unknown kind %r" % k)
