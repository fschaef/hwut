#!/usr/bin/env python3
# PURPOSE:
#
#   Minimal Lua RULE SPACE host, ready to interact with.
#
#   - One persistent Lua VM
#   - Two execution environments:
#       * expr_env   (read-only: cannot write G, cannot define functions)
#       * action_env (can write declared keys in G; can call header helpers)
#   - NOW/TIME/PREV_TIME injected by host
#   - Header section for definitions (helpers, types) + vars declaration
#
# REQUIREMENT:
#   pip install lupa
#
# AUTHOR:
#   (generated skeleton)
# _____________________________________________________________________________

from __future__ import annotations

from dataclasses import dataclass
from typing      import Any, Dict



@dataclass(frozen=True)
class Span:
    file: str
    line: int

    @property
    def chunkname(self) -> str:
        return f"@{self.file}"


class LuaRuleSpace:
    def __init__(self):
        try:
            from lupa import LuaRuntime  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "Missing dependency 'lupa'. Install via: pip install lupa"
            ) from e

        self._lua         = LuaRuntime(unpack_returned_tuples=True)
        self._rs          = None
        self._header_done = False

        # Persistent core tables (engine-owned)
        self._G_keys: set[str] = set()
        self._G_init: Dict[str, Any] = {}

        self._bootstrap()

    def declare_vars(self, mapping: Dict[str, Any]):
        """Declare upfront variables for G (schema + initial values)."""
        if self._header_done:
            raise RuntimeError("vars must be declared before header is finalized.")
        for k in mapping.keys():
            if not isinstance(k, str):
                raise TypeError(f"G key must be str, got {type(k)}")
        self._G_keys |= set(mapping.keys())
        self._G_init.update(mapping)

    def load_header(self, lua_source: str, span: Span):
        """Execute header Lua code (definitions, initialization of declared G keys)."""
        if self._header_done:
            raise RuntimeError("Header already loaded/finalized.")
        if self._rs is None:
            raise RuntimeError("Bootstrap not initialized.")

        self._rs["set_declared_keys"](list(sorted(self._G_keys)))
        self._rs["init_G"](self._G_init)

        self._exec_chunk(
            lua_source = lua_source,
            span       = span,
            env_name   = "header",
        )
        self._header_done = True

    def set_step(self, *, time_sec: float, prev_time_sec: float, now_events: Dict[str, Dict[str, Any]], span: Span):
        """Inject TIME/PREV_TIME/NOW + event globals for current step."""
        if self._rs is None:
            raise RuntimeError("Bootstrap not initialized.")
        if not self._header_done:
            raise RuntimeError("Header not loaded yet.")

        # Build NOW table: NOW[name] = { time=TIME, <attrs...> }
        now_tbl = self._lua.table()
        for name, attrs in now_events.items():
            if not isinstance(name, str):
                raise TypeError("Event name must be str.")
            inst = self._lua.table()
            inst["time"] = float(time_sec)
            inst["name"] = name
            if attrs:
                for k, v in attrs.items():
                    inst[k] = v
            now_tbl[name] = inst

        self._rs["set_step"](float(time_sec), float(prev_time_sec), now_tbl, span.file, int(span.line))

    def eval_expr(self, lua_expr: str, span: Span) -> Any:
        """Evaluate a read-only expression, returns its value."""
        if self._rs is None:
            raise RuntimeError("Bootstrap not initialized.")
        if not self._header_done:
            raise RuntimeError("Header not loaded yet.")

        # Expressions are compiled as: return (<expr>)
        return self._eval_chunk(
            lua_source = lua_expr,
            span       = span,
            env_name   = "expr",
            wrap_as_return=True,
        )

    def run_actions(self, lua_block: str, span: Span):
        """Execute action statements (read+write allowed, but only to declared G keys)."""
        if self._rs is None:
            raise RuntimeError("Bootstrap not initialized.")
        if not self._header_done:
            raise RuntimeError("Header not loaded yet.")
        self._exec_chunk(
            lua_source = lua_block,
            span       = span,
            env_name   = "action",
        )

    def get_G_snapshot(self) -> Dict[str, Any]:
        if self._rs is None:
            raise RuntimeError("Bootstrap not initialized.")
        return dict(self._rs["G_snapshot"]())

    # -------------------------------------------------------------------------
    # internals
    # -------------------------------------------------------------------------
    def _bootstrap(self):
        bootstrap_lua = r'''
'''
        self._rs = self._lua.execute(bootstrap_lua)

    def _exec_chunk(self, *, lua_source: str, span: Span, env_name: str):
        if self._rs is None:
            raise RuntimeError("Bootstrap not initialized.")
        if env_name == "header":
            return self._rs["exec_header"](lua_source, span.file, int(span.line))
        if env_name == "action":
            return self._rs["exec_action"](lua_source, span.file, int(span.line))
        raise ValueError(f"invalid env_name: {env_name}")

    def _eval_chunk(self, *, lua_source: str, span: Span, env_name: str, wrap_as_return: bool):
        if self._rs is None:
            raise RuntimeError("Bootstrap not initialized.")
        if env_name != "expr":
            raise ValueError("eval only supported for expr env")
        return self._rs["eval_expr"](lua_source, span.file, int(span.line))


# -----------------------------------------------------------------------------
# Minimal interactive demo
# -----------------------------------------------------------------------------
def _demo():
    rs = LuaRuleSpace()

    rs.declare_vars({
        "x": 0,
        "mode": "INIT",
        "ok": True,
    })

    header = r'''
-- header definitions
DEF.is_even = function(n) return (n % 2) == 0 end

-- init (allowed: assign declared G keys only)
G.x    = 41
G.mode = "RUN"
'''
    rs.load_header(header, Span("rules.txt", 1))

    # Inject a NOW step (event + attrs)
    rs.set_step(
        time_sec      = 0.815,
        prev_time_sec = 0.000,
        now_events    = {
            "INIT": {"usb": False, "screen": "Monitor"},
            "PING": {"id": 7},
        },
        span=Span("stream.txt", 12),
    )

    # Evaluate read-only expression
    v = rs.eval_expr('INIT.usb == false and G.mode == "RUN" and DEF.is_even(PING.id + 1)', Span("rules.txt", 50))
    print("expr =>", v)

    # Run an action (may write G)
    rs.run_actions('G.x = G.x + 1', Span("rules.txt", 60))
    print("G =>", rs.get_G_snapshot())

    # Try forbidden writes in expression (must error)
    try:
        rs.eval_expr('G.x = 123', Span("rules.txt", 70))
    except Exception as e:
        print("expr error =>", e)

    # Try undeclared write (must error)
    try:
        rs.run_actions('G.unknown = 1', Span("rules.txt", 80))
    except Exception as e:
        print("action error =>", e)


if __name__ == "__main__":
    _demo()
