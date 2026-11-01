#! /bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024 Acme Embedded GmbH
#
# flash.sh -- write the firmware image to the board over SWD
set -e
openocd -f board.cfg -c "program ${1:-build/fw.elf} verify reset exit"
