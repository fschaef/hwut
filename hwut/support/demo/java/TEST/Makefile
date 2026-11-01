# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# THE DEMONSTRATION'S BUILDS. 'x.java' holds the class 'X' (not public: the
# file's name is no class name); 'make x.exe' compiles it, with the support
# classes it uses, into 'x.classes/' -- ITS OWN directory: nothing is shared
# between two targets, so hwut may build several tests at once (services
# E-210: the build runs here, where this Makefile stands). 'x.exe' is a
# launcher: 'java -cp x.classes X'.
#
# WHERE THE SUPPORT STANDS -- the one line below, and nowhere else: Java's
# own CLASSPATH first (javac searches it for sources too), then the support
# beside this tree.
#
# '--enable-preview': the Foreign Function & Memory API (libvterm, the
# pseudo-terminal, SQLite) is final in JDK 22, a preview in JDK 21.
# JAVA_TOOL_OPTIONS is moved onto the command line by the launcher, so the
# JVM's note 'Picked up JAVA_TOOL_OPTIONS' stands in no test's output.
#______________________________________________________________________________
JAVAC       ?= javac
JAVA        ?= java
JAVAC_FLAGS ?= --release 21 --enable-preview -XDsuppressNotes -encoding UTF-8
JAVA_FLAGS  ?= --enable-preview --enable-native-access=ALL-UNNAMED
SUPPORT      = $(if $(CLASSPATH),$(CLASSPATH):)../../../test_writing/java# HWUT-SUPPORT-PATH
SOURCE       = $(foreach d,$(subst :, ,$(SUPPORT)),$(wildcard $(d)/hwut/*.java))

#  'demo' -> 'Demo'
class_of = $(shell echo '$(1)' | sed -E 's/(^|[-_])([a-z])/\U\2/g')

%.exe: %.java $(SOURCE)
	rm -rf $*.classes $@
	$(JAVAC) $(JAVAC_FLAGS) -sourcepath .:$(SUPPORT) -d $*.classes $<
	{ echo '#!/bin/sh'; \
	  echo '# Made by the Makefile: runs $< compiled in $*.classes.'; \
	  echo 'set -f; o=$$JAVA_TOOL_OPTIONS; unset JAVA_TOOL_OPTIONS'; \
	  echo 'exec $(JAVA) $(JAVA_FLAGS) $$o -cp "$$(dirname "$$0")/$*.classes" $(call class_of,$*) "$$@"'; \
	} > $@.tmp
	chmod +x $@.tmp
	mv $@.tmp $@

#  The shop and its fixture speak to SQLite through 'Sqlite.java'; each
#  compiles its own copy of it. The screen runs the viewer.
shop.exe fixture.exe: Sqlite.java
screen.exe: viewer.exe

all: $(patsubst %.java,%.exe,$(filter-out Sqlite.java producer.java,$(wildcard *.java)))

clean:
	rm -rf *.exe *.exe.tmp *.classes

.PHONY: all clean
