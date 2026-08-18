#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the Cipher strategy used by serialising EventChannels.

CHOICES: identity, fernet_preshared, fernet_ephemeral, nacl, nacl_pinned,
         channel_integration;

DESCRIPTION:

A Cipher transforms a Channel's serialised byte payload on send
(encrypt) and receive (decrypt), with an optional handshake() for
key exchange. The default IdentityCipher is a pass-through. Cipher
is a channel-internal concept - it is NOT exported from the event
package's __init__; users do not configure it directly, they pass
a CipherSpec to a channel-parameter factory.

    identity            IdentityCipher: encrypt/decrypt are no-ops;
                        handshake() does nothing.

    fernet_preshared    FernetCipher with a pre-shared key: a blob
                        encrypted by one side decrypts on the other;
                        the ciphertext is not the plaintext.

    fernet_ephemeral    FernetCipher with key=None: an X25519
                        handshake derives a shared key; round-trips
                        work in both directions afterwards.

    nacl                NaClBoxCipher with ephemeral keypairs: public
                        keys are exchanged in the handshake; the Box
                        round-trips.

    nacl_pinned         NaClBoxCipher with a pinned peer key: a
                        matching pin handshakes cleanly; a mismatched
                        pin raises ValueError (man-in-the-middle
                        defence).

    channel_integration a ProcessChannel built through
                        make_channel() with a CipherSpec: events sent
                        on one end arrive intact on the other, both
                        for the identity fast-path and a real Fernet
                        cipher.

