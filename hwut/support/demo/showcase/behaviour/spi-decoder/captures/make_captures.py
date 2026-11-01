#! /usr/bin/env python3
"""make_captures.py -- the recipe of the SPI captures in this directory.

A capture is what a 4-channel logic analyser exports after thresholding,
drawn as text: one line per channel, '-' high, '_' low, one character per
sample. SPI mode 0: SCK idles low, data changes on the falling edge and is
sampled on the rising edge, MSB first, CS active low. One SCK period is
two samples."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def transaction(mosi_bytes, miso_bytes, bit_n=None):
    """RETURN: (cs, sck, mosi, miso) sample strings of one CS-low phase."""
    bit_n = 8 * len(mosi_bytes) if bit_n is None else bit_n
    cs, sck, mosi, miso = "_", "_", "_", "-"
    for k in range(bit_n):
        m = (mosi_bytes[k // 8] >> (7 - k % 8)) & 1
        s = (miso_bytes[k // 8] >> (7 - k % 8)) & 1
        cs += "__"
        sck += "_-"
        mosi += "-" * 2 if m else "_" * 2
        miso += "-" * 2 if s else "_" * 2
    return cs + "_", sck + "_", mosi + "_", miso + "-"


def idle(n):
    return "-" * n, "_" * n, "_" * n, "-" * n


def write(name, note, part_list):
    lane = ["".join(p[i] for p in part_list) for i in range(4)]
    with open(os.path.join(HERE, name), "w") as fh:
        fh.write("# %s\n# SPI mode 0, one SCK period = 2 samples\n" % note)
        for label, samples in zip(("CS", "SCK", "MOSI", "MISO"), lane):
            fh.write("%-5s %s\n" % (label, samples))


write("read-id.cap", "JEDEC 'read ID' (0x9f) to a W25Q128 flash",
      [idle(3), transaction([0x9F, 0, 0, 0], [0xFF, 0xEF, 0x40, 0x18]), idle(3)])
write("write-enable.cap", "'write enable' (0x06), then 'read status' (0x05)",
      [idle(3), transaction([0x06], [0xFF]), idle(4),
       transaction([0x05, 0], [0xFF, 0x02]), idle(3)])
# EMI on CS: the line rises for two samples after 11 bits of a read ID
cs, sck, mosi, miso = transaction([0x9F, 0, 0, 0], [0xFF, 0xEF, 0x40, 0x18])
cut = 1 + 2 * 11
cs = cs[:cut] + "--" + cs[cut + 2:]
write("cs-glitch.cap", "'read ID' with a 2-sample spike on CS after bit 11",
      [idle(3), (cs, sck, mosi, miso), idle(3)])
