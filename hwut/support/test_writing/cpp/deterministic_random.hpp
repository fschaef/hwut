// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: A RANDOM STREAM THAT IS THE SAME EVERYWHERE -- the port of
//          'python/deterministic_random.py', a thin face over
//          '../c/deterministic_random.c'. The same seed gives the same
//          numbers as the Python module, draw for draw: Park-Miller MINSTD.
//
//     hwut::DeterministicStream s(0x42);
//     s.next_int(0, 9);   s.next_float();   s.coin(0.5);
//     s.select(pool);                         -- an element of a vector, array
//     s.gauss(0.0, 1.0);                      -- or string (then a char)
//     s.sample_indices(10, 3);  s.sample(pool, 3);  s.choice(pool);
//
//     hwut::SelectionMarker m;
//     s.select_unchosen(pool, m);
//
// IDENTITY, AS IN PYTHON ('id()'): a marker remembers a candidate that is a
// POINTER by what it points to, any other candidate by its ADDRESS. So a
// fresh vector of the same 'const char*' (or of the same object pointers)
// is the same pool -- as a fresh list of the same objects is in Python; a
// fresh vector of equal 'std::string's is not.
//
// 'gauss' is the one path through libm: a last bit may differ between
// platforms, so a GOOD that prints a draw tolerates the last digits.
// _____________________________________________________________________________
#ifndef HWUT_DETERMINISTIC_RANDOM_HPP
#define HWUT_DETERMINISTIC_RANDOM_HPP

#include <cstdint>
#include <cstddef>
#include <limits>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/types.h>
namespace hwut { namespace c {       // the C core, out of the global namespace
extern "C" {
#include "../c/deterministic_random.h"
}
} }

namespace hwut {

class SelectionMarker {
public:
    SelectionMarker()  { c::SelectionMarker_init(&c_); }
    void reset()       { c::SelectionMarker_reset(&c_); }
    c::SelectionMarker* c() { return &c_; }
private:
    c::SelectionMarker c_;
};

class DeterministicStream {
public:
    static constexpr double INF = std::numeric_limits<double>::infinity();

    explicit DeterministicStream(int64_t seed = 0x42) { c::DeterministicStream_init(&c_, seed); }

    int64_t next_int(int64_t v_min, int64_t v_max);
    double  next_float();
    bool    coin(double probability_of_true);
    double  gauss(double mu, double sigma, double lower = -INF, double upper = INF);
    int64_t gauss_int(double mu, double sigma, double lower = -INF, double upper = INF);
    std::vector<size_t> sample_indices(size_t population_size, size_t k);

    template <class Sequence>
    auto select(const Sequence& candidates) -> decltype(candidates[0])
    /* RETURN: an element of 'candidates' (a vector, array or string),
     *         uniformly drawn; std::invalid_argument where it is empty.   */
    { return candidates[index_into(std::size(candidates))]; }

    template <class Sequence>
    auto choice(const Sequence& seq) -> decltype(seq[0])
    /* RETURN: as 'select' -- Python's 'choice'.                            */
    { return seq[index_into(std::size(seq))]; }

    template <class T>
    std::vector<T> sample(const std::vector<T>& population, size_t n)
    /* RETURN: 'n' distinct elements of 'population' (by place), in the order
     *         'sample_indices' draws their places.                         */
    {
        std::vector<T> result;
        for(size_t i : sample_indices(population.size(), n)) result.push_back(population[i]);
        return result;
    }

    template <class T>
    const T& select_unchosen(const std::vector<T>& candidates, SelectionMarker& marker)
    /* RETURN: a candidate the marker has not seen (by identity, see the
     *         header), uniformly drawn among those, and now recorded; where
     *         every one was seen, the marker is reset and the draw is over
     *         all. std::invalid_argument where 'candidates' is empty.      */
    {
        std::vector<const void*> identity;
        if( candidates.empty() ) throw std::invalid_argument("select_unchosen: no candidates");
        for(const T& x : candidates) identity.push_back(identity_of(x));
        const void* chosen = c::DeterministicStream_select_unchosen(&c_, identity.data(), identity.size(), marker.c());
        for(size_t i = 0; i < identity.size(); ++i) if( identity[i] == chosen ) return candidates[i];
        return candidates[0];                                        // not reached
    }

    c::DeterministicStream* c() { return &c_; }

private:
    size_t index_into(size_t candidate_n);

    template <class T>
    static const void* identity_of(const T& x)
    {
        if constexpr( std::is_pointer<T>::value ) return static_cast<const void*>(x);
        else                                      return static_cast<const void*>(&x);
    }

    c::DeterministicStream c_;
};

} // namespace hwut

#endif
