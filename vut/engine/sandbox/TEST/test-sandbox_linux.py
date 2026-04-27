#!/usr/bin/env python3
"""
PURPOSE: Verify that SandboxLinux._build_cmd generates correct nsjail arguments.

DESCRIPTION:

Tests the nsjail command construction logic of SandboxLinux, obtained via
factory.get(). Covers structural integrity of the argument list, UID/GID
mapping, resource limit translation, network isolation flags, and forbidden
binary masking.

CHOICES:

  cmd_structure:     nsjail binary, mode flag, '--' separator, command placement.
  uid_gid_mapping:   --uid_mapping / --gid_mapping reflect actual process identity.
  resource_limits:   all four resource caps are correctly translated from config.
  network_host:      --disable_clone_newnet logic for shared vs isolated network.
  network_macvlan:   macvlan flags appear only when interface/IP/gateway are set.
  forbidden_masking: existing forbidden binaries are masked; absent ones are not.

AUTHOR: Frank-Rene Schaefer
"""

import os
import sys
from   unittest.mock import patch

sys.path.insert(0, "../" * 4)

from   vut.language_support.python.hwut_runner import HwutRunner
import vut.engine.sandbox.factory              as factory
from   vut.engine.sandbox.base                 import SandboxConfig

WORK_DIR = "/tmp"


def _get_sandbox(config=None):
    """
    RETURN: Sandbox, SandboxLinux instance obtained via factory.get().

    Forces sys.platform to 'linux' so the factory always dispatches to
    SandboxLinux regardless of the actual test host platform.
    """
    with patch("sys.platform", "linux"):
        return factory.get(config or SandboxConfig(fs_forbidden_apps=[]), WORK_DIR)


def _arg_after(args, flag):
    """
    RETURN: str,  value immediately following flag in args.
            None, if flag is absent or has no successor.
    """
    try:
        return args[args.index(flag) + 1]
    except (ValueError, IndexError):
        return None


def _all_values_after(args, flag):
    """
    RETURN: List[str], every args[i+1] where args[i] == flag, in order.

    Collects paired values for flags that appear multiple times (e.g. -R).
    """
    return [args[i + 1] for i in range(len(args) - 1) if args[i] == flag]


def _check(results):
    """
    RETURN: True,  all (bool, label) pairs in results are True; prints OK/FAIL per line.
            False, else.
    """
    ok = True
    for result, label in results:
        print(f"  {'OK  ' if result else 'FAIL'}: {label}")
        ok = ok and result
    return ok


# ---------------------------------------------------------------------------

def test_cmd_structure():
    """
    Verifies structural integrity: nsjail binary is first, mode is 'o',
    '--' separator is present, and the target command follows it exactly.
    """
    sandbox = _get_sandbox()
    cmd     = ["python3", "script.py", "--arg", "val"]
    args    = sandbox._build_cmd(cmd)

    sep_idx = args.index("--") if "--" in args else -1

    print(f"INSPECT: args[:6]     = {args[:6]}")
    print(f"INSPECT: args[-5:]    = {args[-5:]}")

    if _check([
        (args[0] == "/usr/bin/nsjail",           "nsjail binary is first argument"),
        (_arg_after(args, "--mode") == "o",       "--mode value is 'o'"),
        (sep_idx != -1,                           "'--' separator is present"),
        (args[sep_idx + 1:] == cmd,               "target command follows '--' unchanged"),
    ]):
        print("SUCCESS: Command structure is correct.")
    else:
        print("FAIL: Command structure has errors (see above).")


def test_uid_gid_mapping():
    """
    Verifies that --uid_mapping and --gid_mapping encode the actual process
    UID and GID so jailed root maps back to the calling user on the host.
    """
    uid     = os.getuid()
    gid     = os.getgid()
    args    = _get_sandbox()._build_cmd(["echo"])

    uid_map = _arg_after(args, "--uid_mapping")
    gid_map = _arg_after(args, "--gid_mapping")

    print(f"INSPECT: process uid={uid}, gid={gid}")
    print(f"INSPECT: --uid_mapping {uid_map}")
    print(f"INSPECT: --gid_mapping {gid_map}")

    if _check([
        (uid_map == f"0:{uid}:1", f"uid mapping encodes current uid ({uid})"),
        (gid_map == f"0:{gid}:1", f"gid mapping encodes current gid ({gid})"),
    ]):
        print("SUCCESS: UID/GID mapping is correct.")
    else:
        print("FAIL: UID/GID mapping has errors (see above).")


def test_resource_limits():
    """
    Verifies all four resource caps are correctly translated from SandboxConfig
    into the matching nsjail flag values, including the MB→byte conversion for
    cgroup_mem_max.
    """
    config = SandboxConfig(
        rsrc_max_file_size_mb = 5,
        rsrc_max_memory_mb    = 256,
        rsrc_max_pids         = 16,
        rsrc_max_cpu_time_sec = 30,
        fs_forbidden_apps     = [],
    )
    args = _get_sandbox(config)._build_cmd(["echo"])

    expected = [
        ("--rlimit_fsize",    "5",                    "file size cap (MB)"),
        ("--cgroup_mem_max",  str(256 * 1024 * 1024), "memory cap (bytes = MB * 1024²)"),
        ("--cgroup_pids_max", "16",                   "pid cap"),
        ("--time_limit",      "30",                   "cpu time cap (sec)"),
    ]

    ok = True
    for flag, expected_val, label in expected:
        actual = _arg_after(args, flag)
        result = (actual == expected_val)
        print(f"  {'OK  ' if result else 'FAIL'}: {flag} = {actual!r} "
              f"(expected {expected_val!r})  [{label}]")
        ok = ok and result

    if ok:
        print("SUCCESS: Resource limits correctly translated.")
    else:
        print("FAIL: Resource limit translation has errors (see above).")


