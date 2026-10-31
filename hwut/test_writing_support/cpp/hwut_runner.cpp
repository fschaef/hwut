// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The front end of a HWUT test application -- see 'hwut_runner.hpp'.
//
// THE C RUNNER CALLS A PLAIN 'void (*)(void)'. A choice here is a
// 'std::function', so each choice gets one of CHOICE_MAX trampolines, the
// I-th calling the I-th function of the one runner a process has.
// _____________________________________________________________________________
#include "hwut_runner.hpp"

#include <array>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <stdexcept>
#include <utility>

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/types.h>
namespace hwut { namespace c {       // the C core, out of the global namespace
extern "C" {
#include "../c/hwut_runner.h"
}
} }

using namespace hwut::c;

namespace hwut {

namespace {

std::vector<HwutRunner::Function>* the_function_list = nullptr;

void
call(size_t i)
/* RETURN: nothing, once the i-th choice ran; an exception that leaves it
 *         is said on stderr and the process exits 1.                       */
{
    try {
        (*the_function_list)[i]();
    } catch( const std::exception& error ) {
        std::fflush(stdout);
        std::fprintf(stderr, "error: uncaught exception: %s\n", error.what());
        std::exit(1);
    } catch( ... ) {
        std::fflush(stdout);
        std::fprintf(stderr, "error: uncaught exception\n");
        std::exit(1);
    }
}

template <size_t I> void trampoline() { call(I); }

template <size_t... I>
constexpr std::array<HwutRunner_Function, sizeof...(I)>
trampoline_list(std::index_sequence<I...>)
{ return { { &trampoline<I>... } }; }

} // namespace

HwutRunner::HwutRunner(int argc, char** argv, std::string title, ChoiceList choice_list)
/* RETURN: HwutRunner, ready for 'run'. 'choice_list' maps the choice names
 *         to their functions; "-" alone names the choice-less test.       */
    : argc_(argc), argv_(argv), title_(std::move(title)), choice_list_(std::move(choice_list))
{
    if( choice_list_.empty() || choice_list_.size() >= CHOICE_MAX )
        throw std::invalid_argument("HwutRunner: from 1 to 255 choices");
}

int
HwutRunner::run()
/* RETURN: the exit status of the mode the command line selects (see the
 *         header); a refusal is 1.                                         */
{
    static const auto              trampoline = trampoline_list(std::make_index_sequence<CHOICE_MAX>());
    static std::vector<Function>   function_list;
    std::vector<HwutRunner_Choice> c_choice_list;
    std::vector<const char*>       c_happy;
    c::HwutRunner                   c_runner;

    function_list.clear();
    for(const auto& choice : choice_list_) {
        c_choice_list.push_back({ choice.first.c_str(), trampoline[function_list.size()] });
        function_list.push_back(choice.second);
    }
    c_choice_list.push_back({ nullptr, nullptr });
    the_function_list = &function_list;
    for(const auto& h : happy) c_happy.push_back(h.c_str());
    c_happy.push_back(nullptr);

    HwutRunner_init(&c_runner, argc_, argv_, title_.c_str(), c_choice_list.data());
    c_runner.happy      = happy.empty() ? nullptr : c_happy.data();
    c_runner.same_f     = same_f;
    c_runner.parallel_f = parallel_f;
    std::fflush(stdout);
    return HwutRunner_run(&c_runner);
}

int
levenshtein_distance(const std::string& a, const std::string& b)
/* RETURN: the Levenshtein distance between 'a' and 'b', >= 0.              */
{ return HwutRunner_levenshtein_distance(a.c_str(), b.c_str()); }

std::optional<std::string>
levenshtein_best_match(const std::optional<std::string>& needle, const std::vector<std::string>& haystack)
/* RETURN: the element of 'haystack' least distant from 'needle', the first
 *         of equal ones; nullopt where 'needle' is empty or 'haystack' is. */
{
    std::vector<const char*> list;
    for(const auto& h : haystack) list.push_back(h.c_str());
    const char* best = needle ? HwutRunner_levenshtein_best_match(needle->c_str(), list.data(), (int)list.size())
                              : nullptr;
    if( ! best ) return std::nullopt;
    return std::string(best);
}

} // namespace hwut
