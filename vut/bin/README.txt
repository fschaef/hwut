==============================================================================
bin -- THE LAUNCHER ROOF
==============================================================================

Every launcher of the tool stands here, and beside them ONE file that is
not a launcher: '.hwut.conf', the installation's default PREFERENCES
(services E-78). The launchers are two-line shell shims, nothing
importable; each resolves its own location ('readlink -f'), so it answers
by PATH and by path alike.

    .hwut.conf      how hwut SHOWS things -- colours today. A person's
                    '~/.hwut.conf' is read over it, key by key; its
                    comments list the words a colour may be written
                    with. A project never holds a preference.

    hwut.<name>     runs 'python3 -m vut.services.<name>' with the
                    package root's parent prepended to PYTHONPATH --
                    one shim per service face:

                        hwut.config.show     hwut.plan     hwut.run
                        hwut.accept   hwut.target   hwut.cov
                        hwut.diff     hwut.report.details
                        hwut.stability  hwut.wishlist  hwut.report
                        hwut.remove
                        hwut.rename   hwut.move
                        hwut.sanitize hwut.pype

    hwut            THE DEFAULT FACE: 'hwut' alone is 'hwut.run'. A
                    bare 'hwut' states no wish, and a wish that states
                    nothing wants everything -- so it runs the whole
                    tree below the current directory.

                    A launcher's name is the face's name with '-' where
                    the module has '_': a face 'hwut.some-name' runs
                    'services/some_name.py'. A dot cannot stand in a
                    module name, and a module name is what the naming
                    law binds.

    hwut.pype       is one of them: 'services/pype.py', the face over
                    'test_writing_support/hwut_pype'. A '#! /usr/bin/env
                    hwut.pype' she-bang line reaches it when this
                    directory is on PATH.

A launcher holds no logic: no argument is read, no default is chosen,
no path but its own is resolved. The face behind it owns everything the
command line means; 'services/README.txt' states the naming law that
binds the two.

TEST/ drives every launcher and pins that each answers, that the PATH
and by-path forms agree, and that a launcher adds nothing to its face's
own voice.
