from setuptools import setup, Extension
from Cython.Build import cythonize
import os
import sys

sys.argv = [sys.argv[0]] + ["build_ext", "--inplace"]

# Define the extension module
# Ensure the path matches your project structure
ext = Extension(
    name="engine.compare.tolerance.line_element",
    sources=["engine/compare/tolerance/line_element.pyx"],
    # Adding compiler directives for maximum performance
    extra_compile_args=["-O3"] if os.name != 'nt' else ["/O2"],
)

setup(
    name="LineElement Extension",
    ext_modules=cythonize(
        [ext],
        compiler_directives={
            'language_level': "3",
            'boundscheck': False,
            'wraparound': False,
            'cdivision': True,
            'initializedcheck': False,
        }
    ),
)