def test_network_host():
    """
    ntw_share_host_network=True  → --disable_clone_newnet present,
                                    isolation flags (--iface_no_lo) absent.
    ntw_share_host_network=False → --disable_clone_newnet absent,
                                    --iface_no_lo present when loopback disabled.
    """
    base = dict(fs_forbidden_apps=[])

    args_shared   = _get_sandbox(SandboxConfig(ntw_share_host_network=True,
                                               **base))._build_cmd(["echo"])
    args_isolated = _get_sandbox(SandboxConfig(ntw_share_host_network=False,
                                               ntw_disable_loopback=True,
                                               **base))._build_cmd(["echo"])

    net_shared   = [a for a in args_shared   if "net" in a or "iface" in a or "clone" in a]
    net_isolated = [a for a in args_isolated if "net" in a or "iface" in a or "clone" in a]
    print(f"INSPECT: shared-network flags:   {net_shared}")
    print(f"INSPECT: isolated-network flags: {net_isolated}")

    if _check([
        ("--disable_clone_newnet" in     args_shared,
         "--disable_clone_newnet present when sharing host network"),
        ("--iface_no_lo"          not in args_shared,
         "--iface_no_lo absent when sharing host network"),
        ("--disable_clone_newnet" not in args_isolated,
         "--disable_clone_newnet absent in isolated mode"),
        ("--iface_no_lo"          in     args_isolated,
         "--iface_no_lo present when ntw_disable_loopback=True"),
    ]):
        print("SUCCESS: Host-network flag logic is correct.")
    else:
        print("FAIL: Host-network flag logic has errors (see above).")


def test_network_macvlan():
    """
    Full config (iface + IP + GW) → all three macvlan flags with correct values.
    Partial config (iface only)   → IP and GW flags must be absent.
    """
    base = dict(fs_forbidden_apps=[])

    args_full = _get_sandbox(SandboxConfig(
        ntw_macvlan_iface = "eth0",
        ntw_macvlan_ip    = "192.168.1.50",
        ntw_macvlan_gw    = "192.168.1.1",
        **base,
    ))._build_cmd(["echo"])

    args_partial = _get_sandbox(SandboxConfig(
        ntw_macvlan_iface = "eth0",
        **base,
    ))._build_cmd(["echo"])

    macvlan_full    = [a for a in args_full    if "macvlan" in a or a in ("eth0","192.168.1.50","192.168.1.1")]
    macvlan_partial = [a for a in args_partial if "macvlan" in a or a == "eth0"]
    print(f"INSPECT: full-macvlan flags:    {macvlan_full}")
    print(f"INSPECT: partial-macvlan flags: {macvlan_partial}")

    if _check([
        (_arg_after(args_full, "--macvlan_iface") == "eth0",
         "--macvlan_iface = 'eth0'"),
        (_arg_after(args_full, "--macvlan_vs_ip") == "192.168.1.50",
         "--macvlan_vs_ip = '192.168.1.50'"),
        (_arg_after(args_full, "--macvlan_vs_gw") == "192.168.1.1",
         "--macvlan_vs_gw = '192.168.1.1'"),
        ("--macvlan_vs_ip" not in args_partial,
         "--macvlan_vs_ip absent when IP not configured"),
        ("--macvlan_vs_gw" not in args_partial,
         "--macvlan_vs_gw absent when GW not configured"),
    ]):
        print("SUCCESS: MACVLAN flags correctly generated.")
    else:
        print("FAIL: MACVLAN flag generation has errors (see above).")


def test_forbidden_masking():
    """
    A forbidden binary that exists on disk receives a '-R /dev/null:{path}'
    bind-mount entry. A path that does not exist must not appear in args.
    os.path.exists is mocked so the test is host-independent.
    """
    existing = "/usr/bin/curl"
    absent   = "/usr/bin/__nonexistent_binary__"

    config  = SandboxConfig(fs_forbidden_apps=[existing, absent])
    sandbox = _get_sandbox(config)

    exists_map = {existing: True, absent: False}
    with patch("os.path.exists", side_effect=lambda p: exists_map.get(p, False)):
        args = sandbox._build_cmd(["echo"])

    bind_mounts = _all_values_after(args, "-R")
    print(f"INSPECT: -R bind-mount values: {bind_mounts}")

    if _check([
        (f"/dev/null:{existing}" in     bind_mounts,
         f"existing binary '{existing}' is masked with /dev/null"),
        (f"/dev/null:{absent}"   not in bind_mounts,
         f"absent binary '{absent}' is not added to args"),
    ]):
        print("SUCCESS: Forbidden binary masking is correct.")
    else:
        print("FAIL: Forbidden binary masking has errors (see above).")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    choice_map = {
        "cmd_structure":     test_cmd_structure,
        "uid_gid_mapping":   test_uid_gid_mapping,
        "resource_limits":   test_resource_limits,
        "network_host":      test_network_host,
        "network_macvlan":   test_network_macvlan,
        "forbidden_masking": test_forbidden_masking,
    }

    runner = HwutRunner(
        argv=sys.argv,
        title="SandboxLinux._build_cmd via factory",
        choice_map=choice_map,
        happy="SUCCESS.*"
    )
    runner.run()
