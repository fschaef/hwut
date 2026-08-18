#!/usr/bin/env python3
"""
PURPOSE: Verify the security scanner's ability to identify high-risk binaries.

DESCRIPTION:

This test suite validates the logic of the `get` function. It focuses on
transparency by printing the specific file attributes (bits, paths, names)
being mocked and the resulting forbidden list. It covers keyword detection,
SUID/SGID bit analysis, sbin directory execution rules, and whitelist
filtering.

CHOICES:

  keywords:  Detailed log of keyword-based flagging (e.g., ssh, nc).
  suid_bits: Audit of how SUID (0o4000) and SGID (0o2000) trigger flags.
  sbin_exec: Validation of 'sbin' directory policy for any executable.
  whitelist: Verification of exclusion logic for whitelisted paths/names.

AUTHOR: Frank-Rene Schaefer
"""

import sys
from   unittest.mock import MagicMock, patch

sys.path.insert(0, "../" * 4)

from   vut.language_support.python.hwut_runner import HwutRunner
import vut.engine.sandbox.dangerous_executables as scanner

# Snapshot the default search dirs so each test can restore clean state.
_DEFAULT_SEARCH_DIRS = frozenset(vars(scanner)['__search_dirs'])


def _reset_state():
    """Reset module-level globals to their original values before each test."""
    vars(scanner)['__search_dirs'] = set(_DEFAULT_SEARCH_DIRS)


def _make_entry(name, path, mode):
    """
    Build a MagicMock that mimics an os.DirEntry for a regular file.
    """
    m = MagicMock()
    m.name                    = name
    m.path                    = path
    m.is_file.return_value    = True
    m.stat.return_value.st_mode = mode
    return m


def _scandir_for(dir_entry_map):
    """
    Return a side_effect callable for os.scandir that maps each directory
    path to its own list of mock entries, isolating tests from the default
    __search_dirs population.
    """
    def side_effect(directory):
        cm = MagicMock()
        cm.__enter__.return_value = dir_entry_map.get(directory, [])
        cm.__exit__.return_value  = False
        return cm
    return side_effect


def _print_result_list(results):
    """Print the forbidden-binary list in a format matched by the HWUT happy pattern."""
    if not results:
        print("RESULT: Forbidden list is empty.")
    else:
        print("RESULT: Forbidden binaries found:")
        for r in results:
            print(f"  - {r}")


def test_keywords():
    """
    Three files are mocked: ssh and nc are risk-keywords; ls is not.
    Only ssh and nc must appear in the result.
    """
    _reset_state()

    files = [
        ("ssh", "/bin/ssh",    0o100755),
        ("ls",  "/bin/ls",     0o100755),
        ("nc",  "/usr/bin/nc", 0o100755),
    ]
    for name, path, mode in files:
        print(f"MOCK: '{name}' at {path} (mode {oct(mode)})")

    dir_map = {
        "/bin":     [_make_entry(n, p, m) for n, p, m in files if "/bin/" == p[:5]],
        "/usr/bin": [_make_entry(n, p, m) for n, p, m in files if p.startswith("/usr/bin/")],
    }

    with patch("os.scandir", side_effect=_scandir_for(dir_map)):
        results = scanner.get(path_env="/bin:/usr/bin")
        _print_result_list(results)

        if "/bin/ssh" in results and "/usr/bin/nc" in results and "/bin/ls" not in results:
            print("SUCCESS: Keywords correctly identified.")
        else:
            print("FAIL: Keyword detection produced wrong result.")


def test_suid_bits():
    """
    suid_app (SUID) and sgid_app (SGID) must be flagged; norm_app must not.
    All three reside in /usr/bin so the sbin rule plays no role here.
    """
    _reset_state()

    test_cases = [
        ("suid_app", "/usr/bin/suid_app", 0o104755),  # SUID bit set
        ("sgid_app", "/usr/bin/sgid_app", 0o102755),  # SGID bit set
        ("norm_app", "/usr/bin/norm_app", 0o100755),  # neither
    ]
    for name, path, mode in test_cases:
        print(f"MOCK: '{name}' at {path} (mode {oct(mode)})")

    entries = [_make_entry(n, p, m) for n, p, m in test_cases]

    with patch("os.scandir", side_effect=_scandir_for({"/usr/bin": entries})):
        results = scanner.get(path_env="/usr/bin")
        _print_result_list(results)

        if (    "/usr/bin/suid_app" in     results
            and "/usr/bin/sgid_app" in     results
            and "/usr/bin/norm_app" not in results):
            print("SUCCESS: Elevated privileges correctly flagged.")
        else:
            print("FAIL: SUID/SGID detection produced wrong result.")


def test_sbin_exec():
    """
    A non-keyword tool with executable bits in /sbin must be flagged by the
    sbin-directory policy alone, regardless of its name.
    """
    _reset_state()

    name, path, mode = "custom_tool", "/sbin/custom_tool", 0o100711
    print(f"MOCK: Non-keyword '{name}' in /sbin (mode {oct(mode)})")

    with patch("os.scandir", side_effect=_scandir_for({"/sbin": [_make_entry(name, path, mode)]})):
        results = scanner.get(path_env="/sbin")
        _print_result_list(results)

        if "/sbin/custom_tool" in results:
            print("SUCCESS: sbin executable policy enforced.")
        else:
            print("FAIL: sbin executable was not flagged.")


def test_whitelist():
    """
    sudo is a known risk keyword, but once added to the whitelist it must
    be absent from the result regardless of its mode bits.
    """
    _reset_state()

    name, path, mode = "sudo", "/usr/bin/sudo", 0o104111
    print(f"MOCK: High-risk binary '{path}' (mode {oct(mode)})")
    print("ACTION: Adding 'sudo' to whitelist.")

    with patch("os.scandir", side_effect=_scandir_for({"/usr/bin": [_make_entry(name, path, mode)]})):
        results = scanner.get(path_env="/usr/bin", whitelist=["sudo"])
        _print_result_list(results)

        if "/usr/bin/sudo" not in results:
            print("SUCCESS: Whitelist correctly bypassed risk detection.")
        else:
            print("FAIL: Whitelisted binary appeared in forbidden list.")


if __name__ == "__main__":
    choice_map = {
        "keywords":  test_keywords,
        "suid_bits": test_suid_bits,
        "sbin_exec": test_sbin_exec,
        "whitelist": test_whitelist,
    }

    runner = HwutRunner(
        argv=sys.argv,
        title="Handling Dangerous Executables",
        choice_map=choice_map,
        happy="SUCCESS.*"
    )
    runner.run()
