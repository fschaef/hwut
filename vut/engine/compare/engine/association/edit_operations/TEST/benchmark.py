#! /usr/bin/env python
"""SPDX-License: MIT; (C) Frank-Rene Schaefer; Project: VUT
________________________________________________________________________________

PURPOSE: Benchmark suite for evaluating performance and accuracy of 
         edit-distance algorithms using correct LineElement factory logic.
         Supports configurable ratio of lines containing analogies.
________________________________________________________________________________
"""
import sys
import time
import argparse
from dataclasses import dataclass
from typing import List, Tuple

# Ensure VUT is in path
sys.path.insert(0, "../../../../../")

from vut.auxiliary.deterministic_random import DeterministicStream
from vut.engine.compare.input.line_element import E_ToleranceId, LineElement, LineElementString
from vut.engine.compare.engine.line import Line
import vut.engine.compare.engine.association.edit_operations.line as edit_line
import vut.engine.compare.engine.association.edit_operations.line_sequence as edit_seq

@dataclass
class MutationProfile:
    """Defines the probability distribution of different edit operations."""
    substitute: float = 0.1
    insert: float     = 0.05
    delete: float     = 0.05
    transpose: float  = 0.05
    good: float       = 0.75 
    analogy_ratio: float = 0.2  # Ratio of lines that may contain analogies

class ScenarioGenerator:
    """Generates deterministic pairs of sequences for benchmarking."""
    
    def __init__(self, seed: int = 0x12345):
        self.stream = DeterministicStream(seed=seed)
        self.type_pool_all = [
            E_ToleranceId.STRING,
            E_ToleranceId.NUMERIC,
            E_ToleranceId.ANALOGY,
            E_ToleranceId.VISIBLE_NOTHING,
            E_ToleranceId.SEPERATOR
        ]
        self.type_pool_no_analogy = [
            E_ToleranceId.STRING,
            E_ToleranceId.NUMERIC,
            E_ToleranceId.VISIBLE_NOTHING,
            E_ToleranceId.SEPERATOR
        ]

    def _random_le(self, pool: List[E_ToleranceId], content_len=5):
        """Creates a mock LineElement using the provided factory logic and a specific pool."""
        tol_id = pool[self.stream.next_int(0, len(pool) - 1)]
        
        # Context-aware content generation
        if tol_id == E_ToleranceId.NUMERIC:
            # Generate digits '0'-'9' so LineElementNumber can actually parse it
            content = "".join(chr(self.stream.next_int(48, 57)) for _ in range(content_len))
        elif tol_id == E_ToleranceId.ANALOGY:
            # Use standard ((x)) format for analogies
            inner = chr(self.stream.next_int(97, 122))
            content = f"(({inner}))"
        elif tol_id == E_ToleranceId.SEPERATOR:
            content = " "
        else:
            # Standard alphabetic strings
            content = "".join(chr(self.stream.next_int(97, 122)) for _ in range(content_len))
        
        # STRING is special: it's not generated from tokens/factory
        if tol_id == E_ToleranceId.STRING:
            return LineElementString(content)
        
        # Use the requested factory for all other types
        return LineElement.from_match(
            tolerance_id=tol_id, 
            content=content, 
            numeric_tolerance_ratio=0.1
        )

    def generate_le_pair(self, length: int, profile: MutationProfile) -> Tuple[List, List, float]:
        """
        Generates a subject/nominal pair of LineElements.
        The line will contain analogies based on the profile's analogy_ratio.
        """
        # Decide if this specific line should allow analogies
        use_analogy = self.stream.next_int(0, 1000) < (profile.analogy_ratio * 1000)
        pool = self.type_pool_all if use_analogy else self.type_pool_no_analogy

        base = [self._random_le(pool) for _ in range(length)]
        nominal = []
        subject = []
        expected_cost = 0.0

        i = 0
        while i < length:
            r = self.stream.next_int(0, 1000) / 1000.0
            
            if r < profile.delete:
                le = base[i]
                subject.append(le)
                if le.tolerance_id != E_ToleranceId.VISIBLE_NOTHING:
                    expected_cost += 1.0
                i += 1
            elif r < (profile.delete + profile.insert):
                le = self._random_le(pool)
                nominal.append(le)
                if le.tolerance_id != E_ToleranceId.VISIBLE_NOTHING:
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
                nominal.append(self._random_le(pool))
                expected_cost += 1.0
                i += 1
            else:
                subject.append(base[i])
                nominal.append(base[i])
                i += 1
                
        return subject, nominal, expected_cost

    def generate_line_seq_pair(self, num_lines: int, line_len: int, profile: MutationProfile):
        """Generates a pair of Line sequences (files) with distributed analogy types."""
        subject_lines = []
        nominal_lines = []
        
        # We use generate_le_pair logic to create diverse lines
        for i in range(num_lines):
            sub_elements, nom_elements, _ = self.generate_le_pair(line_len, profile)
            subject_lines.append(Line(i, sub_elements))
            nominal_lines.append(Line(i, nom_elements))
            
        return subject_lines, nominal_lines 

class VUTBenchmark:
    def __init__(self):
        self.gen = ScenarioGenerator()

    def run_line_level(self, iterations=100, length=50, analogy_ratio=0.2):
        print(f"--- Line Element Benchmark (N={iterations}, Len={length}, AnalogyRatio={analogy_ratio}) ---")
        profile = MutationProfile(analogy_ratio=analogy_ratio)
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

    def run_sequence_level(self, iterations=10, num_lines=100, analogy_ratio=0.2):
        print(f"--- Line Sequence Benchmark (N={iterations}, Lines={num_lines}, AnalogyRatio={analogy_ratio}) ---")
        profile = MutationProfile(analogy_ratio=analogy_ratio)
        total_time = 0.0
        
        for _ in range(iterations):
            sub, nom = self.gen.generate_line_seq_pair(num_lines, 10, profile)
            start = time.perf_counter()
            edit_seq.do(sub, nom)
            total_time += (time.perf_counter() - start)

        print(f"Total Time: {total_time:.4f}s")
        if total_time > 0:
            print(f"Throughput: {(iterations * num_lines) / total_time:.2f} lines/sec")
        print("-" * 40 + "\n")

def main():
    parser = argparse.ArgumentParser(description="VUT Edit Distance Benchmark Suite")
    parser.add_argument("--line", action="store_true", help="Run line-element level benchmark")
    parser.add_argument("--sequence", action="store_true", help="Run line-sequence level benchmark")
    parser.add_argument("-i", "--iterations", type=int, default=100)
    parser.add_argument("-l", "--length", type=int, default=50)
    parser.add_argument("-ar", "--analogy-ratio", type=float, default=0.02,
                        help="Ratio of lines containing analogies (0.0 to 1.0, default: 0.2)")

    args = parser.parse_args()
    bench = VUTBenchmark()

    run_all = not (args.line or args.sequence)

    if args.line or run_all:
        bench.run_line_level(iterations=args.iterations, length=args.length, analogy_ratio=args.analogy_ratio)

    if args.sequence or run_all:
        bench.run_sequence_level(iterations=args.iterations, num_lines=args.length, analogy_ratio=args.analogy_ratio)

if __name__ == "__main__":
    main()
