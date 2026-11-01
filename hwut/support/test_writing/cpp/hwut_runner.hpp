// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: FRONT END OF A HWUT TEST APPLICATION IN C++ -- the port of
//          'python/hwut_runner.py', a thin face over '../c/hwut_runner.c':
//          the same modes, the same words.
//
//     app --hwut-info      the info block; exit 0.
//     app <choice>         one choice; test output on stdout and stderr,
//                          '<hwut-end>' after it. '-' runs a choice-less test.
//     app --interactive    choices started over stdin, output into two named
//                          sink files per choice, 'done' on the original stdout.
//     app                  the choice-less test; where the application has
//                          choices, refused, naming them.
//
// USAGE:
//
//     int main(int argc, char** argv)
//     {
//         hwut::HwutRunner runner(argc, argv, "What this tests", {
//             { "plain",  [] { ... } },
//             { "tricky", run_tricky },
//         });
//         return runner.run();
//     }
//
// A choice is any 'std::function<void()>' -- a function, a lambda with its
// captures. A choice-less test names its one choice "-" (Python's 'None').
// Before 'run' a test may set 'happy', 'same_f' and 'parallel_f'
// (interactive: choices run concurrently).
//
// THE INTERACTIVE PROTOCOL is Python's, line for line (see the C header):
// every choice runs in a child process of its own, so a choice that calls
// 'exit', crashes or lets an exception escape ends that choice alone.
//
// AN EXCEPTION THAT LEAVES A CHOICE is said on stderr --
// 'error: uncaught exception: <what>' -- and the choice exits 1, without
// '<hwut-end>': as a Python traceback ends the run.
// _____________________________________________________________________________
#ifndef HWUT_RUNNER_HPP
#define HWUT_RUNNER_HPP

#include <functional>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace hwut {

class HwutRunner {
public:
    using Function   = std::function<void()>;
    using ChoiceList = std::vector<std::pair<std::string, Function>>;

    HwutRunner(int argc, char** argv, std::string title, ChoiceList choice_list);
    int run();

    std::vector<std::string> happy;          // the info block's 'HAPPY:' lines
    bool                     same_f     = false;
    bool                     parallel_f = false;

    static constexpr size_t  CHOICE_MAX = 256;

private:
    int         argc_;
    char**      argv_;
    std::string title_;
    ChoiceList  choice_list_;
};

int                        levenshtein_distance(const std::string& a, const std::string& b);
std::optional<std::string> levenshtein_best_match(const std::optional<std::string>& needle,
                                                  const std::vector<std::string>& haystack);

} // namespace hwut

#endif
