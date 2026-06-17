--[[ SPDX-License: MIT; Reactive Rule Engine -- generated-engine bootstrap.

PURPOSE: Engine-provided runtime substrate the transpiler emits code against.

Defines, exactly once, the machinery shared by the three transpiler-generated
typed constructs -- Events, Modes, State Machines -- so a generated class need
only declare what is unique to its kind. The layers of shared machinery:

    1. _match + comparator classes  -- the one value-comparison core.
    2. Queryable                    -- the eight-method query interface.
    3. Space + EventBase            -- the runtime context boundary: owns the
                                       Tracer and is the factory for event
                                       classes, each derived from EventBase and
                                       bound to that Space.
    4. ModeBase / StateMachineBase  -- the lifecycle (until-list, init/deinit).

Every per-kind event class derives from EventBase (hence from Queryable): its
membership is the flat history ring its Space's Tracer retains for that kind.
An event still has no init/deinit -- EventBase adds identity, intrinsic
time/dt, the 'signal' emission surface, and the query surface over history.
]]

local bootstrap = {}

-- ===========================================================================
-- (1) COMPARISON CORE -- _match and the comparator value classes
-- ===========================================================================

--[[ RETURN: boolean, the result of comparing 'actual' against 'expected'.

Routes the comparison: when 'expected' is a comparator value object (carries
'__className' and ':match'), delegates to 'expected:match(actual)'; otherwise
falls back to Luau equality 'actual == expected'. This is the single dispatch
point every query method and the transpiler emit against -- the author writes
the comparator, the engine writes the dispatch.
]]
local function _match(actual, expected)
    local mt = getmetatable(expected)
    if mt ~= nil and mt.__className ~= nil and type(expected.match) == "function" then
        return expected:match(actual)
    end
    return actual == expected
end
bootstrap._match = _match

--[[ RETURN: comparator class, a value class whose instances answer ':match'.

Builds one comparator class from a class name and a match predicate. Every
comparator instance carries '__className' on its metatable (so _match can
recognise it) and a ':match(actual)' method (so _match, or a free guard, can
invoke it). Constructing the class returns a callable: 'Glob("a*")' yields an
instance whose ':match' applies the predicate against its captured arguments.
]]
local function _comparator(class_name, match_fn)
    local cls = {}
    cls.__index = cls
    cls.__className = class_name
    function cls:match(actual)
        return match_fn(self, actual)
    end
    return setmetatable(cls, {
        __call = function(_, ...)
            return setmetatable({ args = { ... } }, cls)
        end,
    })
end

