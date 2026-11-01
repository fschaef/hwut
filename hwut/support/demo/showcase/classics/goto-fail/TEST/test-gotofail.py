#! /usr/bin/env python3
# @hwut {
#     title    = "goto fail (CVE-2014-1266): unreachable statements in the C source, and the forged key exchange it lets through"
#     choices {
#         apple-2014 { features = ["source-checked", "flow-drawn", "unreachable-named", "forgery-shown"]
#                      tolerance { constraints = ["unreachable > 0", "forged_accepted > 0"] } }
#         fixed      { features = ["source-checked", "flow-drawn", "all-reachable", "forgery-refused"]
#                      tolerance { constraints = ["unreachable == 0", "forged_accepted == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  SSLVerifySignedServerKeyExchange() of one sslKeyExchange.c: its control
         flow as the compiler reads it, and its verdict on three key exchanges
HISTORY  In February 2014 Apple shipped iOS 7.0.6 and then OS X 10.9.2 to
fix CVE-2014-1266: in SSLVerifySignedServerKeyExchange() of Secure
Transport (sslKeyExchange.c) one line 'goto fail;' stood twice. The second
copy is not governed by the 'if' above it, so it always jumps -- with
'err' still 0 -- past the final hash and past sslRawVerify(), the check of
the server's signature. Any man in the middle could present a key exchange
signed with his own key, and TLS clients accepted it. The source was
published by Apple (libsecurity_ssl); Adam Langley's analysis ("Apple's
SSL/TLS bug", ImperialViolet, 22 Feb 2014) made the snippet famous.

REQUIREMENT  (artifact) No statement of the C source is unreachable: after
             an unconditional 'goto' or 'return' only a label may follow at
             the same level. (behaviour) A ServerKeyExchange whose signature
             does not verify is refused.

THE ARTIFACT CHECK  The test reads '../<choice>/sslKeyExchange.c' as TEXT.
It splits the function body into statements, notes which ones an 'if'
without braces governs, and walks them: after an UNGUARDED goto the
statements of that block are unreachable until the next label. It also
names two identical goto lines in a row. As a second opinion it asks gcc
-Wmisleading-indentation (GCC 6, 2016 -- a warning that exists because of
this kind of bug) and prints only the lines it names.
THE RUN  The same file is compiled with '../handshake.c' (toy hash, toy
signature = digest XOR key; '../crypto_model.h') and three key exchanges
are verified: the genuine server, a man in the middle signing with his own
key, and one altering the signed DH parameters.

CHOICES
    apple-2014  the file as published: one doubled 'goto fail;'. Six
                statements are unreachable -- the final hash, sslRawVerify()
                and its error branch; both forgeries are accepted.
    fixed       the line removed (as in iOS 7.0.6): every statement
                reachable; both forgeries refused with errSSLCrypto -9809.

HOW TO READ THE GOOD  The statement column is indented by STRUCTURE, as
the compiler reads it, not as written: the doubled 'goto fail;' (line 31)
stands at the level of the 'if' lines -- which the source's indentation
hid. The FLOW column: '|' a reachable statement, 'X' an
unreachable one; '-err->' a jump taken only on error, '=ALWAYS=>' a jump
taken every time. In apple-2014 the X's begin right under '=ALWAYS=>' and
end at 'fail:' -- the signature check is among them. Then the run table:
'returns 0' for a forgery is the vulnerability. The flow picture is
'##! verbatim' (a column is its meaning); all is exact. Laws on the
bindings '((unreachable: N))' and '((forged_accepted: N))': '== 0' for
fixed, '> 0' for the published file.
______________________________________________________________________________
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.join(HERE, "..")
CHOICES = ("apple-2014", "fixed")
FUNCTION = "SSLVerifySignedServerKeyExchange"

HEADER = re.compile(r"^\s*(if|else\s+if|while|for)\s*\(.*\)\s*$|^\s*else\s*$")
GOTO = re.compile(r"^\s*goto\s+(\w+)\s*;\s*$")
LABEL = re.compile(r"^\s*(\w+)\s*:\s*$")


def statements(path):
    """RETURN: [(line number, text, depth)] of the function body, one entry
               per statement, header, label or brace; string literals blanked."""
    lines = open(path).read().split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith(FUNCTION))
    result, depth, buf, first = [], 0, "", None
    for i in range(start, len(lines)):
        raw = lines[i]
        code = re.sub(r'"([^"\\]|\\.)*"', '""', raw.split("//")[0])
        opened = depth
        depth += code.count("{") - code.count("}")
        if opened == 0 and depth == 0:
            continue
        if opened == 1 and depth == 0:          # the function's closing brace
            break
        if not code.strip() or code.strip() in ("{",):
            continue
        if first is None:
            first = i + 1
        buf += (" " if buf else "") + raw.strip()
        if code.rstrip().endswith((";", "{", "}")) or HEADER.match(code) or LABEL.match(code):
            result.append((first, buf, min(opened, depth)))
            buf, first = "", None
    return result


