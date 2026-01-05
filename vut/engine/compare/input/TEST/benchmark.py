import sys

sys.path.insert(0, "../../../../../")
import time
import string
from vut.engine.compare.configuration            import ConfigurationPatternFinder
from vut.engine.compare.input.pattern_finder import PatternFinder
from vut.language_support.python.deterministic_random          import DeterministicStream

def string_stream(n=10000, complexity=0.5, seed=0x42):
    """
    Generates a deterministic stream of strings containing various patterns.
    
    Args:
        n (int): Number of strings to generate.
        complexity (float): Probability [0, 1] of inserting a specific pattern.
        seed (int): The seed for the DeterministicStream.
    """
    stream = DeterministicStream(seed=seed)
    char_pool = string.ascii_lowercase + " "
    letter_pool = string.ascii_letters

    def get_random_string(length):
        return "".join(char_pool[stream.next_int(0, len(char_pool) - 1)] for _ in range(length))

    def gen_analogy():
        char = letter_pool[stream.next_int(0, len(letter_pool) - 1)]
        return f"(({char * 5}))"

    def gen_number():
        return str(stream.gauss(0, 500))

    def gen_whitespace():
        return (" " * stream.next_int(1, 5)) + "\t"

    def gen_slashes():
        return ("/" * stream.next_int(1, 3)) + ("\\" * stream.next_int(1, 2))

    def gen_text():
        return get_random_string(15)

    patterns = [
        gen_analogy,
        gen_number,
        gen_whitespace,
        gen_slashes,
        lambda: "||||",
        lambda: "## ignored content ##",
        gen_text
    ]

    for _ in range(n):
        parts = []
        num_segments = stream.next_int(1, 5)
        for _ in range(num_segments):
            if (stream.next_int(0, 1000) / 1000.0) < complexity:
                pat_idx = stream.next_int(0, len(patterns) - 1)
                parts.append(patterns[pat_idx]())
            else:
                parts.append(get_random_string(10))
        
        yield " ".join(parts)

def verify(results, n, complexity, seed, config):
    """
    Verifies that the collected results match a fresh run of the 
    deterministic generator.
    """
    print(f"Starting verification of {len(results)} lines...")
    verification_finder = PatternFinder(config)
    expected_stream = string_stream(n=n, complexity=complexity, seed=seed)
    
    for i, (actual_elements, expected_line) in enumerate(zip(results, expected_stream)):
        expected_elements = tuple(verification_finder.do(expected_line))
        
        # We compare the length and the string representation of elements
        # to ensure the content and types are identical.
        if len(actual_elements) != len(expected_elements):
            raise ValueError(f"Verification failed at line {i}: Element count mismatch.")
            
        for act, exp in zip(actual_elements, expected_elements):
            if str(act) != str(exp):
                 raise ValueError(f"Verification failed at line {i}: Content mismatch.\nGot: {act}\nExp: {exp}")
    
    print("Verification successful: Results are consistent with expectations.")

def run(n, complexity, seed):
    """
    Benchmarks the PatternFinder and verifies the results.
    """
    config = ConfigurationPatternFinder()
    config.analogy_f = True
    config.numeric_tolerance_ratio = 0.5
    config.whitespace_f = True
    config.backslash_f = True

    # Initialize the generator
    stream = string_stream(n=n, complexity=complexity, seed=seed)
    finder = PatternFinder(config)
    
    # Aggregator for results
    all_results = []
    total_elements = 0
    
    print(f"Starting benchmark (n={n}, complexity={complexity})...")
    start_time = time.perf_counter()
    
    for line in stream:
        # We aggregate elements into a list of tuples
        elements = tuple(finder.do(line))
        all_results.append(elements)
        total_elements += len(elements)
        
    end_time = time.perf_counter()
    duration = end_time - start_time
    
    print("-" * 30)
    print("Benchmark Results:")
    print(f"  Processed: {len(all_results)} lines")
    print(f"  Found:     {total_elements} elements")
    print(f"  Time:      {duration:.4f} seconds")
    if duration > 0:
        print(f"  Throughput: {len(all_results) / duration:.2f} lines/sec")
    print("-" * 30)

    # Now verify the aggregated results
    verify(all_results, n, complexity, seed, config)

if __name__ == "__main__":
    # Benchmark parameters
    N_LINES = 50000
    COMPLEXITY = 0.7
    SEED = 0x42
    
    run(N_LINES, COMPLEXITY, SEED)
