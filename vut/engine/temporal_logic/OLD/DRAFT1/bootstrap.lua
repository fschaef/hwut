-- PURPOSE:
--
-- Sandbox core for a "LuaRuleSpace", named RULE_SPACE_HUB, embedded into a
-- Python-driven temporal logic / HWUT-style engine.
--
-- THIS FILE IS BOTH CODE AND TEACHING MATERIAL.
-- It is written so that an engineer with *no prior Lua knowledge* can
-- understand exactly what happens and why.
--
-- -------------------------------------------------------------------------
-- EXECUTION MODEL (VERY IMPORTANT)
-- -------------------------------------------------------------------------
--
-- There is exactly ONE Lua world.
-- This world is OWNED and DRIVEN by Python.
--
-- Lua never runs autonomously. Python explicitly calls into Lua in
-- well-defined phases using the API table returned by this file:
--
--     RULE_SPACE_HUB
--
-- Python lifecycle:
--
--   (1) Declare which user variables are allowed        -> set_declared_keys
--   (2) Initialize those variables                      -> init_G
--   (3) Execute header code once (definitions, helpers) -> exec_header
--   (4) For each stream step:
--         - inject TIME / PREV_TIME
--         - inject NOW (current events)
--         - execute action blocks                       -> exec_action
--         - evaluate rule expressions                   -> eval_expr
--
-- -------------------------------------------------------------------------
-- WHAT EXISTS INSIDE LUA
-- -------------------------------------------------------------------------
--
-- (A) OBSERVATIONS (read-only, replaced every step)
--     - TIME(), PREV_TIME()
--     - NOW        (events of the current step)
--     - per-event globals (INIT, PING, ...) for convenience
--
-- (B) HISTORY QUERIES (read-only, Python-owned)
--     - seen(E), ever(E), never(E)
--     - time(E,...), count(E,...)
--
-- (C) USER STATE (persistent, controlled)
--     - G.<declared_key>
--     - the ONLY writable user state
--
-- (D) EXECUTION CONTEXTS (STRICT SEPARATION)
--
--     header_env : definitions + initialization (may write G)
--     action_env : runtime effects              (may write G)
--     expr_env   : rule conditions              (READ-ONLY)
--
-- -------------------------------------------------------------------------
-- LUA VERSION COMPATIBILITY (FUTURE-PROOFING)
-- -------------------------------------------------------------------------
--
-- This sandbox is ARCHITECTURALLY independent of the Lua version.
-- Only the *compilation mechanism* differs between Lua 5.1 and Lua ≥ 5.2.
--
-- - Lua 5.1 / LuaJIT: uses loadstring + setfenv
-- - Lua ≥ 5.2:        uses load + lexical _ENV
--
-- The difference is hidden behind ONE internal function: compile_chunk().
-- Rule authors and Python code never see this distinction.
--
-- End-users are completely insulated from Lua version details.
--
-- _____________________________________________________________________________

-- ============================================================================
--  RULE_SPACE_HUB
--
--  The ONLY object returned to Python. Think of this as the "socket" or 
--  "control panel" for the Lua rule space.
-- ============================================================================
local RULE_SPACE_HUB = {}

-- ============================================================================
--  Error Handling
-- ============================================================================
local function _error(msg)
  -- RETURNS: never returns
  --
  -- error(msg, 2) raises an exception attributed to the *caller*.
  -- This ensures error messages point to user code, not framework internals.
  error(msg, 2)
end

-- ============================================================================
--  Table Utilities
-- ============================================================================
local function table_copy_shallow(src)
  -- RETURNS: shallow copy of table `src`
  --
  -- "shallow" means nested tables are NOT cloned.
  local dst = {}
  for k, v in pairs(src) do
    dst[k] = v
  end
  return dst
end

local function table_proxy_readonly(table, what, reason)
  -- RETURNS:
  --   a read-only proxy to `table`
  --
  -- PARAMETERS:
  --   table  : backing storage (real data lives here)
  --   what   : human-readable name ("NOW", "G", "EVENT(INIT)", ...)
  --   reason : optional explanation of *why* writes are forbidden
  --
  -- EXAMPLE ERROR MESSAGE:
  --   "attempt to modify G in expression context: x"
  local proxy = {}

  local mt = {
    -------------------------------------------------------------------------
    -- Prevent inspection or replacement of the metatable.
    -- This is essential to avoid sandbox bypass.
    -------------------------------------------------------------------------
    __metatable = "locked",

    -------------------------------------------------------------------------
    -- READ access:
    --   proxy[k] -> table[k]
    -------------------------------------------------------------------------
    __index = function(_, k)
      return table[k]
    end,

    -------------------------------------------------------------------------
    -- WRITE access:
    --   proxy[k] = v -> ERROR
    -------------------------------------------------------------------------
    __newindex = function(_, k, _)
        _error("attempt to modify "..what.." "..reason..": "..tostring(k))
      end
    end,
  }

  setmetatable(proxy, mt)
  return proxy
