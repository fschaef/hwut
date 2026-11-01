#! /usr/bin/env python3
# @hwut {
#     title    = "UART receiver (8N1, 4x oversampling): bytes out of a sampled RX line"
#     features = ["bytes-as-sent", "mid-bit-look"]
#     choices {
#         clean        { tolerance { constraints = ["wrong_bytes == 0"] } }
#         noise        { features = ["framing-error", "glitch-rejected", "mid-bit-look"]
#                        tolerance { constraints = ["wrong_bytes == 0"] } }
#         fast-3       { features = ["bytes-as-sent", "clock-tolerance"]
#                        tolerance { constraints = ["wrong_bytes == 0"] } }
#         fast-12      { features = ["clock-tolerance", "garbage-shown"]
#                        tolerance { constraints = ["wrong_bytes > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  where the UART receiver sampled each frame of one captured RX line,
         and the bytes it delivered against those sent
REQUIREMENT  The receiver delivers exactly the bytes that were sent; a frame
             whose stop bit is low is flagged as a framing error; a spike on
             the idle line is never taken for a start bit; a sender whose
             clock is off by 3 % is still read correctly.

The unit is C ('../uart_rx.c'), a state machine called once per sample of
the RX pin, as from a timer interrupt; '../decode.c' feeds it a capture from
'../captures/' (a logic-analyser export as text: '-' high, '_' low, one
character per sample) and prints where the receiver LOOKED and what it
delivered. This test draws every frame the receiver saw:

    line   the samples of the frame window
    look   where the receiver sampled: S start, 0..7 data bits (LSB first),
           T stop -- the letter stands IN the column of the sample
    value  the level it read there

and judges what was delivered against what the sender sent (given per
choice, as the sender's log would say).

clean    'Hi!\\n' at the nominal rate: every look in the middle of a bit.
noise    a one-sample spike on the idle line (rejected as a glitch at the
         start look) and a frame whose stop bit is held low (FERR).
fast-3   the sender's clock 3 % fast: the looks drift towards the end of
         the bit cells and still land inside them.
fast-12  12 % fast: the looks drift into the neighbouring bits. The bytes
         come out WRONG with a valid stop bit -- the GOOD file is the
         accepted picture of how a baud mismatch goes unnoticed by the
         framing check, with '!!' where the bytes differ from those sent.

HWUT CONCEPTS  Each frame's picture is a '##! verbatim' region: the column
of a look relative to the edges of the line IS the finding (drift). All
else is exact text: the decoder is deterministic. The number of byte
positions in which the good frames differ from what was sent (a missing or
extra byte counts too) is a constraint binding, '((wrong_bytes: N))':
'wrong_bytes == 0' for clean, noise and fast-3, 'wrong_bytes > 0' for
fast-12 -- 'hwut.accept' refuses a re-recording that delivers other bytes
than were sent, or a fast-12 that no longer shows the garbage. A reviewer
reads the look row against the line row and the 'sent/received' lines at
the end.
______________________________________________________________________________
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
CHOICE_DB = {   # capture, what the sender sent
    "clean":   ("hello.cap",   b"Hi!\n"),
    "noise":   ("noise.cap",   b"O?K"),
    "fast-3":  ("fast-3.cap",  b"Hi!\n"),
    "fast-12": ("fast-12.cap", b"Hi!\n"),
}


def build_and_decode(capture_path):
    with tempfile.TemporaryDirectory() as build:
        exe = os.path.join(build, "decode")
        subprocess.check_call(["gcc", "-Wall", "-Werror", "-I", UNIT, "-o", exe,
                               os.path.join(UNIT, "decode.c"), os.path.join(UNIT, "uart_rx.c")])
        with open(capture_path) as fh:
            return subprocess.run([exe], stdin=fh, capture_output=True, text=True, check=True).stdout


def samples_of(capture_path):
    with open(capture_path) as fh:
        return "".join(ch for line in fh if not line.startswith("#") for ch in line if ch in "-_")


def show(byte):
    return repr(chr(byte))[1:-1] if 32 <= byte < 127 or byte == 10 else "\\x%02x" % byte


def main(choice):
    capture, sent = CHOICE_DB[choice]
    path = os.path.join(UNIT, "captures", capture)
    line = samples_of(path)
    pending, event_list = [], []          # a frame owns the looks before it
    for record in build_and_decode(path).splitlines():
        word = record.split()
        if word[0] == "LOOK":
            pending.append((int(word[1]), word[2], word[3]))
        else:
            event_list.append((word, pending))
            pending = []

    note = open(path).readline().lstrip("# ").strip()
    print("capture: captures/%s -- %s; %d samples, 4 per nominal bit" % (capture, note, len(line)))
    print()
    received = []
    legend = True
    for event, look_list in event_list:
        start = int(event[1])
        lo = max(0, start - 3)
        end = min(look_list[-1][0] + 4, len(line))
        window = range(lo, end)
        mine = dict((at, (what, level)) for at, what, level in look_list)
        look_row = "".join(mine[k][0] if k in mine else "." for k in window)
        value_row = "".join(mine[k][1] if k in mine else "." for k in window)
        if event[0] == "GLITCH":
            print("sample %d: falling edge, start bit NOT confirmed at its middle -> glitch, ignored" % start)
        else:
            value = int(event[2], 16)
            received.append((value, event[3]))
            print("sample %d: frame, byte 0x%02x '%s', stop bit %s"
                  % (start, value, show(value), "high (ok)" if event[3] == "ok" else "LOW -> framing error"))
        print("##! verbatim")
        print("    line   %s" % line[lo:end])
        print("    look   %s" % look_row)
        print("    value  %s" % value_row)
        print("####")
        if legend:
            print("(line: one character per sample, 4 per bit, '-' high '_' low; look: where the receiver")
            print(" sampled -- S start, 0..7 data bits LSB first, T stop; value: the level it read; '.' no sample)")
            legend = False
        print()

    print("sent:      %s" % " ".join("'%s'" % show(b) for b in sent))
    print("received:  %s" % " ".join("'%s'%s" % (show(v), "" if ok == "ok" else "(FERR)")
                                     for v, ok in received))
    good = [v for v, ok in received if ok == "ok"]
    expect = [b for b in sent if b != ord("?")] if choice == "noise" else list(sent)
    print("frames:    %d, framing errors: %d, glitches: %d"
          % (len(received), sum(ok != "ok" for _, ok in received),
             sum(e[0] == "GLITCH" for e, _ in event_list)))
    if good == expect:
        print("verdict:   the frames without framing error carry exactly the bytes sent")
    else:
        print("verdict:   !! the frames without framing error carry %s, the sender sent %s"
              % (" ".join("0x%02x" % v for v in good), " ".join("0x%02x" % v for v in expect)))
    differ = sum(1 for a, b in zip(good, expect) if a != b)
    missing, extra = max(0, len(expect) - len(good)), max(0, len(good) - len(expect))
    wrong_n = differ + missing + extra
    print("bytes not as sent: ((wrong_bytes: %d)) = %d wrong + %d missing + %d extra   law == 0   %s"
          % (wrong_n, differ, missing, extra, "kept" if not wrong_n else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
