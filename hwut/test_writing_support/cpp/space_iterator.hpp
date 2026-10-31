// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: EVERY COMBINATION OF A PARAMETER BASIS -- the port of
//          'python/space_iterator.py', a thin face over '../c/space_iterator.c':
//          the cartesian product, the RIGHTMOST dimension changing fastest.
//
//     std::vector<std::vector<int>> basis = { { 0, 2, 4 }, { 1, 2 } };
//     for(const std::vector<int>& point : hwut::space_iterator::do_(basis))
//         run_test(point[0], point[1]);
//
// 'do_' is Python's 'do' ('do' is a C++ keyword). Its points are values of
// one type T; for a basis of mixed types iterate the INDICES:
//
//     hwut::SpaceIterator it({ 3, 2 });
//     std::vector<size_t> at;
//     while( it.next(at) ) run_test(x[at[0]], name[at[1]]);
//
// An empty basis yields exactly one point, the empty one; a basis with an
// empty dimension yields nothing -- as 'itertools.product'.
// _____________________________________________________________________________
#ifndef HWUT_SPACE_ITERATOR_HPP
#define HWUT_SPACE_ITERATOR_HPP

#include <cstddef>
#include <iterator>
#include <utility>
#include <stdexcept>
#include <vector>

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/types.h>
namespace hwut { namespace c {       // the C core, out of the global namespace
extern "C" {
#include "../c/space_iterator.h"
}
} }

namespace hwut {

class SpaceIterator {
public:
    explicit SpaceIterator(const std::vector<size_t>& size)
    /* RETURN: SpaceIterator before the first point of a basis whose
     *         dimensions have 'size' values each; std::invalid_argument for
     *         more than SPACE_ITERATOR_DIMENSION_MAX dimensions.          */
    {
        if( size.size() > SPACE_ITERATOR_DIMENSION_MAX ) throw std::invalid_argument("SpaceIterator: too many dimensions");
        c::SpaceIterator_init(&c_, size.data(), size.size());
    }

    bool next(std::vector<size_t>& at)
    /* RETURN: true, 'at' holds the next point -- one index per dimension;
     *         false, every point was given ('at' unchanged).              */
    {
        size_t index[SPACE_ITERATOR_DIMENSION_MAX];
        if( ! c::SpaceIterator_next(&c_, index) ) return false;
        at.assign(index, index + c_.dimension_n);
        return true;
    }

private:
    c::SpaceIterator c_;
};

namespace space_iterator {

template <class T>
class Product {
public:
    using Basis = std::vector<std::vector<T>>;

    class iterator {
    public:
        using iterator_category = std::input_iterator_tag;
        using value_type        = std::vector<T>;
        using difference_type   = std::ptrdiff_t;
        using pointer           = const value_type*;
        using reference         = const value_type&;

        iterator() = default;
        iterator(const Basis* basis) : basis_(basis), it_(new SpaceIterator(sizes(*basis))) { step(); }
        iterator(const iterator& other)
            : basis_(other.basis_), it_(other.it_ ? new SpaceIterator(*other.it_) : nullptr), point_(other.point_) {}
        iterator& operator=(iterator other) { std::swap(basis_, other.basis_); std::swap(it_, other.it_); point_.swap(other.point_); return *this; }
        ~iterator() { delete it_; }

        reference  operator*()  const { return point_; }
        pointer    operator->() const { return &point_; }
        iterator&  operator++()       { step(); return *this; }
        bool operator==(const iterator& other) const { return basis_ == other.basis_; }
        bool operator!=(const iterator& other) const { return basis_ != other.basis_; }

    private:
        static std::vector<size_t> sizes(const Basis& basis)
        { std::vector<size_t> n; for(const auto& d : basis) n.push_back(d.size()); return n; }

        void step()
        /* RETURN: nothing; 'point_' is the next point, or the iterator is
         *         the end (basis_ nullptr) once every point was given.     */
        {
            std::vector<size_t> at;
            if( ! it_->next(at) ) { basis_ = nullptr; return; }
            point_.clear();
            for(size_t i = 0; i < at.size(); ++i) point_.push_back((*basis_)[i][at[i]]);
        }

        const Basis*   basis_ = nullptr;
        SpaceIterator* it_    = nullptr;
        value_type     point_;
    };

    explicit Product(Basis basis) : basis_(std::move(basis)) {}
    iterator begin() const { return iterator(&basis_); }
    iterator end()   const { return iterator(); }

private:
    Basis basis_;
};

template <class T>
Product<T>
do_(std::vector<std::vector<T>> basis)
/* RETURN: the points of the cartesian product of 'basis' -- a range of
 *         std::vector<T>, one value per dimension, the rightmost fastest. */
{ return Product<T>(std::move(basis)); }

} // namespace space_iterator
} // namespace hwut

#endif
