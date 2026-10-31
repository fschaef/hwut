# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# The Java test applications. 'test-x.java' holds the class 'TestX' (not
# public: the file's name is no class name); 'make test-x.exe' compiles it
# with the support classes it uses ('-sourcepath ..', package 'hwut') into
# 'test-x.classes/' -- ITS OWN directory: nothing is shared between two
# targets, so hwut may build several tests of this directory at once
# (services E-210: the build runs here, where this Makefile stands). The
# target 'test-x.exe' is a launcher: 'java -cp test-x.classes TestX'.
#
# '--enable-preview': the Foreign Function & Memory API ('hwut_vterm' calls
# libvterm and the pseudo-terminal through it) is final in JDK 22, a preview
# in JDK 21. JAVA_TOOL_OPTIONS is moved onto the command line by the
# launcher, so the JVM's note 'Picked up JAVA_TOOL_OPTIONS' stands in no
# test's output.
#______________________________________________________________________________
JAVAC       ?= javac
JAVA        ?= java
JAVAC_FLAGS ?= --release 21 --enable-preview -XDsuppressNotes -encoding UTF-8
JAVA_FLAGS  ?= --enable-preview --enable-native-access=ALL-UNNAMED
SUPPORT      = ..
SOURCE       = $(wildcard $(SUPPORT)/hwut/*.java)

#  'test-hwut_fsm' -> 'TestHwutFsm'
class_of = $(shell echo '$(1)' | sed -E 's/(^|[-_])([a-z])/\U\2/g')

%.exe: %.java $(SOURCE)
	rm -rf $*.classes $@
	$(JAVAC) $(JAVAC_FLAGS) -sourcepath $(SUPPORT) -d $*.classes $<
	{ echo '#!/bin/sh'; \
	  echo '# Made by the Makefile: runs $< compiled in $*.classes.'; \
	  echo 'set -f; o=$$JAVA_TOOL_OPTIONS; unset JAVA_TOOL_OPTIONS'; \
	  echo 'exec $(JAVA) $(JAVA_FLAGS) $$o -cp "$$(dirname "$$0")/$*.classes" $(call class_of,$*) "$$@"'; \
	} > $@.tmp
	chmod +x $@.tmp
	mv $@.tmp $@

all: $(patsubst %.java,%.exe,$(wildcard test-*.java))

clean:
	rm -rf *.exe *.exe.tmp *.classes

.PHONY: all clean