--[[ RETURN: string, a Luau string pattern equivalent to the glob 'g'.

Translates Unix glob metacharacters ('*', '?', '[...]') into the Luau native
pattern dialect and anchors the result so the whole string must match. Literal
characters that are Luau pattern magic are escaped.
]]
local function _glob_to_pattern(g)
    local out = { "^" }
    local i, n = 1, #g
    while i <= n do
        local c = g:sub(i, i)
        if c == "*" then
            out[#out + 1] = ".*"
        elseif c == "?" then
            out[#out + 1] = "."
        elseif c == "[" then
            local j = i + 1
            if g:sub(j, j) == "!" then j = j + 1 end       -- '[!..]' negation
            if g:sub(j, j) == "]" then j = j + 1 end        -- ']' as first member
            while j <= n and g:sub(j, j) ~= "]" do j = j + 1 end
            local set = g:sub(i + 1, j - 1):gsub("^!", "^")
            out[#out + 1] = "[" .. set .. "]"
            i = j
        elseif c:match("[%^%$%(%)%%%.%[%]%+%-]") then
            out[#out + 1] = "%" .. c
        else
            out[#out + 1] = c
        end
        i = i + 1
    end
    out[#out + 1] = "$"
    return table.concat(out)
end

bootstrap.Glob      = _comparator("Glob",      function(self, a) return string.match(tostring(a), _glob_to_pattern(self.args[1])) ~= nil end)
bootstrap.Pattern   = _comparator("Pattern",   function(self, a) return string.match(tostring(a), self.args[1]) ~= nil end)
bootstrap.Approx    = _comparator("Approx",    function(self, a) return math.abs(a - self.args[1]) < self.args[2] end)
bootstrap.Less      = _comparator("Less",      function(self, a) return a <  self.args[1] end)
bootstrap.LessEq    = _comparator("LessEq",    function(self, a) return a <= self.args[1] end)
bootstrap.Greater   = _comparator("Greater",   function(self, a) return a >  self.args[1] end)
bootstrap.GreaterEq = _comparator("GreaterEq", function(self, a) return a >= self.args[1] end)
bootstrap.Eq        = _comparator("Eq",        function(self, a) return a == self.args[1] end)
bootstrap.UnEq      = _comparator("UnEq",      function(self, a) return a ~= self.args[1] end)

-- ===========================================================================
-- (2) QUERYABLE -- the eight-method query interface, defined once
-- ===========================================================================

local Queryable = {}
Queryable.__index = Queryable
bootstrap.Queryable = Queryable

--[[ RETURN: array, every instance in the collection (insertion order).

Concrete contract a subclass MUST override: yields the current membership the
eight query methods operate on -- live mode instances for a mode registry, or
the retained event history for a tracer key. The base raises, since a bare
Queryable has no membership of its own.
]]
function Queryable:_instances()
    error("Queryable:_instances must be overridden by the concrete collection")
end

--[[ RETURN: True,  the instance satisfies every (member = expected) condition.
            False, else

Tests one instance against a conditions table, routing each field through
_match so a condition value may be a literal or a comparator object.
]]
local function _instance_matches(inst, conditions)
    for member, expected in pairs(conditions) do
        if not _match(inst[member], expected) then
            return false
        end
    end
    return true
end

--[[ RETURN: array, the instances satisfying every condition in 'conditions'.

With an empty or absent 'conditions' table, every instance in the collection
is returned.
]]
function Queryable:list(conditions)
    conditions = conditions or {}
    local out = {}
    for _, inst in ipairs(self:_instances()) do
        if _instance_matches(inst, conditions) then
            out[#out + 1] = inst
        end
    end
    return out
end

--[[ RETURN: True,  at least one instance satisfies 'conditions'.
            False, else

Conditions are required; identical in effect to ':any' with conditions, kept as
the intent-revealing name for existence-with-condition queries.
]]
function Queryable:has(conditions)
    return self:any(conditions)
end

--[[ RETURN: True,  at least one instance matches 'conditions'.
            False, else

With no conditions, true if the collection is non-empty. Chosen over a bare
collection-as-boolean test because Luau treats an empty table as truthy.
]]
function Queryable:any(conditions)
    conditions = conditions or {}
    for _, inst in ipairs(self:_instances()) do
        if _instance_matches(inst, conditions) then
            return true
        end
    end
    return false
end

--[[ RETURN: True,  every instance matches 'conditions' (vacuously true if none).
            False, else

Conditions are required; a conditionless ':all' would be vacuous and is not a
meaningful query.
]]
function Queryable:all(conditions)
    for _, inst in ipairs(self:_instances()) do
        if not _instance_matches(inst, conditions) then
            return false
        end
    end
    return true
end

--[[ RETURN: True,  no instance matches 'conditions'.
            False, else

Conditions are required; for the conditionless case use ':empty'.
]]
function Queryable:none(conditions)
    return not self:any(conditions)
end

--[[ RETURN: True,  the collection holds no instance at all.
            False, else

Takes no conditions; the conditionless complement of ':any'.
]]
function Queryable:empty()
    return #self:_instances() == 0
end

--[[ RETURN: instance | nil, the most recently added instance matching 'conditions'.

Scans the collection from newest to oldest and returns the first match, or nil
when none matches. Newest is the last element of the '_instances' array.
]]
function Queryable:last(conditions)
    conditions = conditions or {}
    local insts = self:_instances()
    for i = #insts, 1, -1 do
        if _instance_matches(insts[i], conditions) then
            return insts[i]
        end
    end
    return nil
end

--[[ RETURN: number, the timeline moment of one instance in this collection.

The reference instant ':since' measures from. The default is an instance's
'begin_time' (modes). A collection whose instances have no 'begin_time' -- an
event history -- overrides this to return 'time'.
]]
function Queryable:_moment(inst)
    return inst.begin_time
end

--[[ RETURN: number | nil, 'now' minus the moment of the most recent match.

Returns the elapsed time since the most recent matching instance, measured from
its ':_moment' ('begin_time' for modes, 'time' for events), or nil when no
instance matches. 'now' is the engine's current instant.
]]
function Queryable:since(now, conditions)
    local m = self:last(conditions)
    if m == nil then return nil end
    return now - self:_moment(m)
end

-- ===========================================================================
-- (3a) SPACE + EVENT BASE -- runtime context boundary and the shared event base
-- ===========================================================================

local Space = {}
Space.__index = Space
bootstrap.Space = Space

--[[ RETURN: space, a fresh runtime context owning its own Tracer.

The Space is the boundary that owns runtime state: each Space instantiates its
own Tracer at construction, and every event class it produces is bound to that
Space. Two Spaces never share history; an event class queries only the Tracer
of the Space that built it.
]]
function Space.new()
    return setmetatable({ tracer = bootstrap.Tracer.new() }, Space)
end

-- EventBase: the one base every per-kind event class derives from. It carries
-- the shared identity wiring, the intrinsic-field stamping, and the signalling
-- surface; it inherits Queryable so every event type answers the eight query
-- methods. A per-kind class adds only its '__className' and its '_instances'.
local EventBase = setmetatable({}, Queryable)
EventBase.__index = EventBase
bootstrap.EventBase = EventBase

--[[ RETURN: array, the traced occurrences of this event kind (flat ring).

The Queryable membership contract for events. The base resolves the kind's flat
history ring from its bound Space's Tracer, keyed by the class's own
'__className'; an unwatched kind has no ring and yields an empty array. A
per-kind class inherits this unchanged -- it need not re-implement it.
]]
function EventBase:_instances()
    local space = self._space
    local watched = space and space.tracer._watched[self.__className]
    return (watched and watched._ring) or {}
end

--[[ RETURN: number, the event's 'time' -- its timeline moment for ':since'. ]]
function EventBase:_moment(inst)
    return inst.time
end

--[[ RETURN: event class, a Queryable event type derived from EventBase, bound to this Space.

Builds the per-kind event class. It derives from EventBase (hence from
Queryable), so identity stamping, the '_instances' history lookup, the
signalling surface, and the eight query methods are all inherited. The class
carries '__className' for the static checks and 'getmetatable', and '_space'
binding it to this Space. Events have no 'init'/'deinit' -- they are ephemeral
and non-reactive; the base adds only identity, intrinsic fields, signalling, and
the query surface over traced history.
]]
function Space:new_event_class(name)
    local cls = setmetatable({}, EventBase)
    cls.__index = cls
    cls.__className = name
    cls._space = self                          -- bind to this runtime context

    --[[ RETURN: event instance, a new occurrence carrying 'fields' plus time/dt.

    'fields' supplies the declared members; 'time' and 'dt' are stamped by the
    engine at emission and overwrite any author-supplied value. The instance's
    metatable is the per-kind class, so it answers the inherited query methods.
    ]]
    function cls.new(fields, time, dt)
        local self = setmetatable(fields or {}, cls)
        self.time = time
        self.dt = dt
        return self
    end

    --[[ RETURN: event instance, the freshly signalled occurrence.

    Stamps a new occurrence with 'time'/'dt' and signals it into the bound
    Space's Tracer (a no-op on the history when the kind is unwatched). The
    single emission surface every event kind shares; returns the instance so a
    caller may inspect it.
    ]]
    function cls.signal(fields, time, dt)
        local ev = cls.new(fields, time, dt)
        cls._space.tracer:record(ev)
        return ev
    end

    return cls
end

-- ===========================================================================
-- (3b) MODE BASE -- lifecycle (identity, until-list, init/deinit) + registry
-- ===========================================================================

--[[ RETURN: mode class, a Queryable type holding the live instances of one kind.

Builds the per-kind mode class. The class object is itself the Queryable
registry of that kind's live instances (':_instances' returns them), so the
eight query methods apply directly to '<MODE_NAME>:any()' etc. The class owns
the shared lifecycle machinery; the transpiler fills in the per-kind 'init',
'deinit', and 'until' content via the returned hooks.
]]
function bootstrap.new_mode_class(name)
    local cls = setmetatable({}, Queryable)
    cls.__index = cls
    cls.__className = name
    cls._live = {}                 -- live instances, insertion order
    cls._until = {}                -- array of until-cause checkers (first-wins)

    --[[ RETURN: array, the live instances of this mode kind.

    Overrides Queryable:_instances; the registry's membership is its live set.
    ]]
    function cls:_instances()
        return cls._live
    end

    --[[ RETURN: string, the identity key built from an argument table.

    Identity is the parameter list: equal parameters mean the same instance.
    The key is the declared parameters joined in declaration order so that a
    re-arm with identical parameters maps to the existing instance.
    ]]
    function cls._identity(params, order)
        local parts = {}
        for _, k in ipairs(order) do
            parts[#parts + 1] = tostring(params[k])
        end
        return table.concat(parts, "\0")
    end

    --[[ RETURN: mode instance, the live instance for 'params' (new or existing).

    Idempotent arming: when an instance with identical parameters is already
    live, that instance is returned unchanged and 'init' is NOT re-run. A new
    instance is stamped with the read-only 'begin_time' and 'begin_event_index',
    registered as live, and its 'init' hook (if any) is run exactly once.
    ]]
    function cls.arm(params, begin_time, begin_event_index, order)
        local key = cls._identity(params, order)
        if cls._by_key == nil then cls._by_key = {} end
        local existing = cls._by_key[key]
        if existing ~= nil then
            return existing                 -- silent no-op re-arm
        end
        local self = setmetatable(params or {}, cls)
        self.begin_time = begin_time
        self.begin_event_index = begin_event_index
        self._key = key
        self._ceased = false
        cls._by_key[key] = self
        cls._live[#cls._live + 1] = self
        if type(self.init) == "function" then self:init() end
        return self
    end

    --[[ RETURN: nil

    Ceases one instance exactly once: removes it from the live set, runs its
    'deinit' hook (if any), and marks it ceased so a coincident second cessation
    (e.g. END after an 'until') is a no-op. The single well-defined cessation
    moment the first-wins 'until' rule guarantees.
    ]]
    function cls.cease(self)
        if self._ceased then return end
        self._ceased = true
        for i, inst in ipairs(cls._live) do
            if inst == self then table.remove(cls._live, i) break end
        end
        cls._by_key[self._key] = nil
        if type(self.deinit) == "function" then self:deinit() end
    end

    --[[ RETURN: True,  some 'until' clause fired and the instance was ceased.
                False, else

    Walks the 'until' checker list in declaration order against the current
    event and ceases the instance on the FIRST checker that fires; no later
    checker is consulted (first-wins). Each checker is a function
    '(self, event) -> boolean'. The transpiler appends checkers via
    ':add_until'; for a state-machine member the mandatory final checker is
    'switched', appended last so an explicit 'until' always wins a tie.
    ]]
    function cls.check_until(self, event)
        for _, checker in ipairs(cls._until) do
            if checker(self, event) then
                cls.cease(self)
                return true
            end
        end
        return false
    end

    --[[ RETURN: nil

    Registers one 'until'-cause checker, in declaration order, onto the kind.
    ]]
    function cls.add_until(checker)
        cls._until[#cls._until + 1] = checker
    end

    return cls
end

-- ===========================================================================
-- (3c) STATE-MACHINE BASE -- single-active habitat over member modes
-- ===========================================================================

--[[ RETURN: state-machine class, a habitat enforcing one active member at a time.

Builds the per-kind state-machine class. Reuses the mode lifecycle for its
member modes and adds only the habitat semantics: at most one member active,
arming a member fires the outgoing member's 'switched', and an optional
'default' member (an implicit do-nothing VOID when unspecified) becomes active
whenever no member remains. The state machine has its own 'init'/'deinit' and
binds 'sm' inside its members (the mode-group counterpart binds 'mg').
]]
function bootstrap.new_state_machine_class(name)
    local sm = bootstrap.new_mode_class(name)
    sm._active = nil               -- the single live member instance, or nil
    sm._default_arm = nil          -- function -> arms the default member (or VOID)

    --[[ RETURN: nil

    Installs the default-member arming function (nil selects the implicit VOID).
    Invoked by the habitat whenever the active member ceases with no successor.
    ]]
    function sm.set_default(arm_fn)
        sm._default_arm = arm_fn
    end

    --[[ RETURN: member instance, the newly active member; previous one switched out.

    The transition primitive: ceases the currently active member (firing its
    'switched' via 'cease', so its 'deinit' runs), then records 'incoming' as the
    single active member. Mutual exclusion is automatic -- this is the only path
    by which a member becomes active.
    ]]
    function sm.switch_to(incoming)
        local outgoing = sm._active
        sm._active = incoming
        if outgoing ~= nil and outgoing ~= incoming then
            outgoing._switched = true            -- mark cause of cessation
            getmetatable(outgoing).cease(outgoing)
        end
        return incoming
    end

    --[[ RETURN: nil

    Restores the single-active invariant after a member ceases by its own
    'until': if the ceased member was the active one and no successor was armed
    in the same instant, the default member (or VOID) is armed.
    ]]
    function sm.ensure_active()
        if sm._active ~= nil and sm._active._ceased then
            sm._active = nil
        end
        if sm._active == nil and sm._default_arm ~= nil then
            sm._active = sm._default_arm()
        end
    end

    return sm
end

-- ===========================================================================
-- (3d) MODE-GROUP BASE -- non-exclusive habitat over member modes
-- ===========================================================================

--[[ RETURN: mode-group class, a habitat whose member modes overlap freely.

Builds the per-kind mode-group class. Reuses the mode lifecycle for its member
modes and adds no exclusion: any number of members live at once, arming one
does not cease another. The mode group has its own 'init'/'deinit' and binds
'mg' inside its members -- the non-exclusive counterpart of the state machine's
'sm'. The two aggregate self-bindings, 'sm' and 'mg', are symmetric; the
transpiler emits whichever the enclosing aggregate kind dictates.
]]
function bootstrap.new_mode_group_class(name)
    local mg = bootstrap.new_mode_class(name)
    return mg
end

-- ===========================================================================
-- (3e) REACTOR CONTAINERS -- where a spawned aggregate lives
-- ===========================================================================
--
-- A spawned aggregate instance is offered to a CONTAINER. A container admits
-- or rejects the offer under a mutexed three-call slot protocol so concurrent
-- spawns cannot both claim one slot:
--
--     key = container:slot_reserve()      -- MUTEXED; 0 (NO_SLOT) on reject
--     -- construct the instance on the reserved key, outside the lock --
--     container:slot_set(key, instance)   -- commit the instance into the slot
--     ...
--     container:slot_free(key)            -- release on '-!' / end of existence
--
-- 'slot_free' on an unknown or already-freed key is a no-op, so ending an
-- existence is safe to call once even after a host has already released it.
-- Two base classes differ only in how 'slot_reserve' decides:
--   ScalarReactorContainer  holds 0..1; reserve fails when occupied.
--   MultiReactorContainer   holds 0..N; reserve mints a fresh key unless a
--                           kind-specific rule (capacity, or the default
--                           container's identity-by-parameters) rejects.

local NO_SLOT = 0

--[[ RETURN: scalar-container class, a container holding at most one instance.

ScalarReactorContainer reserves its single slot iff empty; a second reserve
while occupied returns NO_SLOT, so a duplicate spawn constructs nothing.
]]
function bootstrap.new_scalar_container()
    local c = { _slot = nil, _taken = false }

    --[[ RETURN: int key,  the reserved slot
                 NO_SLOT,   when already occupied

    The reserve half of the slot protocol; the caller treats this as the
    mutexed critical section. ]]
    function c:slot_reserve()
        if self._taken then return NO_SLOT end
        self._taken = true
        return 1
    end

    --[[ RETURN: nil. Commits 'instance' into the reserved slot 'key'. ]]
    function c:slot_set(key, instance)
        if key == 1 then self._slot = instance end
    end

    --[[ RETURN: nil. Releases the slot; an unknown/freed key is a no-op. ]]
    function c:slot_free(key)
        if key == 1 then self._slot = nil; self._taken = false end
    end

    --[[ RETURN: array, the held instance as a one- or zero-element list. ]]
    function c:_instances()
        if self._slot ~= nil then return { self._slot } end
        return {}
    end

    return c
end

--[[ RETURN: multi-container class, a container holding any number of instances.

MultiReactorContainer mints a fresh key per reserve unless an 'admit(self,
params)' predicate rejects the offer. The default per-kind container passes an
'admit' that rejects a parameterisation already present (identity = parameters,
as for modes), giving the silent-no-op duplicate-spawn semantics.
]]
function bootstrap.new_multi_container(admit)
    local c = { _slots = {}, _next = 1, _admit = admit }

    --[[ RETURN: int key,  a fresh reserved slot
                 NO_SLOT,  when the 'admit' predicate rejects

    The reserve half of the slot protocol (mutexed critical section). ]]
    function c:slot_reserve(params)
        if self._admit ~= nil and not self._admit(self, params) then
            return NO_SLOT
        end
        local key = self._next
        self._next = self._next + 1
        self._slots[key] = false        -- reserved, not yet committed
        return key
    end

    --[[ RETURN: nil. Commits 'instance' into the reserved slot 'key'. ]]
    function c:slot_set(key, instance)
        if self._slots[key] ~= nil then self._slots[key] = instance end
    end

    --[[ RETURN: nil. Releases the slot; an unknown/freed key is a no-op. ]]
    function c:slot_free(key)
        self._slots[key] = nil
    end

    --[[ RETURN: array, every committed instance, in key order. ]]
    function c:_instances()
        local out = {}
        for key = 1, self._next - 1 do
            local v = self._slots[key]
            if v ~= nil and v ~= false then out[#out + 1] = v end
        end
        return out
    end

    return c
end

bootstrap.NO_SLOT = NO_SLOT

-- ===========================================================================
-- (4) TRACER -- opt-in event history; each key is a Queryable
-- ===========================================================================

local Tracer = {}
Tracer.__index = Tracer
bootstrap.Tracer = Tracer

--[[ RETURN: tracer, a fresh tracer holding no watched kinds.

The history facility is opt-in: until a kind is registered via ':watch', it has
no history and answering a query against it is a (transpile-time) error.
]]
function Tracer.new()
    return setmetatable({ _watched = {} }, Tracer)
end

--[[ RETURN: nil

Registers coverage for one event kind. 'last' bounds the entries retained for
the kind (default 1). History is a single flat ring per type -- there is no
per-attribute keying. Querying an unregistered kind is rejected statically by
the transpiler -- this closes the silent-nil class of bug where a forgotten
'watch' makes every query return nil.
]]
function Tracer:watch(kind, last)
    self._watched[kind.__className] = {
        kind = kind,
        last = last or 1,
        _ring = {},            -- flat history of occurrences, oldest first
    }
end

--[[ RETURN: nil

Records one occurrence into its kind's flat history when the kind is watched
(otherwise a no-op). The ring is trimmed from the front so it never exceeds the
'last' bound set at ':watch'.
]]
function Tracer:record(event)
    local w = self._watched[getmetatable(event).__className]
    if w == nil then return end
    local ring = w._ring
    ring[#ring + 1] = event
    while #ring > w.last do table.remove(ring, 1) end
end

return bootstrap
