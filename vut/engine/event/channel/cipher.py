"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Cipher - pluggable encryption strategy for EventChannels.

A Cipher transforms the serialised byte blob of a Channel on its way
out (encrypt) and on its way in (decrypt). It sits BETWEEN
serialisation and transport. The default IdentityCipher does nothing;
it is a pass-through.

A Cipher is meaningful only for channels that actually produce bytes
on a wire - ProcessChannel and RemoteChannel. In-process channels
(AsyncChannel, ThreadChannel) shuttle live Event objects and
never serialise; they always use IdentityCipher.


INTERFACE

    async handshake(raw_send, raw_recv)   -- run any key-exchange the
                                            cipher needs, using the two
                                            raw byte primitives supplied
                                            by the Channel
    encrypt(blob: bytes) -> bytes         -- transform on send
    decrypt(blob: bytes) -> bytes         -- transform on receive

handshake() receives two callables from the Channel:
    raw_send(b: bytes)   -> awaitable     -- send raw bytes to the peer
    raw_recv()           -> awaitable[bytes] -- receive raw bytes

These operate on the not-yet-secured transport. The Cipher uses them
to exchange whatever public material its scheme needs. handshake()
completes BEFORE the Channel is handed up to the Terminal, so by the
time any Event (including the Terminal's own Up/Down lifecycle events)
crosses the wire, the Cipher is fully established.

The handshake messages are raw bytes, NOT Events. They are exchanged
below the Event layer - there is a chicken-and-egg otherwise (you
cannot send an Event securely until the Cipher is up).


THE FOUR CIPHERS

    IdentityCipher    pass-through; no encryption, no handshake.
                      The default. Used by all in-process channels
                      and by Process/Remote channels when no security
                      is configured.

    FernetCipher      symmetric authenticated encryption
                      (cryptography.fernet). Either a pre-shared key
                      is supplied, or an ephemeral X25519 exchange
                      derives one during handshake().

    NaClBoxCipher     public-key authenticated encryption (PyNaCl /
                      libsodium Box). Each side has a long-term or
                      ephemeral keypair; handshake() exchanges public
                      keys.

    TLSCipher         TLS via an ssl.SSLContext in memory-BIO mode.
                      handshake() runs the TLS handshake over the raw
                      primitives; encrypt/decrypt route plaintext
                      through the established TLS record layer.


SECRECY vs IDENTITY  (read this before trusting a configuration)

An ephemeral key exchange with NO pre-shared anchor gives SECRECY but
not IDENTITY: the channel is encrypted to whoever you handshook with,
but a man-in-the-middle can handshake with each side separately and
read everything. To AUTHENTICATE the peer you need a pre-shared
anchor - a shared key, a certificate, or a token from configuration.

    -- FernetCipher with a pre-shared key:  authenticated (the key
       IS the shared anchor).
    -- FernetCipher with ephemeral-only exchange:  encrypted but
       UNAUTHENTICATED - safe only where no MITM is possible.
    -- NaClBoxCipher with pre-shared peer public keys:  authenticated.
    -- NaClBoxCipher with ephemeral keys and no pinned peer key:
       encrypted but UNAUTHENTICATED.
    -- TLSCipher with certificate verification:  authenticated.

For purely local transports (Process, Thread) identity does not
matter - there is no wire to sit on. For RemoteChannel it does.
________________________________________________________________________________
"""
import os
import sys

from abc import ABC, abstractmethod


# ============================================================================
# Abstract base
# ============================================================================

class Cipher(ABC):
    """Pluggable encryption strategy for an EventChannel.

    See module header for the contract and the secrecy-vs-identity
    discussion.
    """

    @abstractmethod
    async def handshake(self, raw_send, raw_recv) -> None:
        """RETURN: None,  once the cipher is fully established.

        Runs whatever key-exchange this cipher needs. raw_send and
        raw_recv are async callables provided by the Channel that
        move raw bytes over the not-yet-secured transport:

            await raw_send(b"...")        # bytes -> peer
            data = await raw_recv()       # bytes <- peer

        IdentityCipher's handshake is a no-op.
        """
        ...

    @abstractmethod
    def encrypt(self, blob: bytes) -> bytes:
        """RETURN: bytes, the encrypted form of blob.

        Called on the serialised payload before it hits the transport.
        """
        ...

    @abstractmethod
    def decrypt(self, blob: bytes) -> bytes:
        """RETURN: bytes,  the decrypted plaintext.

        Called on bytes arriving from the transport, before
        deserialisation. May raise if the blob fails authentication;
        the Channel treats a raised exception as a corrupt message.
        """
        ...


# ============================================================================
# IdentityCipher - the default pass-through
# ============================================================================

class IdentityCipher(Cipher):
    """No encryption. Pass-through. The default cipher.

    Used by all in-process channels and by Process/Remote channels
    when no security is configured.
    """

    async def handshake(self, raw_send, raw_recv) -> None:
        """RETURN: None.  No-op: identity needs no key exchange."""
        return None

    def encrypt(self, blob: bytes) -> bytes:
        """RETURN: bytes, blob unchanged."""
        return blob

    def decrypt(self, blob: bytes) -> bytes:
        """RETURN: bytes, blob unchanged."""
        return blob


# ============================================================================
# FernetCipher - symmetric authenticated encryption
# ============================================================================

class FernetCipher(Cipher):
    """Symmetric authenticated encryption via cryptography.fernet.

    Two modes:

      -- pre-shared key: construct with key=<32-byte urlsafe-base64
         Fernet key>. handshake() is then a no-op and the channel is
         AUTHENTICATED (the shared key is the anchor).

      -- ephemeral exchange: construct with key=None. handshake()
         performs an X25519 exchange, derives a Fernet key from the
         shared secret. The channel is ENCRYPTED but UNAUTHENTICATED
         unless an anchor is added (see module header).

    Requires the 'cryptography' package.
    """

    def __init__(self, key: "bytes | None" = None):
        """RETURN: a new FernetCipher.

        key -- a urlsafe-base64-encoded 32-byte Fernet key for the
               pre-shared mode, or None to derive one via ephemeral
               X25519 exchange in handshake().
        """
        self._preshared_key = key
        self._fernet        = None          # built in handshake() or here
        if key is not None:
            from cryptography.fernet import Fernet
            self._fernet = Fernet(key)

    async def handshake(self, raw_send, raw_recv) -> None:
        """RETURN: None.

        Pre-shared mode: no-op. Ephemeral mode: exchange X25519 public
        keys, derive a shared secret, turn it into a Fernet key.
        """
        if self._fernet is not None:
            return None                     # pre-shared; nothing to do

        # Ephemeral X25519 exchange.
        from cryptography.hazmat.primitives.asymmetric.x25519 import (
            X25519PrivateKey, X25519PublicKey,
        )
        from cryptography.hazmat.primitives                   import serialization, hashes
        from cryptography.hazmat.primitives.kdf.hkdf          import HKDF
        import base64

        my_priv = X25519PrivateKey.generate()
        my_pub  = my_priv.public_key().public_bytes(
            encoding = serialization.Encoding.Raw,
            format   = serialization.PublicFormat.Raw,
        )
        # Exchange: send ours, receive theirs. Symmetric - both sides
        # send first, then receive; the transport buffers.
        await raw_send(my_pub)
        peer_pub_bytes = await raw_recv()
        peer_pub       = X25519PublicKey.from_public_bytes(peer_pub_bytes)

        shared = my_priv.exchange(peer_pub)
        # HKDF the raw shared secret into a 32-byte Fernet key.
        derived = HKDF(
            algorithm = hashes.SHA256(),
            length    = 32,
            salt      = None,
            info      = b"vut-event-fernet",
        ).derive(shared)

        from cryptography.fernet import Fernet
        self._fernet = Fernet(base64.urlsafe_b64encode(derived))
        return None

    def encrypt(self, blob: bytes) -> bytes:
        """RETURN: bytes, the Fernet token for blob."""
        return self._fernet.encrypt(blob)

    def decrypt(self, blob: bytes) -> bytes:
        """RETURN: bytes, the plaintext.

        Raises cryptography.fernet.InvalidToken if the blob fails
        authentication or was tampered with.
        """
        return self._fernet.decrypt(blob)

    @staticmethod
    def generate_key() -> bytes:
        """RETURN: bytes, a fresh urlsafe-base64 Fernet key.

        Helper for setting up the pre-shared mode.
        """
        from cryptography.fernet import Fernet
        return Fernet.generate_key()


# ============================================================================
# NaClBoxCipher - public-key authenticated encryption
# ============================================================================

class NaClBoxCipher(Cipher):
    """Public-key authenticated encryption via PyNaCl (libsodium Box).

    Each side has a Curve25519 keypair. handshake() exchanges public
    keys. A Box is then formed from (my_private, peer_public); it
    provides authenticated encryption in both directions.

    Two modes for the peer's identity:

      -- pinned peer key: construct with expected_peer_public=<bytes>.
         After the handshake, the received peer key is checked against
         the pinned value; a mismatch raises. This AUTHENTICATES the
         peer.

      -- unpinned: construct with expected_peer_public=None. The
         channel is ENCRYPTED but UNAUTHENTICATED (see module header).

    The local keypair may be supplied (long-term identity) or left
    None to generate an ephemeral one.

    Requires the 'pynacl' package.
    """

    def __init__(self,
                 private_key:          "bytes | None" = None,
                 expected_peer_public: "bytes | None" = None):
        """RETURN: a new NaClBoxCipher.

        private_key          -- 32 raw bytes of a Curve25519 private
                               key for a long-term identity, or None
                               to generate an ephemeral keypair.
        expected_peer_public -- 32 raw bytes of the peer's expected
                               public key (pinned mode), or None to
                               accept whatever the peer presents.
        """
        from nacl.public import PrivateKey

        if private_key is not None:
            self._private = PrivateKey(private_key)
        else:
            self._private = PrivateKey.generate()

        self._expected_peer_public = expected_peer_public
        self._box                  = None          # built in handshake()

    async def handshake(self, raw_send, raw_recv) -> None:
        """RETURN: None.

        Exchanges public keys and forms the Box. If a pinned peer key
        was supplied, verifies the received key against it and raises
        ValueError on mismatch.
        """
        from nacl.public import PublicKey, Box

        my_pub = bytes(self._private.public_key)
        await raw_send(my_pub)
        peer_pub_bytes = await raw_recv()

        if self._expected_peer_public is not None:
            if peer_pub_bytes != self._expected_peer_public:
                raise ValueError(
                    "NaClBoxCipher.handshake: peer public key does not "
                    "match the pinned expected key - possible "
                    "man-in-the-middle, refusing the connection."
                )

        peer_pub  = PublicKey(peer_pub_bytes)
        self._box = Box(self._private, peer_pub)
        return None

    def encrypt(self, blob: bytes) -> bytes:
        """RETURN: bytes, the Box-encrypted blob (nonce prepended).

        PyNaCl's Box.encrypt prepends a fresh random nonce.
        """
        return bytes(self._box.encrypt(blob))

    def decrypt(self, blob: bytes) -> bytes:
        """RETURN: bytes, the plaintext.

        Raises nacl.exceptions.CryptoError if the blob fails
        authentication.
        """
        return self._box.decrypt(blob)

    @staticmethod
    def generate_keypair() -> "tuple[bytes, bytes]":
        """RETURN: (private_bytes, public_bytes), a fresh Curve25519 keypair.

        Helper for setting up long-term identities. The private half
        is the secret; the public half is what a peer pins.
        """
        from nacl.public import PrivateKey
        priv = PrivateKey.generate()
        return bytes(priv), bytes(priv.public_key)


# ============================================================================
# TLSCipher - TLS via an ssl.SSLContext in memory-BIO mode
# ============================================================================

class TLSCipher(Cipher):
    """TLS over the raw transport, via ssl.SSLObject (memory-BIO mode).

    handshake() drives the TLS handshake using the Channel's raw
    byte primitives. After that, encrypt() feeds plaintext into the
    TLS layer and returns the resulting TLS records; decrypt() feeds
    TLS records in and returns plaintext.

    Constructed with an ssl.SSLContext and a role flag:

      -- server_side=True   : behaves as the TLS server
      -- server_side=False  : behaves as the TLS client

    The SSLContext carries certificate / verification configuration.
    A context with proper certificate verification AUTHENTICATES the
    peer; a context with verification disabled gives encryption only.

    Uses the standard library 'ssl' module - no extra dependency.

    NOTE: this implementation drives the memory BIO. Each encrypt()
    may produce zero or more TLS records; the framing of records on
    the wire is the Channel's responsibility (it already length-
    prefixes payloads). Because TLS records do not map one-to-one to
    application messages, a production TLSCipher would buffer; this
    implementation is structured for the common case where each
    application message fits comfortably in the record machinery.
    """

    def __init__(self, ssl_context, server_side: bool = False):
        """RETURN: a new TLSCipher.

        ssl_context -- a configured ssl.SSLContext.
        server_side -- True for the TLS server end, False for client.
        """
        self._ctx         = ssl_context
        self._server_side = server_side
        self._incoming    = None        # ssl.MemoryBIO
        self._outgoing    = None        # ssl.MemoryBIO
        self._sslobj      = None        # ssl.SSLObject

    async def handshake(self, raw_send, raw_recv) -> None:
        """RETURN: None,  once the TLS handshake has completed.

        Drives ssl.SSLObject.do_handshake() against the memory BIOs,
        shuttling handshake records over raw_send / raw_recv.
        """
        import ssl

        self._incoming = ssl.MemoryBIO()
        self._outgoing = ssl.MemoryBIO()
        self._sslobj   = self._ctx.wrap_bio(
            self._incoming, self._outgoing,
            server_side = self._server_side,
        )

        # do_handshake() raises SSLWantReadError when it needs more
        # bytes from the peer. Loop: flush our outgoing, read peer's
        # incoming, retry.
        while True:
            try:
                self._sslobj.do_handshake()
                break
            except ssl.SSLWantReadError:
                # Flush anything we produced, then await peer bytes.
                out = self._outgoing.read()
                if out:
                    await raw_send(out)
                data = await raw_recv()
                self._incoming.write(data)
        # Flush any final handshake bytes.
        out = self._outgoing.read()
        if out:
            await raw_send(out)
        return None

    def encrypt(self, blob: bytes) -> bytes:
        """RETURN: bytes, the TLS records produced for blob.

        Writes plaintext into the TLS layer and returns whatever TLS
        records the layer emits on the outgoing BIO.
        """
        self._sslobj.write(blob)
        return self._outgoing.read()

    def decrypt(self, blob: bytes) -> bytes:
        """RETURN: bytes, the plaintext recovered from the TLS records.

        Feeds TLS records into the incoming BIO and reads decrypted
        application data back out.
        """
        import ssl
        self._incoming.write(blob)
        chunks = []
        while True:
            try:
                chunk = self._sslobj.read()
            except ssl.SSLWantReadError:
                break
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
