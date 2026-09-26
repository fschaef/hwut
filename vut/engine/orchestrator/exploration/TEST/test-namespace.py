#! /usr/bin/env python3
#
# @hwut {
#     title = "The configuration namespace: which key is read where."
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE NAMESPACE, AS THE READER ENFORCES IT -- not as a table says.
         Every key the framework knows is written, with a well-formed
         minimal value, into each place a key can stand; a scratch tree is
         explored as 'hwut.run' explores it; the faults decide:

             +    read here
             -    refused here, by name (VOCABULARY)
             ?    the value's shape refused (TYPE) -- the key is read here
             .    no fault and no effect: SILENTLY DROPPED

         '.' is the one mark that must never appear: a key written where
         nothing reads it and nothing says so hides a mistake.

The places:

    root        'hwut-root.conf', top level
    root.def    'hwut-root.conf', inside 'app_defaults'
    dir         a test directory's 'hwut.conf', top level
    dir.def     a test directory's 'hwut.conf', inside 'app_defaults'
    dir.app     a test directory's 'hwut.conf', inside one 'apps' entry
    header      a source file's '@hwut { }'
    choice      inside one choice of the header
______________________________________________________________________________
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, *[".."] * 5)))

from vut.engine.orchestrator.exploration.tree_explorer import explore_tree_stream
from vut.engine.orchestrator.exploration.configuration_tree import KEY_TO_FIELD

#  EVERY KEY THE FRAMEWORK KNOWS, with a minimal well-formed value.
VALUE_DB = {
    #  test parameters
    "build":                   'build { framework = "make"  executable = "app" }',
    "caps":                    "caps { timeout_sec = 5 }",
    "pype":                    'pype = "cat"',
    "tolerance":               "tolerance { slash = false }",
    "diff_display_parameters": "diff_display_parameters { margin = 0.2 }",
    "same":                    "same = true",
    "interactive":             "interactive = true",
    "execute":                 'execute = "./$file"',
    "output":                  'output = ["<stdout>"]',
    #  a specification's structure
    "title":                   'title = "T"',
    "language":                'language = "bash"',
    "choices":                 'choices = ["c"]',
    #  directory keys
    "on_entry":                'on_entry = "true"',
    "on_exit":                 'on_exit = "true"',
    "test_directory":          'test_directory = "TEST"',
    "ignore":                  'ignore = ["x.log"]',
    "collision":               'collision = ["test-x.sh"]',
    "dependency":              'dependency { "test-x.sh" = [] }',
    "target":                  'target { t = "./t.sh" }',
    "app_defaults":             "app_defaults { }",
    "apps":                    'apps { "test-y.sh" { title = "Y" } }',
    "language-setup":          'language-setup { bash { extensions = [".sh"] } }',
    "variant_group":           'variant_group { g { a { } } }',
    #  a person's preference, not a project's
    "colors":                  "colors { }",
}
assert set(KEY_TO_FIELD) <= set(VALUE_DB), \
       "a test parameter the probe does not know: %s" % (set(KEY_TO_FIELD) - set(VALUE_DB))

PLACE_LIST = ["root", "root.def", "dir", "dir.def", "dir.app", "header", "choice"]


def tree_of(place, line):
    """RETURN: (str, str|None, str), the root conf, the directory conf and
    the header with 'line' written into 'place'."""
    root, directory = "hwut {\n%s\n}\n", None
    header = '@hwut {\n    title = "T"\n%s\n}'
    rl = dl = hl = ""
    if   place == "root":     rl = line
    elif place == "root.def": rl = "app_defaults { %s }" % line
    elif place == "dir":      dl = line
    elif place == "dir.def":  dl = "app_defaults { %s }" % line
    elif place == "dir.app":
        dl = 'apps { "test-y.sh" { %s\n %s } }' % ("" if line.startswith("title")
                                                  else 'title = "Y"', line)
    elif place == "header":   hl = line
    elif place == "choice":   hl = 'choices { c { %s } }' % line
    directory = ("hwut {\n%s\n}\n" % dl) if dl else None
    return root % rl, directory, header % hl


def verdict(place, key):
    """RETURN: str, one of '+', '-', '?', '.' -- how the reader answered
    'key' written into 'place'."""
    with tempfile.TemporaryDirectory() as work:
        return _verdict_in(work, place, key)


def _verdict_in(work, place, key):
    """RETURN: str, 'verdict' for one scratch tree 'work', which the
    caller removes."""
    os.makedirs(os.path.join(work, "t", "TEST"))
    root, directory, header = tree_of(place, VALUE_DB[key])
    if place == "header" and key == "title": header = '@hwut {\n    title = "T"\n}'
    open(os.path.join(work, "hwut-root.conf"), "w").write(root)
    if directory is not None:
        open(os.path.join(work, "t", "TEST", "hwut.conf"), "w").write(directory)
    for name in ("test-x.sh", "test-y.sh"):
        path = os.path.join(work, "t", "TEST", name)
        body = header if name == "test-x.sh" else ""
        open(path, "w").write("#!/bin/bash\n"
                              + "".join("# %s\n" % l for l in body.splitlines())
                              + 'echo x\necho "<hwut-end>"\n')
        os.chmod(path, 0o755)
    fault_list = []
    try:
        for _rel, result in explore_tree_stream(work, fault_list=fault_list):
            fault_list.extend(result.fault_list)
    except Exception as error:                     # noqa: BLE001
        return "!%s" % type(error).__name__
    named = [str(f) for f in fault_list if "'%s'" % key in str(f)]
    if any("VOCABULARY" in f for f in named): return "-"
    if named:                                  return "?"
    if fault_list:                             return "?"
    return "+" if _read_f(work, place, key) else "."


def _read_f(work, place, key):
    """RETURN: bool, True where the stated value reached what the reader
    built -- a spec field, or an application's parameters."""
    fault_list = []
    for _rel, result in explore_tree_stream(work, fault_list=fault_list):
        app_set = result.app_set
        spec    = app_set.directory_spec
        for attr in ("title", "on_entry", "on_exit", "test_directory",
                     "ignore", "collision", "dependency", "target_db",
                     "app_defaults", "language_setup", "variant_db"):
            if key.replace("-", "_") in attr or (key == "target" and attr == "target_db") \
               or (key == "variant_group" and attr == "variant_db"):
                if getattr(spec, attr, None): return True
        for app in app_set:
            field = KEY_TO_FIELD.get(key)
            #  'apps' IS READ where it makes a header-less file a test:
            #  'test-y.sh' carries no '@hwut'.
            if key == "apps" and app.source_file == "test-y.sh" \
               and place not in ("dir.app",): return True
            if field is not None:
                for parameters in (app.choice_db or {}).values():
                    if getattr(parameters, field, None) is not None: return True
            if key in ("title", "language", "choices"): return True
    return key in ("app_defaults", "apps", "dependency", "collision", "colors") and False


def main():
    """RETURN: None. The namespace table."""
    print("%-24s %s" % ("key", "  ".join("%-8s" % p for p in PLACE_LIST)))
    for key in VALUE_DB:
        print("%-24s %s" % (key, "  ".join("%-8s" % verdict(p, key) for p in PLACE_LIST)))
    print("<hwut-end>")


if __name__ == "__main__":
    if "--hwut-info" in sys.argv:
        print("The configuration namespace: which key is read where.;"); sys.exit(0)
    main()
