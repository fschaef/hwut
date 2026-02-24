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
  keywords:  Detailed log of keyword-based flagging (e.g., ssh, sudo).
  suid_bits: Audit of how SUID (0o4000) and SGID (0o2000) trigger flags.
  sbin_exec: Validation of 'sbin' directory policy for any executable.
  whitelist: Verification of exclusion logic for whitelisted paths/names.

AUTHOR: Gemini HWUT-Unit Test Writer
        Frank-Rene Schaefer
"""

import sys
from   unittest.mock import MagicMock, patch

sys.path.insert(0, "../" * 4)

from   vut.language_support.python.hwut_runner          import HwutRunner
from   vut.language_support.python.deterministic_random import DeterministicStream
import vut.engine.sandbox.dangerous_executables         as     scanner

# Initialize deterministic random for repeatable test scenarios
ds = DeterministicStream(seed=0x42)

def print_result_list(results):
    """Helper to provide transparent output of findings."""
    if not results:
        print("RESULT: Forbidden list is empty.")
    else:
        print("RESULT: Forbidden binaries found:")
        for r in results:
            print(f"  - {r}")

def test_keywords():
    """Checks if risk keywords trigger a flag with transparent output."""
    # Test with a known keyword and a safe name
    files = [
        {"name": "ssh",    "path": "/bin/ssh",    "mode": 0o100755},
        {"name": "ls",     "path": "/bin/ls",     "mode": 0o100755},
        {"name": "netcat", "path": "/usr/bin/nc", "mode": 0o100755}
    ]
    
    mock_entries = []
    for f in files:
        m = MagicMock()
        m.name = f["name"]
        m.path = f["path"]
        m.is_file.return_value = True
        m.stat.return_value.st_mode = f["mode"]
        mock_entries.append(m)
        print(f"MOCK: File '{f['name']}' at {f['path']} (Mode: {oct(f['mode'])})")

    with patch("os.scandir") as mock_scandir:
        mock_scandir.return_value.__enter__.return_value = mock_entries
        results = scanner.get(path_env="/bin:/usr/bin")
        print_result_list(results)
        
        if "/bin/ssh" in results and "/usr/bin/nc" in results:
            print("SUCCESS: Keywords correctly identified.")

def test_suid_bits():
    """Audit of SUID/SGID bit detection."""
    # 0o4000 = SUID, 0o2000 = SGID
    test_cases = [
        {"name": "suid_app", "path": "/usr/bin/suid_app", "mode": 0o104755},
        {"name": "sgid_app", "path": "/usr/bin/sgid_app", "mode": 0o102755},
        {"name": "norm_app", "path": "/usr/bin/norm_app", "mode": 0o100755}
    ]

    mock_entries = []
    for tc in test_cases:
        m = MagicMock()
        m.name = tc["name"]
        m.path = tc["path"]
        m.is_file.return_value = True
        m.stat.return_value.st_mode = tc["mode"]
        mock_entries.append(m)
        print(f"MOCK: {tc['name']} with bits {oct(tc['mode'])}")

    with patch("os.scandir") as mock_scandir:
        mock_scandir.return_value.__enter__.return_value = mock_entries
        results = scanner.get(path_env="/usr/bin")
        print_result_list(results)
        
        if "/usr/bin/suid_app" in results and "/usr/bin/sgid_app" in results:
            print("SUCCESS: Elevated privileges correctly flagged.")

def test_sbin_exec():
    """Validation of sbin directory transparency."""
    # Any executable in sbin should be flagged regardless of name
    m = MagicMock()
    m.name = "custom_tool"
    m.path = "/sbin/custom_tool"
    m.is_file.return_value = True
    m.stat.return_value.st_mode = 0o100711 # Executable bits set
    
    print(f"MOCK: Non-keyword tool '{m.name}' in /sbin with mode {oct(0o100711)}")

    with patch("os.scandir") as mock_scandir:
        mock_scandir.return_value.__enter__.return_value = [m]
        results = scanner.get(path_env="/sbin")
        print_result_list(results)
        
        if "/sbin/custom_tool" in results:
            print("SUCCESS: sbin executable policy enforced.")

def test_whitelist():
    """Verification of whitelist exclusion transparency."""
    # sudo is a risk, but we whitelist it
    m = MagicMock()
    m.name = "sudo"
    m.path = "/usr/bin/sudo"
    m.is_file.return_value = True
    m.stat.return_value.st_mode = 0o104111 

    print(f"MOCK: High-risk binary '{m.path}'")
    print("ACTION: Adding 'sudo' to whitelist.")

    with patch("os.scandir") as mock_scandir:
        mock_scandir.return_value.__enter__.return_value = [m]
        results = scanner.get(path_env="/usr/bin", whitelist=["sudo"])
        print_result_list(results)
        
        if "/usr/bin/sudo" not in results:
            print("SUCCESS: Whitelist correctly bypassed risk detection.")

if __name__ == "__main__":
    choice_map = {
        "keywords":  test_keywords,
        "suid_bits": test_suid_bits,
        "sbin_exec": test_sbin_exec,
        "whitelist": test_whitelist
    }

    runner = HwutRunner(
        argv=sys.argv,
        title="Handling Dangerous Executables",
        choice_map=choice_map,
        happy="SUCCESS.*" 
    )
    runner.run()
