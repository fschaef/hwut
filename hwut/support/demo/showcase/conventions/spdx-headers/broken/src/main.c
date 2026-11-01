/* SPDX-License-Identifier: MIT
 * Copyright (c) 2024 Acme Embedded GmbH
 */
#include "board.h"

int main(void) { board_init(); for (;;) { board_poll(); } }
