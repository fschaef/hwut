#  The prototype's build: the simulation, its image id first (README 14).
#  HWUT_REMOTE is the directory support/remote; copied elsewhere, set it.
HWUT_REMOTE ?= ../..
RE        := $(HWUT_REMOTE)
AGENT     := $(RE)/target/verilog/agent.v $(RE)/target/verilog/phy_stdio.v
INPUTS    := $(sort top.v adder.v $(AGENT)) Makefile
TOOLCHAIN := iverilog -V 2>&1 | head -1

TMP/uut.vvp: TMP/image_id top.v adder.v $(AGENT)
	iverilog -g2005 -I TMP -o $@ top.v adder.v $(AGENT)

include $(RE)/host/image_id.mk
