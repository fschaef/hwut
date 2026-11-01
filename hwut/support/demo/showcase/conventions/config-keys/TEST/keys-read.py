"""keys-read.py <dir> -- every configuration key the code under <dir> reads.

Prints one line per read: 'key file:line form', sorted. Not a test of its own
(no @hwut block); test-config-keys.sh calls it.

  *.py  parsed by Python's own parser (ast), so spelling, spacing, line breaks
        and nesting do not matter. Reads are
          os.getenv("X")  os.environ.get("X")  os.environ["X"]   -> env key X
          c.get*("s", "k")  c["s"]["k"]  c["s"].get*("k")        -> INI key s.k
        where c is a name assigned from configparser.ConfigParser().
  *.sh  every $X and ${X...} outside '...' and comments, whose X the script
        does not assign itself (X=, export X=, read X, for X in) and which is
        not one of the shell's standard variables (HOME, PATH, ...).
"""
import ast
import os
import re
import sys

SHELL_STANDARD = {"HOME", "PATH", "PWD", "OLDPWD", "USER", "SHELL", "TMPDIR", "LANG", "IFS"}
GETTERS = {"get", "getint", "getfloat", "getboolean"}


def const(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def dotted(node):
    """'os.environ' for Attribute(Name(os), environ); '' for anything else."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return dotted(node.value) + "." + node.attr
    return ""


def python_reads(path):
    tree = ast.parse(open(path).read(), path)
    cfg = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
           and isinstance(n.value, ast.Call) and dotted(n.value.func).endswith("ConfigParser")
           for t in n.targets if isinstance(t, ast.Name)}
    is_env = lambda n: dotted(n) in ("os.environ", "environ")
    is_cfg = lambda n: isinstance(n, ast.Name) and n.id in cfg
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and n.args:
            f, a = n.func, [const(x) for x in n.args]
            if dotted(f) in ("os.getenv", "getenv") and a[0]:
                yield a[0], n.lineno, "os.getenv"
            elif isinstance(f, ast.Attribute) and f.attr == "get" and is_env(f.value) and a[0]:
                yield a[0], n.lineno, "os.environ.get"
            elif isinstance(f, ast.Attribute) and f.attr in GETTERS:
                if is_cfg(f.value) and len(a) >= 2 and a[0] and a[1]:
                    yield a[0] + "." + a[1], n.lineno, "cfg.%s(s,k)" % f.attr
                elif isinstance(f.value, ast.Subscript) and is_cfg(f.value.value) \
                        and const(f.value.slice) and a[0]:
                    yield const(f.value.slice) + "." + a[0], n.lineno, "cfg[s].%s(k)" % f.attr
        elif isinstance(n, ast.Subscript) and const(n.slice):
            if is_env(n.value):
                yield const(n.slice), n.lineno, "os.environ[]"
            elif isinstance(n.value, ast.Subscript) and is_cfg(n.value.value) and const(n.value.slice):
                yield const(n.value.slice) + "." + const(n.slice), n.lineno, "cfg[s][k]"


def shell_reads(path):
    text = [re.sub(r"'[^']*'", "''", re.sub(r"(^|\s)#.*", "", l)) for l in open(path)]
    assigned = set()
    for l in text:
        assigned |= set(re.findall(r"(?:^|[\s;&|(])(?:export\s+|local\s+|readonly\s+)?([A-Za-z_]\w*)=", l))
        assigned |= set(re.findall(r"\bfor\s+([A-Za-z_]\w*)\s+in\b", l))
        for names in re.findall(r"\bread\s+((?:-\w+\s+)*[A-Za-z_][\w\s]*)", l):
            assigned |= {w for w in names.split() if not w.startswith("-")}
    for i, l in enumerate(text, 1):
        for braced, bare in re.findall(r"\$(?:\{([A-Za-z_]\w*)|([A-Za-z_]\w*))", l):
            name = braced or bare
            if name not in assigned and name not in SHELL_STANDARD:
                yield name, i, "${%s}" % name if braced else "$" + name


def main(root):
    read_list = []
    for d, _, files in os.walk(root):
        for f in files:
            path = os.path.join(d, f)
            reader = python_reads if f.endswith(".py") else shell_reads if f.endswith(".sh") else None
            if reader:
                rel = os.path.relpath(path, root)
                read_list += [(k, rel, line, form) for k, line, form in reader(path)]
    for k, rel, line, form in sorted(read_list):
        print("%s %s:%d %s" % (k, rel, line, form))


main(sys.argv[1])
