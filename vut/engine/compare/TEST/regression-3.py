#! /usr/bin/env python3
#  @hwut {
#    title   = "Registry Sandbox Regression"
#    choices = ["associate", "equivalence"]
#  }
"""
Regression Test Suite 3: Global Registry Isolation and Performance check.

PURPOSE:
    Verify that the Registry is isolated per session. We use a 'SpyStream'
    to capture the registry instance active during the engine's execution.
"""
import sys
import io
import asyncio

# --- Path Setup ---
from config import HwutRunner

from vut.engine.compare.configuration import Configuration
import vut.engine.compare.main          as main
import vut.engine.compare.contract.frozen_analogy_db as fdb

# --- The Spy ---

class SpyStream(io.StringIO):
    """A stream that captures the active ContextVar registry during a read."""
    def __init__(self, content):
        super().__init__(content)
        self.captured_registry = None

    async def readline(self):
        # This is called by the engine while the Sandbox is active
        reg = fdb.context_frozen_analogy_db_registry.get()
        if reg and self.captured_registry is None:
            self.captured_registry = reg
        return super().readline()

# --- Utilities ---

def generate_potpourri(n, prefix="sym"):
    """Generates strings for a potpourri block with n analogies."""
    s = ["##! potpourri"]
    n_list = ["##! potpourri"]
    for i in range(n):
        s.append(f"{i} (({prefix}_{i}))") # add some unique 'i' to prevent to liberal analogies
        n_list.append(f"{i} ((val_{i}))") # add some unique 'i' to prevent to liberal analogies
    s.append("####")
    n_list.append("####")
    return "\n".join(s), "\n".join(n_list)

async def run_monitored_session(mode, subject_str, nominal_str):
    """Runs a session and returns the SpyStream used."""
    cfg = Configuration()
    spy = SpyStream(subject_str)
    nom = io.StringIO(nominal_str)

    if mode == 'equivalence':
        await main.is_equivalent(cfg, spy, nom)
    else:
        async for _ in main.associate(cfg, spy, nom):
            pass
    return spy

# --- Scenario Logic ---

async def run_isolation_test(mode):
    print(f"\n[SCENARIO] Mode: {mode.upper()}")
    print("-" * 80)

    # Access the registry limit (256)
    # We use the default registry instance to find the constant
    limit = fdb.context_frozen_analogy_db_registry.get()._MASK_LIMIT

    # --- STEP 1: HEAVY SESSION ---
    heavy_n = limit + 10
    h_s, h_n = generate_potpourri(heavy_n, "HEAVY")

    print(f"  Action: Running Heavy Session ({heavy_n} analogies)...")
    spy_heavy = await run_monitored_session(mode, h_s, h_n)
    reg_heavy = spy_heavy.captured_registry

    # --- STEP 2: LIGHT SESSION ---
    l_s, l_n = generate_potpourri(1, "LIGHT")
    print("  Action: Running Light Session (1 analogy: '((LIGHT_0))')...")

    # Separate task to ensure isolation
    spy_light = await asyncio.create_task(run_monitored_session(mode, l_s, l_n))
    reg_light = spy_light.captured_registry

    # --- STEP 3: VERIFICATION ---
    if not reg_heavy or not reg_light:
        print("\nVERDICT: FAIL")
        print("DETAILS: Registry capture failed. Solvers might not be triggering FrozenAnalogyDb.")
        return

    # 1. Identity Check
    same_instance = (reg_heavy is reg_light)

    # 2. Leakage Check
    heavy_in_light = "((HEAVY_0))" in reg_light.symbols

    # 3. Poisoning Check
    light_id = reg_light.symbols.get("((LIGHT_0))")

    print("\n  STATE INSPECTION:")
    print(f"    - Same Registry Instance: {same_instance}")
    print(f"    - Heavy symbols count:   {len(reg_heavy.symbols)}")
    print(f"    - Light symbols count:   {len(reg_light.symbols)}")
    print(f"    - Leakage detected:      {heavy_in_light}")
    print(f"    - Light Symbol ID:       {light_id} (Limit: {limit})")

    if same_instance or heavy_in_light or (light_id is not None and light_id >= limit):
        reasons = []
        if same_instance:  reasons.append("Same registry instance reused")
        if heavy_in_light: reasons.append("Data leaked between sessions")
        if light_id is not None and light_id >= limit:
            reasons.append(f"ID poisoned ({light_id} >= {limit})")
        print("\nVERDICT: FAIL")
        print(f"DETAILS: {' & '.join(reasons)}")
    else:
        print("\nVERDICT: PASS")
        print("DETAILS: Sessions are isolated. Symbol IDs reset to 0.")

if __name__ == "__main__":
    choices = {
        "equivalence": lambda: asyncio.run(run_isolation_test("equivalence")),
        "associate":   lambda: asyncio.run(run_isolation_test("associate")),
    }
    HwutRunner(sys.argv, "Registry Sandbox Regression", choices).run()
