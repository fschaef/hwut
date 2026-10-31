// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The deterministic random stream -- see 'deterministic_random.hpp'.
// _____________________________________________________________________________
#include "deterministic_random.hpp"

using namespace hwut::c;

namespace hwut {

int64_t
DeterministicStream::next_int(int64_t v_min, int64_t v_max)
/* RETURN: an integer uniform in [v_min, v_max]; the state steps even where
 *         the range is one value.                                          */
{ return DeterministicStream_next_int(&c_, v_min, v_max); }

double
DeterministicStream::next_float()
/* RETURN: a number in [0, 1): 'next_int(0, 1000000) / 1000001'.            */
{ return DeterministicStream_next_float(&c_); }

bool
DeterministicStream::coin(double probability_of_true)
/* RETURN: true with 'probability_of_true', false else.                     */
{ return DeterministicStream_coin(&c_, probability_of_true) != 0; }

double
DeterministicStream::gauss(double mu, double sigma, double lower, double upper)
/* RETURN: a draw of the normal distribution (mu, sigma) by Box-Muller,
 *         clipped to [lower, upper] (-INF, INF: none).                     */
{ return DeterministicStream_gauss(&c_, mu, sigma, lower, upper); }

int64_t
DeterministicStream::gauss_int(double mu, double sigma, double lower, double upper)
/* RETURN: 'gauss' rounded to the nearest integer, a half to the even one --
 *         as Python's 'round'.                                             */
{ return DeterministicStream_gauss_int(&c_, mu, sigma, lower, upper); }

std::vector<size_t>
DeterministicStream::sample_indices(size_t population_size, size_t k)
/* RETURN: 'k' distinct indices of 0 .. population_size-1, drawn by
 *         Fisher-Yates; std::invalid_argument where k > population_size.  */
{
    if( k > population_size ) throw std::invalid_argument("sample_indices: k > population_size");
    std::vector<size_t> result(k);
    if( k ) DeterministicStream_sample_indices(&c_, population_size, k, result.data());
    return result;
}

size_t
DeterministicStream::index_into(size_t candidate_n)
/* RETURN: an index into 'candidate_n' candidates, uniformly drawn;
 *         std::invalid_argument where there is none to draw.              */
{
    if( candidate_n == 0 ) throw std::invalid_argument("select: no candidates");
    return DeterministicStream_select(&c_, candidate_n);
}

} // namespace hwut
