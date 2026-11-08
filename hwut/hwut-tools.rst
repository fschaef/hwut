.. SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer

=============================================================================
THE TOOLS -- what the platforms of 'hwut-root.conf' announce
=============================================================================

Every tool a platform announces (``tools = [...]``) and every tool a conf
``requires`` is explained here, one ``[[name]]`` each (intend/26 o-52). The
file is optional; where it stands it binds: a name it does not explain is
refused at the start. A tool is an informal name for what a subtree needs;
an announcement is a hint, not a complete list.

[[iverilog]]
    Icarus Verilog -- ``iverilog`` and its runtime ``vvp``: the simulator
    under which the remote agent and its prototype are tested
    (support/remote/iverilog).

[[verilator]]
    Verilator, the SystemVerilog simulator and its coverage
    (the Verilog port).

[[ghdl]]
    GHDL, the VHDL simulator: the VHDL port and demo.

[[gcc]]
    The GNU C and C++ compilers with make and libc headers: the C and C++
    ports and demos.

[[gfortran]]
    GNU Fortran: the Fortran port.

[[go]]
    The Go tool chain (``go run``): the Go port.

[[rustc]]
    The Rust compiler: the Rust port.

[[ghc]]
    The Glasgow Haskell Compiler with ``runghc``: the Haskell port.

[[erlang]]
    Erlang/OTP with ``escript``: the Erlang port.

[[guile]]
    GNU Guile 3: the Scheme port.

[[swipl]]
    SWI-Prolog: the Prolog port.

[[java]]
    A Java 21 JDK: the Java port.

[[node]]
    Node.js: the JavaScript port.

[[perl]]
    Perl 5 with FFI::Platypus: the Perl port.

[[pwsh]]
    PowerShell 7: the PowerShell port.

[[gcov]]
    GCC's coverage tool, for 'hwut.coverage' over C, C++ and Fortran.

[[lcov]]
    lcov and gcovr, the coverage report tools beside gcov.
