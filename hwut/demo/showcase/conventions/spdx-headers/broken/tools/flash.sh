#! /bin/bash
#
# flash.sh -- write the firmware image to the board over SWD
#
# Usage: flash.sh [image]   (default: build/fw.elf)
# Needs openocd 0.12 or newer on PATH.
#
# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Acme Embedded GmbH
set -e
openocd -f board.cfg -c "program ${1:-build/fw.elf} verify reset exit"
