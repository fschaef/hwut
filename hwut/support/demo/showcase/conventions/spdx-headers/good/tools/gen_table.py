#! /usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Acme Embedded GmbH
"""gen_table.py -- generate the sine table of the PWM modulator."""
import math
print(",".join("%d" % round(32767 * math.sin(2 * math.pi * i / 64)) for i in range(64)))
