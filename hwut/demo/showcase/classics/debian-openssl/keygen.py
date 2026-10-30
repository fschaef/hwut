"""
______________________________________________________________________________
keygen.py -- a key generator as Debian's OpenSSL made keys from September
2006 to May 2008, and as upstream OpenSSL did: the key is a function of what
was stirred into the random pool.

    key_of(pid, entropy, release)

'release' is 'debian-2006' -- the line that stirs the entropy in is gone
(it was commented out to quiet Valgrind), the process id is the only seed
left -- or 'upstream'. The key is SHA-256 of the pool, shown as 16 hex
digits: a stand-in for an RSA or DSA key derived from the pool.
______________________________________________________________________________
"""
import hashlib


def pool_of(pid, entropy, release):
    """
    RETURN: bytes, what the random pool holds when the key is made: the
            process id, and the gathered entropy unless 'release' is
            'debian-2006'.
    """
    pool = b"pid:%d;" % pid
    if release != "debian-2006":
        pool += b"entropy:%d;" % entropy        # the line Debian removed
    return pool


def key_of(pid, entropy, release):
    """RETURN: str, the key made from the pool, 16 hex digits."""
    return hashlib.sha256(pool_of(pid, entropy, release)).hexdigest()[:16]
