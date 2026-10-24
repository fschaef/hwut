#! /usr/bin/env python3
"""make_captures.py -- draws the three captures of this directory as text,
the way a logic analyser export looks after thresholding: '-' high, '_'
low, one character per sample, 4 samples per nominal bit. Run once; the
.cap files are the fixtures (committed), this script is their recipe."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def frame_bits(byte, stop=1):
    return [0] + [(byte >> i) & 1 for i in range(8)] + [stop]


def render(bit_list, samples_per_bit):
    """RETURN: the samples of a bit sequence sent with 'samples_per_bit'."""
    total = int(len(bit_list) * samples_per_bit)
    return "".join("-" if bit_list[min(int(k / samples_per_bit), len(bit_list) - 1)] else "_"
                   for k in range(total))


def write(name, note, samples):
    with open(os.path.join(HERE, name), "w") as fh:
        fh.write("# %s\n# 8N1, receiver expects 4 samples per bit; '-' high, '_' low\n" % note)
        for k in range(0, len(samples), 64):
            fh.write(samples[k:k + 64] + "\n")


def idle(bit_n):
    return [1] * bit_n


# clean: "Hi!\n", exactly 4 samples per bit, varying idle gaps
bits = idle(3)
for byte, gap in zip(b"Hi!\n", (1, 2, 1, 3)):
    bits += frame_bits(byte) + idle(gap)
write("hello.cap", "clean line: 'Hi!\\n' at the nominal rate", render(bits, 4))

# noise: 'O', a one-sample spike on the idle line, a frame with its stop bit
# held low (the sender's break), then 'K'
s = render(idle(3) + frame_bits(ord("O")) + idle(3), 4)
s = s[:-6] + "_" + s[-5:]                             # the spike
s += render(frame_bits(ord("?"), stop=0) + [0, 0] + idle(3) + frame_bits(ord("K")) + idle(3), 4)
write("noise.cap", "'O', a spike, a frame with a low stop bit, 'K'", s)

# senders whose clocks run fast: 3 % (inside the tolerance of a mid-bit look
# over ten bits) and 12 % (far outside)
for pct in (3, 12):
    write("fast-%d.cap" % pct, "'Hi!\\n' from a sender whose clock runs %d %% fast" % pct,
          render(idle(3) + sum((frame_bits(b) + idle(1) for b in b"Hi!\n"), []), 4 / (1 + pct / 100.0)))
