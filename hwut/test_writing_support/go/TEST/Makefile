# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# The Go test applications, each built by 'go build' from its one source:
# the support packages are found through '../go.mod' (module
# 'hwut/test_writing_support/go'). Go's build cache holds what two targets
# share, and it is safe for builds at the same time; no other file is shared
# between two targets, so hwut may build several tests of this directory at
# once (services E-210: the build runs here, where this Makefile stands).
#
# 'go build' is asked every time -- it knows best what is out of date; a
# product that is current is not written again.
#
# OFFLINE: no module is required, and no toolchain is fetched
# (GOTOOLCHAIN=local). Where HOME is not writable, Go's cache stands under
# this directory ('.gocache').
#______________________________________________________________________________
GO ?= go
export GOTOOLCHAIN = local
export GOFLAGS     = -mod=mod
ifeq ($(GOCACHE),)
ifneq ($(shell test -w "$$HOME" && echo writable),writable)
export GOCACHE = $(CURDIR)/.gocache
endif
endif

%.exe: %.go FORCE
	$(GO) build -o $@ $<

clean:
	rm -f *.exe
	rm -rf .gocache

FORCE:
.PHONY: clean FORCE
