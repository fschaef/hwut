"""
NAME
    trace_runner - A selective Python execution tracer with variable inspection.

SYNOPSIS
    python trace_runner.py <script_path> [arguments...]

DESCRIPTION
    trace_runner executes a Python script with active line-by-line tracing.
    It logs execution flow, the actual source code line being run, and
    the current state of local variables.

    Tracing is restricted to specific modules or directories to prevent
    system noise.

CONFIGURATION
    Edit the variables at the top of the script:

    TARGET_MODULES      : List of module name prefixes to trace.
    TARGET_DIRECTORIES  : List of directory paths to trace.
    SHOW_SOURCE_LINE    : Set True to print the code line being executed.
    SHOW_LOCAL_VARS     : Set True to print local variables at every step.
    MAX_VAR_LENGTH      : Truncate long variable string representations.

OUTPUT
    TRACE: <module>:<line> in <func>
      >>> <source_code_line>
      VARS:
        var_name = value

AUTHOR
    Custom Wrapper Logic.
"""

import sys
import os
import linecache

# --- CONFIGURATION ---

# 1. Filter by Module Name
TARGET_MODULES = [
    "vut.engine.compare.main",
    "vut.engine.potpourri"
]

# 2. Filter by Directory
TARGET_DIRECTORIES = [
    # "./src/plugins",
]

# 3. Output Detail Levels
SHOW_SOURCE_LINE = True   # Print the actual code line (e.g., "x = x + 1")
SHOW_LOCAL_VARS  = True   # Print local variables in the current scope
MAX_VAR_LENGTH   = 100    # Truncate variable values longer than this

# --- INITIALIZATION HELPERS ---

ABS_TARGET_DIRS = [os.path.abspath(d) for d in TARGET_DIRECTORIES]

def truncate(obj):
    """Helper to safely format and truncate variable values."""
    try:
        s = repr(obj)
        if len(s) > MAX_VAR_LENGTH:
            return s[:MAX_VAR_LENGTH] + "..."
        return s
    except Exception:
        return "<error repr()>"

def tracer(frame, event, arg):
    """
    The trace function called by sys.settrace.
    """
    if event != 'line':
        return tracer

    should_trace = False

    # 1. Check Module Name
    module_name = frame.f_globals.get("__name__", "")
    if any(module_name.startswith(t) for t in TARGET_MODULES):
        should_trace = True

    # 2. Check Directory (if not already matched)
    if not should_trace and ABS_TARGET_DIRS:
        code = frame.f_code
        filename = code.co_filename
        if filename and not filename.startswith('<'):
            abs_filename = os.path.abspath(filename)
            if any(abs_filename.startswith(d) for d in ABS_TARGET_DIRS):
                should_trace = True

    # 3. Output
    if should_trace:
        lineno = frame.f_lineno
        code = frame.f_code
        func_name = code.co_name
        filename = code.co_filename

        # Header
        print(f"TRACE: {module_name}:{lineno} in {func_name}")

        # OPTIONAL: Show Source Code
        if SHOW_SOURCE_LINE:
            # linecache handles file reading efficiently
            line = linecache.getline(filename, lineno).strip()
            if line:
                print(f"  >>> {line}")

        # OPTIONAL: Show Local Variables
        if SHOW_LOCAL_VARS:
            local_vars = frame.f_locals
            if local_vars:
                print("  VARS:")
                for name, value in local_vars.items():
                    # Filter out some internal python noise if desired
                    if not name.startswith("__"):
                        print(f"    {name} = {truncate(value)}")

        print("-" * 40) # Separator for readability

    return tracer

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    script_path = sys.argv[1]

    # Adjust sys.argv
    sys.argv = sys.argv[1:]

    # Set path
    sys.path.insert(0, os.path.dirname(os.path.abspath(script_path)))

    # Install tracer
    sys.settrace(tracer)

    # Execute
    try:
        with open(script_path) as f:
            code = compile(f.read(), script_path, 'exec')
            exec(code, {'__name__': '__main__', '__file__': script_path})
    except Exception as e:
        sys.settrace(None)
        raise e