NOTE: TLSCipher is not exercised here - it needs a certificate/key
pair on disk, the same reason RemoteChannel is not in the suite.
When a real remote+TLS deployment exists, add an integration test.
______________________________________________________________________________
"""
import asyncio
import os
import sys
import config                                                       # noqa: F401

from vut.language_support.python.hwut_runner    import HwutRunner
from vut.engine.event                           import Event, category
from vut.engine.event.channel.parameter         import (EventChannelParameter,
                                                        CipherSpec)
from vut.engine.event.channel.cipher            import (IdentityCipher,
                                                        FernetCipher,
                                                        NaClBoxCipher)


# Test-local event vocabulary.
with category("TEST_LOCAL_CIPHER"):

    class EventSecret(Event):
        payload: str


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


async def _connected_pair(cipher_a, cipher_b):
    """RETURN: None. Runs the two ciphers' handshakes against each other.

    Wires cipher_a and cipher_b together with two asyncio.Queues so
    each can run handshake() against the other, as if across a real
    channel. Both handshakes run concurrently (each may send before
    receiving).
    """
    q_ab: asyncio.Queue = asyncio.Queue()
    q_ba: asyncio.Queue = asyncio.Queue()

    async def a_send(b): await q_ab.put(b)
    async def a_recv():  return await q_ba.get()
    async def b_send(b): await q_ba.put(b)
    async def b_recv():  return await q_ab.get()

    await asyncio.gather(cipher_a.handshake(a_send, a_recv),
                         cipher_b.handshake(b_send, b_recv))


def run_identity():
    """RETURN: None. IdentityCipher is a pass-through."""
    c = IdentityCipher()

    banner("encrypt is identity")
    blob = c.encrypt(b"hello world")
    print("encrypt(b'hello world') == b'hello world': %s"
          % (blob == b"hello world"))

    banner("decrypt is identity")
    print("decrypt(b'hello world') == b'hello world': %s"
          % (c.decrypt(b"hello world") == b"hello world"))

    banner("handshake is a no-op")
    asyncio.run(_connected_pair(IdentityCipher(), IdentityCipher()))
    print("two IdentityCiphers handshook without error")


def run_fernet_preshared():
    """RETURN: None. FernetCipher with a shared key round-trips."""
    key = FernetCipher.generate_key()
    enc = FernetCipher(key=key)
    dec = FernetCipher(key=key)

    banner("ciphertext differs from plaintext")
    blob = enc.encrypt(b"the secret")
    print("ciphertext != plaintext: %s" % (blob != b"the secret"))

    banner("the other side decrypts it")
    print("decrypt(encrypt(x)) == x: %s" % (dec.decrypt(blob) == b"the secret"))

    banner("a wrong key fails to decrypt")
    other = FernetCipher(key=FernetCipher.generate_key())
    try:
        other.decrypt(blob)
        print("UNEXPECTED: wrong key decrypted")
    except Exception as e:
        print("wrong key raised %s (expected)" % type(e).__name__)


def run_fernet_ephemeral():
    """RETURN: None. FernetCipher ephemeral X25519 handshake."""
    a = FernetCipher(key=None)
    b = FernetCipher(key=None)

    banner("run the ephemeral handshake")
    asyncio.run(_connected_pair(a, b))
    print("handshake completed")

    banner("round-trip A -> B")
    blob = a.encrypt(b"from a")
    print("B decrypts A's message: %s" % (b.decrypt(blob) == b"from a"))

    banner("round-trip B -> A")
    blob2 = b.encrypt(b"from b")
    print("A decrypts B's message: %s" % (a.decrypt(blob2) == b"from b"))


def run_nacl():
    """RETURN: None. NaClBoxCipher with ephemeral keypairs."""
    a = NaClBoxCipher()
    b = NaClBoxCipher()

    banner("run the public-key handshake")
    asyncio.run(_connected_pair(a, b))
    print("handshake completed")

    banner("round-trip A -> B")
    blob = a.encrypt(b"nacl message")
    print("B decrypts A's message: %s" % (b.decrypt(blob) == b"nacl message"))

    banner("round-trip B -> A")
    blob2 = b.encrypt(b"nacl reply")
    print("A decrypts B's message: %s" % (a.decrypt(blob2) == b"nacl reply"))


def run_nacl_pinned():
    """RETURN: None. NaClBoxCipher pinned-peer-key behaviour."""
    priv_a, pub_a = NaClBoxCipher.generate_keypair()
    priv_b, pub_b = NaClBoxCipher.generate_keypair()

    banner("matching pins handshake cleanly")
    a = NaClBoxCipher(private_key=priv_a, expected_peer_public=pub_b)
    b = NaClBoxCipher(private_key=priv_b, expected_peer_public=pub_a)
    asyncio.run(_connected_pair(a, b))
    print("both sides accepted the peer key")
    blob = a.encrypt(b"pinned ok")
    print("round-trip works: %s" % (b.decrypt(blob) == b"pinned ok"))

    banner("a mismatched pin raises ValueError")
    _, wrong_pub = NaClBoxCipher.generate_keypair()
    a2 = NaClBoxCipher(private_key=priv_a, expected_peer_public=wrong_pub)
    b2 = NaClBoxCipher(private_key=priv_b, expected_peer_public=pub_a)

    results = asyncio.run(_pinned_mismatch(a2, b2))
    raised = [r for r in results if isinstance(r, ValueError)]
    print("ValueError raised by the pinning side: %s" % (len(raised) == 1))


async def _pinned_mismatch(a, b):
    """RETURN: list, the gather results of both handshakes.

    Wires a and b with shared queues and runs both handshakes with
    return_exceptions so the ValueError from the pinning side is
    captured rather than propagated.
    """
    q_ab: asyncio.Queue = asyncio.Queue()
    q_ba: asyncio.Queue = asyncio.Queue()

    async def a_send(x): await q_ab.put(x)
    async def a_recv():  return await q_ba.get()
    async def b_send(x): await q_ba.put(x)
    async def b_recv():  return await q_ab.get()

    return await asyncio.gather(
        a.handshake(a_send, a_recv),
        b.handshake(b_send, b_recv),
        return_exceptions=True,
    )


def run_channel_integration():
    """RETURN: None. ProcessChannel through make_channel with a CipherSpec."""
    asyncio.run(_channel_integration())


async def _channel_integration():
    """RETURN: None. Identity fast-path and Fernet path, end to end."""
    banner("process channel, identity cipher (default)")
    a_ecp, b_ecp = EventChannelParameter.for_process()
    a_ch, b_ch = await asyncio.gather(a_ecp.make_channel(),
                                      b_ecp.make_channel())
    await a_ch.send(EventSecret(payload="plain"))
    got = await b_ch.receive()
    print("identity round-trip payload: %r" % got.payload)
    await a_ch.close()
    await b_ch.close()

    banner("process channel, Fernet cipher via CipherSpec.fernet_env")
    os.environ["TEST_CIPHER_FERNET_KEY"] = \
        FernetCipher.generate_key().decode("ascii")
    spec = CipherSpec.fernet_env("TEST_CIPHER_FERNET_KEY")
    a_ecp, b_ecp = EventChannelParameter.for_process(cipher_spec=spec)
    a_ch, b_ch = await asyncio.gather(a_ecp.make_channel(),
                                      b_ecp.make_channel())
    await a_ch.send(EventSecret(payload="encrypted"))
    got = await b_ch.receive()
    print("fernet round-trip payload:   %r" % got.payload)
    await a_ch.close()
    await b_ch.close()

    banner("in-process channels ignore cipher_spec (always identity)")
    a_ecp, b_ecp = EventChannelParameter.for_async()
    print("for_async cipher_spec kind: %s" % a_ecp.cipher_spec.kind.name)


HwutRunner(
    argv       = sys.argv,
    title      = "Cipher (channel encryption strategy)",
    choice_map = {
        "identity":            run_identity,
        "fernet_preshared":    run_fernet_preshared,
        "fernet_ephemeral":    run_fernet_ephemeral,
        "nacl":                run_nacl,
        "nacl_pinned":         run_nacl_pinned,
        "channel_integration": run_channel_integration,
    },
).run()
