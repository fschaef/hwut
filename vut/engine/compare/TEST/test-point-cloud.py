#! /usr/bin/env python3
#
# @hwut {
#     title      = "Point-Cloud Region: coverage, pair, dist, constraint, errors"
#     choices    = ["constraint", "coverage", "dist", "errors",
#                   "generative", "pair", "spatial"]
# }
#
"""'point-cloud' region: every line is an n-dimensional point.

Pins DOC/SEMANTICS.txt section 7.5 (POINT-CLOUD): symmetric-coverage
default, bijective 'pair' mode, distance functions (built-in and
expression), the 'constraint' property check, the nominal-is-authoritative
rule, the malformed-data asymmetry, and the loud errors (including the
expression whitelist). The 'generative' choice is a deterministic
metamorphic family (DeterministicStream).
"""
import sys
import os
import io
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[0]), "../../../../"))

from vut.engine.compare.configuration   import Configuration      # noqa: E402
import vut.engine.compare.main          as     main               # noqa: E402
from vut.engine.compare.region.registry import RegionSyntaxError  # noqa: E402
from vut.language_support.python.deterministic_random import DeterministicStream  # noqa: E402

if "--hwut-info" in sys.argv:
    print("Point-Cloud Region: coverage, pair, dist, constraint, errors;")
    print("CHOICES: coverage, pair, dist, constraint, errors, generative, spatial;")
    sys.exit()

CONFIG = Configuration()


async def verdict_pair(subject_txt, nominal_txt):
    """RETURNS: (bool, bool), Judge and Lawyer verdict -- THE LAW requires
                agreement.
    """
    judge = await main.is_equivalent(CONFIG, io.StringIO(subject_txt),
                                             io.StringIO(nominal_txt))
    lawyer = await main.is_equivalent_by_association(
                                     CONFIG, io.StringIO(subject_txt),
                                             io.StringIO(nominal_txt))
    return judge, lawyer


def show(title, subject_txt, nominal_txt):
    judge, lawyer = asyncio.run(verdict_pair(subject_txt, nominal_txt))
    agree = "ok" if judge == lawyer else "LAW-BROKEN"
    print("%-42s judge: %-5s lawyer: %-5s [%s]"
          % (title + ":", judge, lawyer, agree))


def region(params, body):
    return "##! point-cloud %s\n%s####\n" % (params, body)


if "coverage" in sys.argv:
    print("## Default: every point has a nearest neighbour <= limit, both ways.")
    show("identical, permuted",
         region("limit=0.05", "0.1 0.2\n0.3 0.4\n"),
         region("limit=0.05", "0.3 0.4\n0.1 0.2\n"))
    show("jitter within limit",
         region("limit=0.05", "0.11 0.21\n0.31 0.39\n"),
         region("limit=0.05", "0.1 0.2\n0.3 0.4\n"))
    show("jitter beyond limit",
         region("limit=0.05", "0.2 0.3\n"),
         region("limit=0.05", "0.1 0.2\n"))
    show("duplicate subject point (counts free)",
         region("limit=0.05", "0.1 0.2\n0.1 0.2\n"),
         region("limit=0.05", "0.1 0.2\n"))
    show("uncovered nominal point",
         region("limit=0.05", "0.1 0.2\n"),
         region("limit=0.05", "0.1 0.2\n5 5\n"))
    show("both regions empty",
         region("limit=0.05", ""), region("limit=0.05", ""))
    print("## Malformed data is asymmetric (nominal is authoritative):")
    show("subject line is not a point",
         region("limit=0.05", "0.1 banana\n"),
         region("limit=0.05", "0.1 0.2\n"))
    show("subject dimension clash",
         region("limit=0.05", "0.1 0.2 0.3\n"),
         region("limit=0.05", "0.1 0.2\n"))

