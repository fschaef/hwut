/* @hwut {
 *     title      = "space_iterator: every combination of a parameter basis"
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         product { features = ["cpp-space"] }
 *         edges   { features = ["cpp-space"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The C++ port of 'python/TEST/test-space-iterator.py', held against
 *          its GOOD files by '.link'. The basis is one of strings; the
 *          points are vectors of them.
 * _____________________________________________________________________________
 */
#include <cstdio>
#include <string>
#include <vector>
#include "hwut_runner.hpp"
#include "space_iterator.hpp"

using Basis = std::vector<std::vector<std::string>>;

static void banner(const std::string& label) { std::printf("\n--- %s ---\n", label.c_str()); }

static void
points(const Basis& basis)
{
    int n = 0;
    for(const auto& point : hwut::space_iterator::do_(basis)) {
        std::string text;
        for(size_t i = 0; i < point.size(); ++i) text += (i ? ", " : "") + point[i];
        std::printf("  (%s)\n", text.c_str());
        n += 1;
    }
    std::printf("  %d point(s)\n", n);
}

int
main(int argc, char** argv)
{
    hwut::HwutRunner runner(argc, argv, "space_iterator: every combination of a parameter basis", {
        { "product", [] {
            banner("[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points");
            points({ { "0", "2", "4" }, { "otto", "heinz" }, { "1", "2" } });
        } },
        { "edges", [] {
            banner("an EMPTY basis -- one point, the empty one");
            points({});
            banner("a basis with an EMPTY dimension -- nothing");
            points({ { "1", "2" }, {}, { "3" } });
            banner("ONE dimension -- its values one by one");
            points({ { "a", "b", "c" } });
        } },
    });
    return runner.run();
}
