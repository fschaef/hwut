#!/usr/bin/env python3
"""
PURPOSE: Audit the nsjail sandbox execution, IO handling, and file monitoring.

DESCRIPTION: 
This test suite validates the Sandbox class, specifically focusing on the 
transparency of command-line generation for nsjail, the asynchronous 
streaming of stdin/stdout/stderr, and the file-watching/backup lifecycle. 
It uses mock subprocesses to avoid requiring a literal nsjail installation 
during logic verification.

CHOICES:
  args:       Verify nsjail argument construction, including forbidden binary masking.
  io_stream:  Audit the asynchronous handling of stdin and stdout streams.
  file_watch: Audit the pre-execution backup and post-execution file retrieval.
  stop_event: Verify the external stop_event correctly terminates the process.

AUTHOR: Gemini HWUT-Unit Test Writer
        Frank-Rene Schaefer
"""

import sys
import asyncio
import tempfile
import shutil
import re
from   pathlib import Path
from   unittest.mock import patch, AsyncMock

sys.path.insert(0, "../" * 4)

from   vut.language_support.python.hwut_runner          import HwutRunner            # noqa 
from   vut.language_support.python.deterministic_random import DeterministicStream   # noqa
import vut.engine.sandbox.system_call                   as     system_call                    # noqa


ds = DeterministicStream(seed=0x42)

def print_banner(msg):
    print(f"\n--- {msg} ---")

def print_pretty_cmd(args):
    """Prints a sorted, aligned command line for transparency."""
    print("GENERATED NSJAIL COMMAND:")
    base_exe = args[0]
    
    try:
        sep_idx = args.index("--")
        flags = args[1:sep_idx]
        trailing = args[sep_idx:]
    except ValueError:
        flags = args[1:]
        trailing = []

    print(f"  {base_exe}")
    
    pairs = []
    i = 0
    while i < len(flags):
        if flags[i].startswith("-") and i + 1 < len(flags) and not flags[i+1].startswith("-"):
            pairs.append(f"{flags[i]:<20} {flags[i+1]}")
            i += 2
        else:
            pairs.append(f"{flags[i]}")
            i += 1
            
    for p in sorted(pairs):
        print(f"    {p}")
        
    if trailing:
        print(f"    {' '.join(trailing)}")

async def test_args():
    """Verify nsjail arguments are built correctly."""
    print_banner("Testing Argument Construction")
    forbidden = ["/usr/bin/ssh", "/usr/bin/wget"]
    config = system_call.SandboxConfig(forbidden_binaries=forbidden)
    
    with patch("os.path.exists", side_effect=lambda p: p in forbidden):
        with patch("os.getuid", return_value=1000), patch("os.getgid", return_value=1000):
            sandbox = system_call.Sandbox(config, work_dir="/tmp/work")
            cmd = ["python3", "-c", "print('hello')"]
            args = sandbox._build_nsjail_args(cmd)
            print_pretty_cmd(args)
            if any("/dev/null:/usr/bin/ssh" in a for a in args):
                print("SUCCESS: Masking detected in arguments.")

async def test_io_stream():
    """Audit Async IO streaming."""
    print_banner("Testing Async IO Streaming")
    config = system_call.SandboxConfig()
    sandbox = system_call.Sandbox(config, work_dir="/tmp")
    output_captured = []
    async def mock_stdout_handler(data):
        msg = data.decode().strip()
        print(f"HANDLER-RECEIVE: {msg}")
        output_captured.append(msg)

    mock_proc = AsyncMock()
    mock_proc.stdout.at_eof.side_effect = [False, True]
    mock_proc.stdout.read.return_value = b"Hello Sandbox"
    mock_proc.stderr.at_eof.return_value = True
    mock_proc.stdin = AsyncMock()
    mock_proc.wait.return_value = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        await sandbox.run("echo 'Hello'", mock_stdout_handler, AsyncMock(), [])
        if "Hello Sandbox" in output_captured:
            print("SUCCESS: IO stream handled.")

async def test_file_watch():
    """Audit the file backup logic and prove backup creation/cleanup."""
    print_banner("Testing File Watching and Backup")
    
    test_dir = tempfile.mkdtemp(prefix="hwut_sandbox_")
    try:
        work_path = Path(test_dir)
        target_file = work_path / "result.txt"
        target_file.write_text("backup_this_data")
        
        print(f"INITIAL STATE: {target_file.name} created in temp dir.")
        
        config = system_call.SandboxConfig()
        sandbox = system_call.Sandbox(config, work_dir=test_dir)
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.at_eof.return_value = True
        mock_proc.stderr.at_eof.return_value = True

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            await sandbox.run("noop", AsyncMock(), AsyncMock(), ["result.txt"])

        print("FILESYSTEM PROOF:")
        found_backup = False
        for p in work_path.iterdir():
            print(f"  FILE: {p.name}")
            if re.match(r"result\.txt-\d{8}-\d{6}", p.name):
                found_backup = True
        
        if found_backup:
            print("SUCCESS: Valid timestamped backup generated.")
    
    finally:
        shutil.rmtree(test_dir)
        # Note: The path is masked in the HAPPY pattern to avoid diff issues
        print(f"CLEANUP: Removed temporary directory: {test_dir}")

async def test_stop_event():
    """Verify stop_event termination."""
    print_banner("Testing Stop Event Termination")
    config = system_call.SandboxConfig()
    sandbox = system_call.Sandbox(config, work_dir="/tmp")
    stop_event = asyncio.Event()
    mock_proc = AsyncMock()
    mock_proc.returncode = None
    async def slow_wait():
        await asyncio.sleep(0.2)
        return -1
    mock_proc.wait = slow_wait
    mock_proc.stdout.at_eof.return_value = True
    mock_proc.stderr.at_eof.return_value = True

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        async def trigger():
            await asyncio.sleep(0.05)
            print("ACTION: Setting stop_event.")
            stop_event.set()
        
        asyncio.create_task(trigger())
        await sandbox.run("sleep 10", AsyncMock(), AsyncMock(), [], stop_event=stop_event)
        if mock_proc.terminate.called:
            print("SUCCESS: Termination signal sent.")

if __name__ == "__main__":
    def run_async(func):
        return lambda: asyncio.run(func())

    choice_map = {
        "args":       run_async(test_args),
        "io_stream":  run_async(test_io_stream),
        "file_watch": run_async(test_file_watch),
        "stop_event": run_async(test_stop_event)
    }

    runner = HwutRunner(
        argv       = sys.argv,
        title      = "Sandboxed System Call",
        choice_map = choice_map,
        happy      = [r"  FILE: result\.txt-\d{4}y\d{2}m\d{2}d-\d{2}h\d{2}m\d{2}s\.BACKUP"]
    )
    runner.run()
