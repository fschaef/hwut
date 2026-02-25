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
import os
import sys
import asyncio
from   unittest.mock import patch, AsyncMock

sys.path.insert(0, "../" * 4)

from   vut.language_support.python.hwut_runner          import (HwutRunner,        # noqa 
                                                                ScriptApplication)
from   vut.language_support.python.deterministic_random import DeterministicStream # noqa
import vut.engine.sandbox.system_call                   as     system_call         # noqa


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
    print_banner("Testing Async IO Streaming with behavioral script")
    
    script_lines = [
        'echo "Hello stdout!"',
        'echo "Bonjour stderr!" >&2',
        'read -r line',
        'echo "received -- $line --"',
    ]
    
    with ScriptApplication(None, "/bin/bash", script_lines) as script_path:
        config = system_call.SandboxConfig()
        # Ensure the sandbox work_dir matches the temp file location
        sandbox = system_call.Sandbox(config, work_dir=os.path.dirname(script_path))

        async def stdout_handler(data):
            for line in data.decode().splitlines():
                print(f"STDOUT: {line.strip()}")

        async def stderr_handler(data):
            for line in data.decode().splitlines():
                print(f"STDERR: {line.strip()}")

        # Provide trigger input
        stdin_reader = asyncio.StreamReader()
        stdin_reader.feed_data(b"Hello Application; This is sent by you through 'stdin'.")
        stdin_reader.feed_eof()

        # script_path is absolute, which works with nsjail -R /
        await sandbox.run(command_line   = script_path,
                          stdout_handler = stdout_handler,
                          stderr_handler = stderr_handler,
                          watch_files    = [],
                          stdin_reader   = stdin_reader)

async def test_file_size_limit():
    """Verify that the process is terminated if it writes too much data."""
    print_banner("Testing File Size Watchdog")
    
    # Try to write 11MB to a file named 'bloat.txt'
    # using 'dd'. 11 * 1024 * 1024 = 11534336 bytes.
    script_lines = [
        'echo "APP: Attempting to write 11MB file..."',
        'dd if=/dev/zero of=bloat.txt bs=1M count=11 2>&1',
        'echo "APP: Write finished successfully (This should not be seen)"'
    ]
    
    with ScriptApplication(None, "/bin/bash", script_lines) as script_path:
        # We set the limit to 10MB
        config = system_call.SandboxConfig(max_file_size_mb=10)
        sandbox = system_call.Sandbox(config, work_dir="/tmp")

        async def stdout_handler(data):
            for line in data.decode().splitlines():
                print(f"STDOUT: {line.strip()}")

        print("ACTION: Running application with 10MB limit...")
        exit_code = await sandbox.run(command_line   = script_path,
                                      stdout_handler = stdout_handler,
                                      stderr_handler = AsyncMock(), 
                                      watch_files    = [])
        
        # Note: Exit code for SIGXFSZ is often 153 (128 + 25) or 
        # nsjail might return its own failure code.
        if exit_code != 0:
            print("SUCCESS: Process was termination by FORCE!")

async def test_stop_event():
    """Verify stop_event termination via signal trapping in the script."""
    print_banner("Testing Stop Event Termination (Behavioral)")
    
    script_lines = [
        'trap "echo \'RECEIVED SIGTERM\'; exit 0" SIGTERM',
        'echo "APP: Started and waiting..."',
        'while true; do sleep 0.1; done'
    ]
    
    with ScriptApplication(None, "/bin/bash", script_lines) as script_path:
        config = system_call.SandboxConfig()
        sandbox = system_call.Sandbox(config, work_dir="/tmp")
        stop_event = asyncio.Event()

        async def stdout_handler(data):
            for line in data.decode().splitlines():
                print(f"STDOUT: {line.strip()}")

        # We do NOT use patch here. We run the real script.
        async def trigger():
            await asyncio.sleep(0.5) # Give the app time to start
            print("ACTION: Setting stop_event.")
            stop_event.set()

        asyncio.create_task(trigger())
        
        print("ACTION: Running sandboxed application ... until 'TERMINATION' trigger")
        exit_code = await sandbox.run(command_line   = script_path,
                                      stdout_handler = stdout_handler,
                                      stderr_handler = AsyncMock(),
                                      watch_files    = [],
                                      stop_event     = stop_event)

        print(f"EXIT CODE: {exit_code}")

if __name__ == "__main__":
    def run_async(func):
        return lambda: asyncio.run(func())

    choice_map = {
        "args":       run_async(test_args),
        "io_stream":  run_async(test_io_stream),
        "file_size":  run_async(test_file_size_limit),
        "stop_event": run_async(test_stop_event)
    }

    runner = HwutRunner(
        argv       = sys.argv,
        title      = "Sandboxed System Call",
        choice_map = choice_map,
        happy      = [
            r"result\.txt-\d{4}y\d{2}m\d{2}d-\d{2}h\d{2}m\d{2}s\.BACKUP"
        ]
    )
    runner.run()