if "pair" in sys.argv:
    print("## 'pair': bijective matching, every pair <= limit, equal counts.")
    show("clean bijection, permuted",
         region("limit=0.05 pair", "0.1 0.2\n0.3 0.4\n"),
         region("limit=0.05 pair", "0.31 0.41\n0.1 0.2\n"))
    show("duplicate cannot pair twice",
         region("limit=0.05 pair", "0.1 0.2\n0.1 0.2\n"),
         region("limit=0.05 pair", "0.1 0.2\n"))
    show("contended points resolved",
         region("limit=0.05 pair", "0.1 0.2\n0.1 0.2\n"),
         region("limit=0.05 pair", "0.1 0.2\n0.11 0.21\n"))
    show("count mismatch",
         region("limit=0.05 pair", "0.1 0.2\n"),
         region("limit=0.05 pair", "0.1 0.2\n0.3 0.4\n"))

if "dist" in sys.argv:
    print("## Distance functions: built-ins and whitelisted expressions.")
    show("Linf tolerates the diagonal",
         region("limit=0.1 dist=Linf", "0.1 0.1\n"),
         region("limit=0.1 dist=Linf", "0.19 0.19\n"))
    show("L2 rejects the same diagonal",
         region("limit=0.1 dist=L2", "0.1 0.1\n"),
         region("limit=0.1 dist=L2", "0.19 0.19\n"))
    show("L1 sums components",
         region("limit=0.1 dist=L1", "0.1 0.1\n"),
         region("limit=0.1 dist=L1", "0.14 0.14\n"))
    show("expression: first component only",
         region("limit=0.5 dist={abs(x[0]-y[0])}", "0.1 99\n"),
         region("limit=0.5 dist={abs(x[0]-y[0])}", "0.2 -5\n"))
    print("## Nominal is authoritative: the subject's limit is ignored.")
    show("subject declares limit=0.0001",
         region("limit=0.0001", "0.11 0.21\n"),
         region("limit=0.05",   "0.1 0.2\n"))

if "constraint" in sys.argv:
    print("## constraint={...}: a property every point must satisfy;")
    print("## aliases x, y, z, w = p[0..3]. Counts are irrelevant.")
    C = "constraint={abs(y - sin(x)/x) < 0.01}"
    show("points on the curve y=sin(x)/x",
         region(C, "0.5 0.9589\n1.0 0.8415\n2.0 0.4546\n"),
         region(C, "1.0 0.8415\n"))
    show("a point off the curve",
         region(C, "1.0 0.5\n"),
         region(C, "1.0 0.8415\n"))
    show("combined with limit",
         region("limit=0.05 " + C, "1.0 0.8415\n"),
         region("limit=0.05 " + C, "1.01 0.8414\n"))

if "errors" in sys.argv:
    print("## Broken specifications fail LOUDLY.")
    bad = [
        ("no criterion",
         region("", "0.1\n"),                       region("", "0.1\n")),
        ("nominal line is not a point",
         region("limit=0.1", "0.1\n"),              region("limit=0.1", "banana\n")),
        ("nominal violates own constraint",
         region("constraint={x < 1}", "0.5\n"),     region("constraint={x < 1}", "2.0\n")),
        ("forbidden name in expression",
         region("constraint={__import__}", "1\n"),  region("constraint={__import__}", "1\n")),
        ("forbidden construct in expression",
         region("constraint={[i for i in p]}", "1\n"),
         region("constraint={[i for i in p]}", "1\n")),
        ("unbalanced braces",
         region("constraint={x < 1", "1\n"),        region("constraint={x < 1", "1\n")),
        ("unknown parameter",
         region("radius=1", "0.1\n"),               region("radius=1", "0.1\n")),
    ]
    for name, subject_txt, nominal_txt in bad:
        try:
            asyncio.run(verdict_pair(subject_txt, nominal_txt))
            print("%-36s -> NO ERROR (unexpected!)" % name)
        except RegionSyntaxError as e:
            print("%-36s -> %s" % (name, e))