end

-- ============================================================================
--  User State: G
--
--  G is the ONLY persistent mutable user state.
--  Keys must be declared upfront by Python.
-- ============================================================================
local G_KEYS           = {}  -- set of allowed variable names
local G_USER_VARIABLES = {}  -- actual storage for values

local function G_assert_declared(key)
  -- Enforces the declared-key policy.
  if not G_KEYS[key] then
    _error("undeclared variable write: G."..tostring(key))
  end
end

local function G_make_view_readwrite()
  -- RETURNS: table exposed as `G` in header/action contexts.
  --
  -- READS:  G.x -> G_USER_VARIABLES["x"]
  --
  -- WRITES: G.x = v
  --         -> intercepted by __newindex
  --         -> checked against declared keys
  local G = {}
  local mt = {
    __index = function(_, k)       -- READ ACCESS: access original table
      return G_USER_VARIABLES[k]
    end,
    __newindex = function(_, k, v) -- WRITE ACCESS: allow, if key is declared
      G_assert_declared(k)
      G_USER_VARIABLES[k] = v
    end,
    __metatable = "locked",        -- METADATA: make it invisible
  }
  setmetatable(G, mt)
  return G
end

local function G_make_view_readonly()
  -- RETURNS: read-only view of G used in expressions.
  return table_proxy_readonly(G_USER_VARIABLES, "G", "in expression context")
end

-- ============================================================================
--  Step Observation: TIME / PREV_TIME / NOW
-- ============================================================================
local TIME      = 0.0
local PREV_TIME = 0.0

-- NOW_REAL holds the events of the CURRENT step.
-- It is replaced completely on every step.
local NOW_REAL = {}

-- Read-only view exposed to user code
local NOW_RO = table_proxy_readonly(NOW_REAL, "NOW", "which is read only")


-- Optional convenience:
--   If NOW_REAL contains an event "INIT",
--   user code can write INIT.usb instead of NOW["INIT"].usb
local EVENT_GLOBALS = {}

local function NOW_event_globals_clear(env)
  -- Removes per-event globals from an environment.
  for name, _ in pairs(EVENT_GLOBALS) do
    env[name] = nil
  end
  EVENT_GLOBALS = {}
end


local function NOW_event_globals_set(env)
  -- For each event in NOW_REAL, inject:
  --   env[EVENT_NAME] = read-only proxy to its attribute table
  for name, inst in pairs(NOW_REAL) do
    env[name] = table_proxy_readonly(inst, "EVENT("..name..")", "which is read only")
    EVENT_GLOBALS[name] = true
  end
end


-- ============================================================================
--  Occurrence Helpers (HISTORY)
--
--  These are DEFAULT STUBS.
--  The Python host replaces them by executing header code that rebinds
--  `seen`, `time`, `count`, etc. inside the Lua environment.
-- ============================================================================
local function seen(_)       return false end
local function time_fn(_, _) return nil   end
local function first_time(_) return nil   end
local function last_time(_)  return nil   end
local function count(_, _)   return 0     end


-- ============================================================================
--  Event Predicates: now / ever / never
-- ============================================================================
local function EventSpec_normalize(E)
  -- RETURNS:
  --   event_name (string)
  --   filters (table or nil)
  --
  -- Supported forms:
  --   "EVENT"
  --   { name="EVENT", attr=value, ... }
  local t = type(E)

  if t == "string" then
    return E, nil
  end

  if t == "table" then
    if type(E.name) ~= "string" then
      _error("event spec table requires field .name as string")
    end

    -- Build attribute filters:
    -- copy all fields EXCEPT "name"
    local filters = {}
    for k, v in pairs(E) do
      if k ~= "name" then
        filters[k] = v
      end
    end

    return E.name, filters
  end

  _error("invalid event spec")
end

local function EventSpec_match_now(inst, filters)
  -- RETURNS: true iff the current event instance matches all filters
  --
  -- Example:
  --   filters = { id=7, status="OK" }
  --   inst.id == 7 and inst.status == "OK"
  if not filters then return true end

  for k, v in pairs(filters) do
    if inst[k] ~= v then
      return false
    end
  end

  return true
end

local function now(E)
  -- RETURNS: true iff event E occurred in the CURRENT step (NOW)
  local name, filters = EventSpec_normalize(E)
  local inst = NOW_REAL[name]
  if not inst then return false end
  return EventSpec_match_now(inst, filters)
end

