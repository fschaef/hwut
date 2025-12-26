import time

# Assuming these are accessible via your sys.path setup
import sys
import os

this_directory = os.path.join(os.path.dirname(sys.argv[0]), "../../../../../")
sys.path.insert(0, this_directory)

import vut.engine.compare.friends_pairing.matching              as m              #noqa E402
from   vut.engine.compare.engine.analogy_db                     import AnalogyDb  #noqa E402
import vut.engine.compare.friends_pairing.TEST.benchmark_helper as scn            #noqa E402

def run_benchmark(n_range:     list[int], 
                  k_range:     list[float], 
                  ratio_range: list[float],
                  iterations:  int = 1) -> None:
    """
    PERFORMANCE ANALYSIS:
    Sweeps through parameter variations to measure pairing efficiency.
    """
    results = []

    print(f"{'N':>5} | {'K_AVG':>6} | {'RATIO':>6} | {'TIME (s)':>10} | {'STATUS'}")
    print("-" * 50)

    def iterable(n_range, k_range, ratio_range):
        for n in n_range:
            for k in k_range:
                for ratio in ratio_range:
                    yield n, k , ratio

    for n, k, ratio in iterable(n_range, k_range, ratio_range):
        # Generate the potential_pair_db using our deterministic generator
        # Note: ac_pp_n is kept constant for baseline, but could be swept too
        db = scn.scenario(n=n, c_vs_uc_ratio=ratio, k_avg=k, ac_pp_n=2)

        for ia, mate_list in db.items():
            for ib, analogy_db in mate_list:
                print(f"[{ia}]-[{ib}] -- {analogy_db}")

        # Wrap the dictionary into the Result structure required by pairing()
        # Assuming UnpairedCandidateGraph can be initialized from our dict
        state = m.Result(potential_pair_db     = db, 
                         pair_db               = {}, # Start with empty paired graph
                         analogy_constraint_db = AnalogyDb(),
                         required_pair_n       = n,
                         aborted_f             = False)

        # Timing execution
        avg_t   = 0
        abort_f = True
        for _ in range(1):
            start    = time.perf_counter()
            output   = m.pairing(state)
            end      = time.perf_counter()
            abort_f &= output.aborted_f
            avg_t   += (end - start) / float(iterations)

        status = "ABORTED" if abort_f else "SUCCESS"
        print(f"{n:5d} | {k:6.1f} | {ratio:6.2f} | {avg_t:10.5f} | {status}")

    return results

if __name__ == "__main__":
    # Define the variations you want to test
    # Example: See how scaling N from 10 to 100 affects time
    N_SAMPLES = list(range(1, 100))
   
    # Example: See how 'ambiguity' (partners per entry) affects backtracking
    K_SAMPLES = [5.5]
    
    # Example: See how constraint density affects speed
    RATIO_SAMPLES = [0.0 ]

    results = run_benchmark(N_SAMPLES, K_SAMPLES, RATIO_SAMPLES)
