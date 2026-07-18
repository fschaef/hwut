"""Bootstrap: insert the component directory (parent of TEST/) into sys.path
so that 'import hwut_pype' works from any invocation directory."""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
