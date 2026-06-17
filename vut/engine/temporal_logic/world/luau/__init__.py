"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

LUAU WORLD  --  the reference implementation of the three world faces.

Implements the world contract (../__init__.py) for Roblox's Luau:

    span        LuauOracle    BUILT   (luau_span_oracle.py): brace-finding
                                          under a Role frame; reference
                                          collection. Plugged into the lexer.
    emission    LuauEmitter       UNBUILT (todo-4). Its substrate exists --
                                  location_mapper.py (source<->target line map)
                                  and generated_code_checker.py (the INTERNAL
                                  validator: luau-analyze over emitted code,
                                  error attribution). The checker is private to
                                  emission and is NOT re-exported here.
    execution   LuauRunner        UNBUILT (todo-4). Wraps the 'luau' interpreter.

Only the built concrete is re-exported. The emitter and runner appear when the
emitter session lands; the validator never leaves the world (no outward use).
______________________________________________________________________________
"""
from .luau_span_oracle import LuauOracle

__all__ = ["LuauOracle"]
