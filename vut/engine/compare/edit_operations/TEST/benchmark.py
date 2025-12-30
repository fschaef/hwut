#! /usr/bin/env python
"""SPDX-License: MIT; (C) Frank-Rene Schaefer; Project: VUT
________________________________________________________________________________

PURPOSE: Benchmark suite for evaluating performance and accuracy of 
         edit-distance algorithms.

SCENARIOS:
    1. Line Element Level: Comparing sequences of LineElements (Inside a Line).
    2. Line Sequence Level: Comparing lists of Lines (Between Files).

METRICS:
    - Throughput: Elements/Second or Lines/Second.
    - Path Optimality: Did the algorithm find a cost <= Mutation Cost?
________________________________________________________________________________
"""
import sys
sys.path.insert(0, "../../../../../")

import time
import argparse
from dataclasses import dataclass
from typing import List, Tuple

from vut.auxiliary.deterministic_random import DeterministicStream
from vut.engine.compare.tolerance.line_element import E_ToleranceId, LineElement
from vut.engine.compare.engine.line import Line
import vut.engine.compare.edit_operations.line as edit_line
import vut.engine.compare.edit_operations.line_sequence as edit_seq

@dataclass
class MutationProfile:
    """Defines the probability distribution of different edit operations."""
    substitute: float = 0.1
    insert: float     = 0.05
    delete: float     = 0.05
    transpose: float  = 0.05
    good: float       = 0.75 # Remaining probability

class ScenarioGenerator:
    """Generates deterministic pairs of sequences for benchmarking."""
    
    def __init__(self, seed: int = 0x12345):
        self.stream = DeterministicStream(seed=seed)
        self.type_pool = [
            E_ToleranceId.STRING,
            E_ToleranceId.NUMERIC,
            E_ToleranceId.ANALOGY,
            E_ToleranceId.VISIBLE_NOTHING,
            E_ToleranceId.SEPERATOR
        ]

    def _random_le(self, content_len=5):
        """Creates a mock LineElement."""
        tol_id = self.type_pool[self.stream.next_int(0, len(self.type_pool) - 1)]
        content = "".join(chr(self.stream.next_int(97, 122)) for _ in range(content_len))
        le = LineElement.from_match(tol_id, content, 0.01, (1,2,3))
        return le

    def generate_le_pair(self, length: int, profile: MutationProfile) -> Tuple[List, List, float]:
        """
        Generates a subject/nominal pair of LineElements.
        RETURNS: (subject, nominal, expected_max_cost)
        """
        base = [self._random_le() for _ in range(length)]
        nominal = []
        subject = []
        expected_cost = 0.0

        i = 0
        while i < length:
            r = self.stream.next_int(0, 1000) / 1000.0
            
            if r < profile.delete:
                subject.append(base[i])
                expected_cost += 1.0
                i += 1
            elif r < (profile.delete + profile.insert):
                nominal.append(self._random_le())
                expected_cost += 1.0
            elif r < (profile.delete + profile.insert + profile.transpose) and i < length - 1:
                subject.append(base[i+1])
                subject.append(base[i])
                nominal.append(base[i])
                nominal.append(base[i+1])
                expected_cost += 0.5 
                i += 2
            elif r < (profile.delete + profile.insert + profile.transpose + profile.substitute):
                subject.append(base[i])
                nominal.append(self._random_le())
                expected_cost += 1.0
                i += 1
            else:
                subject.append(base[i])
                nominal.append(base[i])
                i += 1
                
        return subject, nominal, expected_cost

    def generate_line_seq_pair(self, num_lines: int, line_len: int, profile: MutationProfile):
        """Generates a pair of Line sequences (files)."""
        base_lines = []
        for i in range(num_lines):
            elements = [self._random_le() for _ in range(line_len)]
            base_lines.append(Line(i, elements))
            
        return base_lines, base_lines 

class VUTBenchmark:
    def __init__(self):
        self.gen = ScenarioGenerator()

    def run_line_level(self, iterations=100, length=50):
        print(f"--- Line Element Benchmark (N={iterations}, Len={length}) ---")
        profile = MutationProfile()
        total_time = 0.0
        total_elements = 0
        
        for _ in range(iterations):
            sub, nom, _ = self.gen.generate_le_pair(length, profile)
            start = time.perf_counter()
            edit_line.do(tuple(sub), tuple(nom))
            total_time += (time.perf_counter() - start)
            total_elements += (len(sub) + len(nom))

        print(f"Total Time: {total_time:.4f}s")
        if total_time > 0:
            print(f"Throughput: {total_elements / total_time:.2f} elements/sec")
        print("-" * 40 + "\n")

    def run_sequence_level(self, iterations=10, num_lines=100):
        print(f"--- Line Sequence Benchmark (N={iterations}, Lines={num_lines}) ---")
        total_time = 0.0
        
        for _ in range(iterations):
            sub, nom = self.gen.generate_line_seq_pair(num_lines, 10, MutationProfile())
            start = time.perf_counter()
            edit_seq.do(sub, nom)
            total_time += (time.perf_counter() - start)

        print(f"Total Time: {total_time:.4f}s")
        if total_time > 0:
            print(f"Throughput: {(iterations * num_lines) / total_time:.2f} lines/sec")
        print("-" * 40 + "\n")

def main():
    parser = argparse.ArgumentParser(description="VUT Edit Distance Benchmark Suite")
    
    # Selection flags
    parser.add_argument("--line", action="store_true", help="Run line-element level benchmark")
    parser.add_argument("--sequence", action="store_true", help="Run line-sequence level benchmark")
    
    # Parameters
    parser.add_argument("-i", "--iterations", type=int, default=100, 
                        help="Number of iterations for the benchmark (default: 100)")
    parser.add_argument("-l", "--length", type=int, default=50, 
                        help="Sequence length (elements per line or lines per sequence, default: 50)")

    args = parser.parse_args()
    bench = VUTBenchmark()

    # If no flags provided, run both by default
    run_all = not (args.line or args.sequence)

    if args.line or run_all:
        bench.run_line_level(iterations=args.iterations, length=args.length)

    if args.sequence or run_all:
        # For sequence level, we keep iterations lower by default if using global i
        # but here we follow the user's explicit iterations.
        bench.run_sequence_level(iterations=args.iterations, num_lines=args.length)

if __name__ == "__main__":
    main()