def walk(stmt_list):
    """RETURN: ([(line, text, depth, guarded, mark, flow)], [duplicate lines]);
               mark '|' reachable or 'X' unreachable."""
    rows, duplicates = [], []
    reachable_at = {1: True}           # depth -> is the next statement reachable
    conditional_at = {1: False}        # depth -> was the block opened by an 'if'
    guarded, prev_goto = False, None
    for line, text, depth in stmt_list:
        if text.startswith("}"):                       # a block closes
            for d in [d for d in reachable_at if d > depth]:
                del reachable_at[d], conditional_at[d]
        if LABEL.match(text):
            reachable_at[depth] = True
        mark = "|" if all(reachable_at.get(d, True) for d in range(1, depth + 1)) else "X"
        flow = ""
        g = GOTO.match(text)
        if g:
            if prev_goto == text:
                duplicates.append(line)
            conditional = guarded or conditional_at.get(depth, False)
            flow = ("-err-> %s" if conditional else "=ALWAYS=> %s") % g.group(1)
            if not guarded:
                reachable_at[depth] = False
        elif text.startswith("return") and not guarded:
            reachable_at[depth] = False
        elif LABEL.match(text):
            flow = "<- every jump lands here"
        if text.endswith("{"):                         # a block opens
            reachable_at[depth + 1] = True
            conditional_at[depth + 1] = text.startswith("if")
        rows.append((line, text, depth, guarded, mark, flow))
        prev_goto = text if g else None
        guarded = bool(HEADER.match(text))
    return rows, duplicates


def gcc_opinion(path, scratch):
    r = subprocess.run(["gcc", "-c", "-Wmisleading-indentation", "-I", TOP, "-o",
                        os.path.join(scratch, "x.o"), path], capture_output=True, text=True)
    return sorted({int(m.group(1)) for m in re.finditer(r"sslKeyExchange\.c:(\d+):\d+: warning", r.stderr)})


def run_handshake(path, scratch):
    exe = os.path.join(scratch, "handshake")
    subprocess.run(["gcc", "-O2", "-Wall", "-Wno-misleading-indentation", "-I", TOP, "-o", exe,
                    os.path.join(TOP, "handshake.c"), path], check=True)
    return subprocess.run([exe], capture_output=True, text=True, check=True).stdout.splitlines()


def main(choice):
    path = os.path.join(TOP, choice, "sslKeyExchange.c")
    rows, duplicates = walk(statements(path))
    unreachable = [r for r in rows if r[4] == "X" and not r[1].startswith("}")]
    print("file: %s/sslKeyExchange.c   function: %s()" % (choice, FUNCTION))
    print()
    print("CONTROL FLOW of the function body, from the first check on")
    print("##! verbatim")
    print(" line  reach  statement" + " " * 57 + "flow")
    started = False
    for line, text, depth, guarded, mark, flow in rows:
        started = started or text.startswith("if")
        if not started:
            continue
        shown = "    " * (depth - 1 + guarded) + text
        shown = shown if len(shown) <= 64 else shown[:61] + "..."
        print((" %4d    %s    %-64s  %s" % (line, mark, shown, flow)).rstrip())
    print("####")
    print("('|' reachable  'X' unreachable  '-err->' jump on error only  '=ALWAYS=>' unconditional jump)")
    print()
    if unreachable:
        print("UNREACHABLE  statements at lines %s" % ", ".join(str(u[0]) for u in unreachable))
    for line in duplicates:
        print("DUPLICATE    line %d repeats the goto of the line before" % line)
    scratch = tempfile.mkdtemp(prefix="gotofail-")
    try:
        warned = gcc_opinion(path, scratch)
        run = run_handshake(path, scratch)
    finally:
        shutil.rmtree(scratch, True)
    print("second opinion, gcc -Wmisleading-indentation: %s"
          % (", ".join("warns at line %d (the 'if' whose body looks like lines %d-%d)" % (w, w + 1, w + 2)
                       for w in warned) if warned else "no warning"))
    print("unreachable statements: ((unreachable: %d))   law == 0   %s"
          % (len(unreachable), "kept" if not unreachable else "BROKEN"))
    print()
    print("THE RUN: three ServerKeyExchange messages, verified by this file")
    forged = 0
    for line in run:
        print("  " + line)
        if not line.startswith("case 1") and "returns      0" in line:
            forged += 1
    print("forgeries accepted: ((forged_accepted: %d)) of 2   law == 0   %s" % (forged, "kept" if not forged else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICES:
        print("choices: %s" % ", ".join(CHOICES))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
