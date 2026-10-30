#! /usr/bin/env python3
# @hwut {
#     title    = "Debian OpenSSL (2006-2008): one line removed, and every key is one of 32768"
#     choices {
#         debian-2006 { features = ["machines-drawn", "shared-keys-shown", "space-enumerated", "collisions-named"]
#                       tolerance { constraints = ["collisions > 0", "in_table > 0"] } }
#         upstream    { features = ["machines-drawn", "shared-keys-shown", "space-enumerated", "keys-distinct"]
#                       tolerance { constraints = ["collisions == 0", "in_table == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the keys 2000 machines make, how many of them are shared, and how
         many an attacker finds by computing every key the generator can
         make from the process id alone
HISTORY  In September 2006 a Debian maintainer commented out a line of
OpenSSL's random-pool code that Valgrind reported as reading uninitialised
memory. That line was also the one that stirred gathered entropy into the
pool. From then on the only varying input left was the process id, at most
32768 values on Linux, so every key Debian and Ubuntu machines generated
-- SSH host keys, user keys, certificates -- was one of a small set an
attacker could compute in advance. The flaw was found and announced in May
2008 (DSA-1571); every key made in between had to be replaced.

REQUIREMENT  Keys of different machines never coincide, and the set of
             keys the generator can make cannot be enumerated.

THE UNIT  '../keygen.py': key_of(pid, entropy, release) -- SHA-256 of the
random pool, 16 hex digits, a stand-in for the key the pool seeds.
'debian-2006' leaves the entropy out of the pool, 'upstream' stirs it in.

THE MACHINES  DeterministicStream(2008): 2000 machines, each with a process
id in 1 .. 32768 and 64 bits of entropy. The same machines on every run
and every computer.

WHAT THE TEST PRINTS
  1. THE FIRST MACHINES: pid, entropy, key.
  2. SHARED KEYS: how many machines hold a key another machine holds too,
     and the five keys held most often.
  3. THE ATTACKER'S TABLE: the key for every pid 1 .. 32768, computed
     without any entropy -- and how many of the 2000 machines' keys stand
     in it.

CHOICES
    debian-2006   about 2000^2 / (2 x 32768) pairs share a key by the
                  birthday bound; the table holds every machine's key.
    upstream      2000 distinct keys; the table holds none.

HOW TO READ THE GOOD  Everything is exact: the stream and the hash are the
same everywhere. Bindings: '((collisions: N))' machines whose key another
machine also holds, '((in_table: N))' machines whose key the attacker's
table holds; laws '> 0' for debian-2006, '== 0' for upstream.
______________________________________________________________________________
"""
import collections
import os
import shutil
import sys

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
from hwut.test_writing_support.python.deterministic_random import DeterministicStream

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from keygen import key_of                                       # noqa: E402

SEED, MACHINE_N, PID_MAX = 2008, 2000, 32768
RELEASE_TUPLE = ("debian-2006", "upstream")


def machine_list():
    """
    RETURN: list of (pid, entropy), one per machine, drawn from
            DeterministicStream(SEED): pid in 1 .. PID_MAX, entropy 64 bits.
    """
    stream = DeterministicStream(SEED)
    result = []
    for _ in range(MACHINE_N):
        pid = stream.next_int(1, PID_MAX)
        entropy = (stream.next_int(0, 2 ** 32 - 1) << 32) | stream.next_int(0, 2 ** 32 - 1)
        result.append((pid, entropy))
    return result


def main(release):
    """RETURN: int, 0 once the keys, the sharing and the table are printed."""
    machines = machine_list()
    key_list = [key_of(pid, entropy, release) for pid, entropy in machines]
    count_db = collections.Counter(key_list)
    collisions = sum(n for n in count_db.values() if n > 1)
    table = set(key_of(pid, 0, "debian-2006") for pid in range(1, PID_MAX + 1))
    in_table = sum(1 for key in key_list if key in table)

    print("release %s, %d machines from DeterministicStream(%d)" % (release, MACHINE_N, SEED))
    print()
    print("1. THE FIRST MACHINES")
    print("##! verbatim")
    print("   machine    pid  entropy             key")
    for k, ((pid, entropy), key) in enumerate(zip(machines[:6], key_list[:6])):
        print("   %7d  %5d  %016x    %s" % (k + 1, pid, entropy, key))
    print("####")
    print()
    print("2. SHARED KEYS")
    print("##! verbatim")
    print("   distinct keys among %d machines: %d" % (MACHINE_N, len(count_db)))
    shared = [(n, key) for key, n in count_db.items() if n > 1]
    shared.sort(key=lambda pair: (-pair[0], pair[1]))
    if shared:
        print("   held most often:")
        for n, key in shared[:5]:
            print("       %s  by %d machines" % (key, n))
    else:
        print("   no key is held by two machines")
    print("####")
    print("   machines sharing a key ((collisions: %d))   %s"
          % (collisions, "law > 0   the flaw, reproduced" if release == "debian-2006"
             else "law == 0   %s" % ("kept" if collisions == 0 else "BROKEN")))
    print()
    print("3. THE ATTACKER'S TABLE: the key of every pid 1 .. %d, no entropy" % PID_MAX)
    print("##! verbatim")
    print("   keys in the table: %d -- the whole space, computed in seconds" % len(table))
    print("####")
    print("   machines whose key is in it ((in_table: %d)) of %d   %s"
          % (in_table, MACHINE_N, "law > 0   the flaw, reproduced" if release == "debian-2006"
             else "law == 0   %s" % ("kept" if in_table == 0 else "BROKEN")))
    return 0


if __name__ == "__main__":
    release = sys.argv[1] if len(sys.argv) > 1 else ""
    if release not in RELEASE_TUPLE:
        print("choices: %s" % ", ".join(RELEASE_TUPLE))
        sys.exit(1)
    status = main(release)
    print("<hwut-end>")
    sys.exit(status)