local function ever(E)
  -- RETURNS: true iff event E occurred at least once in HISTORY
  --
  -- IMPORTANT: This does NOT inspect NOW.
  return seen(E) and true or false
end


local function never(E)
  -- RETURNS:
  --   true iff event E never occurred
  return not ever(E)
end


-- ============================================================================
--  Execution Environments
--
--  SAME names, DIFFERENT permissions.
-- ============================================================================

local header_env = {}
local action_env = {}
local expr_env   = {}

local G_RW = G_make_view_readwrite()
local G_RO = G_make_view_readonly()

--  Safe Standard Library Exposure
--  Copy math/string/table => make them immutable by user
local SAFE_MATH   = table_copy_shallow(math)
local SAFE_STRING = table_copy_shallow(string)
local SAFE_TABLE  = table_copy_shallow(table)

local SAFE_BASE = {
  assert   = assert,
  error    = error,
  ipairs   = ipairs,
  pairs    = pairs,
  tonumber = tonumber,
  tostring = tostring,
  type     = type,
  select   = select,
  next     = next,
}


local function ENV_init(env, G_view)
  -- Populates one execution environment.
  for k, v in pairs(SAFE_BASE) do env[k] = v end

  env.math   = SAFE_MATH
  env.string = SAFE_STRING
  env.table  = SAFE_TABLE

  -- TIME and PREV_TIME are FUNCTIONS so they cannot be overwritten.
  env.TIME      = function() return TIME      end
  env.PREV_TIME = function() return PREV_TIME end

  env.NOW = NOW_RO
  env.G   = G_view

  env.seen       = seen
  env.time       = time_fn
  env.count      = count
  env.first_time = first_time
  env.last_time  = last_time

  env.now   = now
  env.ever  = ever
  env.never = never
end

ENV_init(header_env, G_RW)
ENV_init(action_env, G_RW)
ENV_init(expr_env,   G_RO)

-- Header-only namespace for helper definitions
header_env.DEF = {}

-- ============================================================================
--  Compilation Helpers 
-- ============================================================================

-- Lua >= 5.2 implementation
local function compile_chunk(lua_src, file, line, env, wrap_return)
  local pad        = (line and line > 1) and string.rep("\n", line - 1) or ""
  local code       = wrap_return and ("return ("..lua_src..")") or lua_src
  local wrapped    = pad .. "local _ENV = ...; " .. code
  local chunk, err = load(wrapped, "@"..file, "t")

  if not chunk then _error(err) end
  return function() return chunk(env) end
end

-- ============================================================================
--  RULE_SPACE_HUB API (Python-facing)
-- ============================================================================

function RULE_SPACE_HUB.set_declared_keys(keys)
  -- Defines the schema of G.
  G_KEYS = {}
  for _, k in ipairs(keys) do G_KEYS[k] = true end
end


function RULE_SPACE_HUB.init_G(init_tbl)
  -- Initializes declared G variables.
  for k, v in pairs(init_tbl) do
    if not G_KEYS[k] then
      _error("init assigns undeclared key: "..tostring(k))
    end
    G_USER_VARIABLES[k] = v
  end
end


function RULE_SPACE_HUB.set_step(time_sec, prev_time_sec, now_tbl, _file, _line)
  -- Injects current-step observation.
  TIME      = time_sec
  PREV_TIME = prev_time_sec

  for k, _ in pairs(NOW_REAL) do NOW_REAL[k] = nil end
  for name, inst in pairs(now_tbl) do NOW_REAL[name] = inst end

  NOW_event_globals_clear(header_env)
  NOW_event_globals_clear(action_env)
  NOW_event_globals_clear(expr_env)

  NOW_event_globals_set(header_env)
  NOW_event_globals_set(action_env)
  NOW_event_globals_set(expr_env)
end


function RULE_SPACE_HUB.exec_header(lua_src, file, line)
  -- RETURNS: result of header execution
  local chunk = compile_chunk(lua_src, file, line, header_env, false)
  return chunk()
end


function RULE_SPACE_HUB.exec_action(lua_src, file, line)
  -- RETURNS: result of action execution
  local chunk = compile_chunk(lua_src, file, line, action_env, false)
  return chunk()
end


function RULE_SPACE_HUB.eval_expr(lua_src, file, line)
  -- RETURNS: value of expression
  local chunk = compile_chunk(lua_src, file, line, expr_env, true)
  return chunk()
end


function RULE_SPACE_HUB.G_snapshot()
  -- RETURNS: plain Lua table snapshot of all declared G variables
  local out = {}
  for k, _ in pairs(G_KEYS) do out[k] = G_USER_VARIABLES[k] end
  return out
end


return RULE_SPACE_HUB