if "generative" in sys.argv:
    print("## Metamorphic families over generated clouds (seed-stable).")
    rng    = DeterministicStream(seed=0xC10D)
    LIMIT  = 0.05
    checks = {"permute": [0, 0], "jitter_in": [0, 0], "jitter_out": [0, 0]}

    def gen_cloud(n, dim):
        return [tuple(rng.next_int(0, 1000) / 100.0 for _ in range(dim))
                for _ in range(n)]

    def render(cloud):
        body = "".join(" ".join("%.4f" % c for c in p) + "\n" for p in cloud)
        return region("limit=%s" % LIMIT, body)

    for case in range(60):
        dim   = rng.next_int(1, 3)
        cloud = gen_cloud(rng.next_int(1, 6), dim)

        rotated = cloud[1:] + cloud[:1]
        v = asyncio.run(verdict_pair(render(rotated), render(cloud)))
        checks["permute"][1] += 1
        checks["permute"][0] += (v == (True, True))

        jit = [tuple(c + (rng.next_int(-100, 100) / 100.0)
                     * (LIMIT * 0.4 / max(1, dim)) for c in p)
               for p in cloud]
        v = asyncio.run(verdict_pair(render(jit), render(cloud)))
        checks["jitter_in"][1] += 1
        checks["jitter_in"][0] += (v == (True, True))

        i   = rng.next_int(0, len(cloud) - 1)
        far = [tuple(c + 10 * LIMIT for c in p) if j == i else p
               for j, p in enumerate(cloud)]
        v = asyncio.run(verdict_pair(render(far), render(cloud)))
        checks["jitter_out"][1] += 1
        checks["jitter_out"][0] += (v == (False, False))

    for name in ("permute", "jitter_in", "jitter_out"):
        ok, total = checks[name]
        print("  %-10s expected-verdict (judge==lawyer): %d/%d" % (name, ok, total))
    print("result: %s" % ("PASS" if all(o == t for o, t in checks.values())
                          else "FAIL"))

if "spatial" in sys.argv:
    print("## Grid index (built-in metrics) vs brute force (expression")
    print("## metrics) must produce IDENTICAL verdicts -- same clouds are")
    print("## compared under 'euclidean'/'Linf' (grid path) and their")
    print("## expression twins (brute path).")
    rng   = DeterministicStream(seed=0x9C1D)
    LIMIT = 0.35
    TWIN_DB = {
        "euclidean": "{sqrt((x[0]-y[0])**2 + (x[1]-y[1])**2)}",
        "Linf":      "{max(abs(x[0]-y[0]), abs(x[1]-y[1]))}",
    }

    def render(cloud, dist_spec, pair_s):
        body = "".join("%.4f %.4f\n" % p for p in cloud)
        return "##! point-cloud limit=%s dist=%s%s\n%s####\n" \
               % (LIMIT, dist_spec, pair_s, body)

    agree_db = {name: [0, 0] for name in TWIN_DB}
    for case in range(50):
        n_s = rng.next_int(1, 12)
        n_n = rng.next_int(1, 12)
        s_cloud = [(rng.next_int(0, 300) / 100.0, rng.next_int(0, 300) / 100.0)
                   for _ in range(n_s)]
        n_cloud = [(rng.next_int(0, 300) / 100.0, rng.next_int(0, 300) / 100.0)
                   for _ in range(n_n)]
        pair_s  = " pair" if rng.next_int(0, 1) else ""
        for name, twin in TWIN_DB.items():
            grid  = asyncio.run(verdict_pair(render(s_cloud, name, pair_s),
                                             render(n_cloud, name, pair_s)))
            brute = asyncio.run(verdict_pair(render(s_cloud, twin, pair_s),
                                             render(n_cloud, twin, pair_s)))
            agree_db[name][1] += 1
            agree_db[name][0] += (grid == brute and grid[0] == grid[1])

    for name, (ok, total) in agree_db.items():
        print("  %-10s grid == brute (and judge == lawyer): %d/%d"
              % (name, ok, total))
    print("result: %s" % ("PASS" if all(o == t for o, t in agree_db.values())
                          else "FAIL"))
