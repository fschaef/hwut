# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# THE GO DEMONSTRATION'S BUILD: every program here is built by 'go build' from
# its one source ('shop.exe' and 'fixture.exe' with 'sqlite.go' beside it).
#
#     make demo.exe          what hwut asks, for a test whose header says
#                            'build { framework = "make", executable = "%.exe" }'
#     make helpers           what 'on_entry' asks: the programs that are no
#                            test, and 'shop.exe' for 'delivery.json'
#
# WHERE THE SUPPORT STANDS is said on ONE line, the one marked below: the
# variable HWUT_SUPPORT_GO where it is set, else the port beside this demo in
# the clone. Go has no search path for a module: a workspace names it. Each
# target writes a workspace of its OWN, '.gowork/<stem>.work' -- this
# directory's module and the support's -- and builds with GOWORK naming it.
# No file is shared between two targets but Go's build cache, which is safe
# for builds at the same time; so hwut may build several tests at once
# (services E-210: the build runs here, where this Makefile stands).
#
# OFFLINE: no module is required, and no toolchain is fetched
# (GOTOOLCHAIN=local). Where HOME is not writable, Go's cache stands under
# this directory ('.gocache').
#______________________________________________________________________________
SUPPORT := $(or $(HWUT_SUPPORT_GO),../../../test_writing/go)   # HWUT-SUPPORT-PATH

GO ?= go
export GOTOOLCHAIN = local
unexport GOFLAGS
ifeq ($(GOCACHE),)
ifneq ($(shell test -w "$$HOME" && echo writable),writable)
export GOCACHE = $(CURDIR)/.gocache
endif
endif

HELPER_LIST = fixture.exe viewer.exe producer.exe shop.exe

#  RETURN: the workspace file of target '$*' written, naming this module
#          and the support; else make stops on the failing command.
define workspace
	@mkdir -p .gowork
	@printf 'go 1.24\n\nuse (\n\t%s\n\t%s\n)\n' "$(CURDIR)" "$(abspath $(SUPPORT))" > .gowork/$*.work
endef

helpers: $(HELPER_LIST)

shop.exe fixture.exe: %.exe: %.go sqlite.go FORCE
	$(workspace)
	GOWORK=$(CURDIR)/.gowork/$*.work $(GO) build -o $@ $*.go sqlite.go

%.exe: %.go FORCE
	$(workspace)
	GOWORK=$(CURDIR)/.gowork/$*.work $(GO) build -o $@ $<

clean:
	rm -f *.exe stock.csv
	rm -rf .gowork .gocache

FORCE:
.PHONY: helpers clean FORCE
