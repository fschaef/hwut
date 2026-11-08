#  SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#  ___________________________________________________________________________
#
#  host/image_id.mk -- THE IMAGE ID: a hash of everything that changes the
#  image (README 14). A writer's Makefile sets, then includes this file:
#
#      INPUTS     the files that change the image (sorted: order is no fact)
#      TOOLCHAIN  the compiler's version command
#
#  TMP/image_id holds eight hex digits and changes only when the hash does,
#  so make rebuilds the image only then; TMP/image_id.vh carries it into the
#  Verilog as the define IMAGE_ID.
#  ___________________________________________________________________________
TMP/image_id: FORCE
	@mkdir -p TMP
	@(cat $(INPUTS); $(TOOLCHAIN)) | sha256sum | cut -c1-8 > $@.new
	@if cmp -s $@.new $@; then rm $@.new; else mv $@.new $@; fi
	@if [ ! -f TMP/image_id.vh ] || [ TMP/image_id.vh -ot $@ ]; then \
	  echo "\`define IMAGE_ID 32'h$$(cat $@)" > TMP/image_id.vh; fi

.PHONY: FORCE
