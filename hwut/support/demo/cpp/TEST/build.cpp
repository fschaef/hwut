/* @hwut {
 *     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
 *     build   { framework = "make", executable = "%.exe" }
 *     pype    = "build.pypes"
 *     same    = true
 *     choices = ["serial", "parallel"]
 *     features = ["pype-in-header", "pype-system", "same-nominal", "choices-as-list",
 *                 "pype-push-pop", "pype-entry-exit", "pype-import", "pype-repeat-group",
 *                 "pype-quantity", "pype-anchors-globs-flush"]
 *     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * SUBJECT  the log of a recursive build -- configure, then the directories
 *          'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
 *          a pype system makes of it.
 * REQUIREMENT  A parallel build builds what the serial build builds: the same
 *              sources, the same warnings, the same archives and the same
 *              program, linked from the same parts.
 *
 * The application only REPORTS the build as it happens, as 'make -w' would.
 * The header's 'pype = "build.pypes"' puts a SYSTEM of two pype scripts
 * between it and the comparison (hwut runs it; the application prints no
 * '<hwut-end>'):
 *
 *     build.pypes       --> normalise.pype --> build.pype
 *     normalise.pype    the job tag of a parallel build goes ('flush')
 *     build.pype        the summary, sorted: modes pushed and popped over
 *                       nested directories, '<entry>'/'<exit>', a vocabulary
 *                       imported from 'compiler.pype', a repeat group,
 *                       durations read as quantities
 *
 * 'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.cpp.link'. Serial or
 * parallel, the summary must be the same. 'choices' is a list.
 *
 * The laws: the compile times sum to under 5 s, and nothing in the log broke
 * the build's grammar ('((breaches: 0))').
 * _____________________________________________________________________________
 */
#include <chrono>
#include <cstdio>
#include <map>
#include <mutex>
#include <random>
#include <string>
#include <thread>
#include <vector>

struct Directory {
    std::vector<std::string>           source_list;
    std::map<std::string, std::string> warning_db;
    std::string                        product;
};

//  What each directory does: its sources, warnings and products.
static const std::map<std::string, Directory> DIRECTORY_DB = {
    { "lib",         { { "lib/str.c", "lib/num.c", "lib/map.c" },
                       { { "lib/num.c", "lib/num.c:14:9: warning: unused variable 'n'" } },
                       "ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o" } },
    { "app/plugins", { { "app/plugins/png.c", "app/plugins/svg.c" },
                       { { "app/plugins/svg.c", "app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'" } },
                       "ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o" } },
    { "app",         { { "app/main.c", "app/cli.c" },
                       { },
                       "ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a" } },
};

static std::mt19937_64 rng;
static std::mutex      rng_lock;

static double took_s()
/* RETURN: double, how long one compilation takes, in s: from [0.04, 0.12). */
{
    std::lock_guard<std::mutex> guard(rng_lock);
    return std::uniform_real_distribution<double>(0.04, 0.12)(rng);
}

static std::vector<std::string> compile_lines(const std::string& name)
/* RETURN: what building directory 'name' prints, its sources compiled in
 *         the time each takes.                                           */
{
    const Directory& spec = DIRECTORY_DB.at(name);
    std::vector<std::string> line_list;
    char line[256];
    for(const std::string& source : spec.source_list) {
        double took = took_s();
        std::this_thread::sleep_for(std::chrono::duration<double>(took));
        char spent[32];
        if( took < 0.1 ) std::snprintf(spent, sizeof(spent), "%d ms", (int)(took * 1000));
        else             std::snprintf(spent, sizeof(spent), "%.2f s", took);
        std::string object = source.substr(0, source.size() - 2) + ".o";
        std::snprintf(line, sizeof(line), "cc -c %s -o %s (took %s)", source.c_str(), object.c_str(), spent);
        line_list.push_back(line);
        auto warning = spec.warning_db.find(source);
        if( warning != spec.warning_db.end() ) line_list.push_back(warning->second);
    }
    return line_list;
}

static std::vector<std::string> directory_block(const std::string& name, int level, const std::string& inner = "")
/* RETURN: the block 'make -w' prints for 'name' at 'level', the block of
 *         'inner' nested before the product.                             */
{
    std::vector<std::string> line_list = { "make[" + std::to_string(level) + "]: Entering directory '" + name + "'" };
    for(const std::string& line : compile_lines(name)) line_list.push_back(line);
    if( ! inner.empty() )
        for(const std::string& line : directory_block(inner, level + 1)) line_list.push_back(line);
    line_list.push_back(DIRECTORY_DB.at(name).product);
    line_list.push_back("make[" + std::to_string(level) + "]: Leaving directory '" + name + "'");
    return line_list;
}

static void configure()
/* RETURN: nothing. Prints what 'configure' prints, and that make enters the
 *         top directory.                                                 */
{
    std::printf("configure: checking for cc... cc\n");
    std::printf("configure: checking for ar... ar\n");
    std::printf("make: Entering directory 'demo'\n");
    std::fflush(stdout);
}

static void serial()
/* RETURN: nothing. Builds one directory after the other. */
{
    configure();
    for(const char* name : { "lib", "app" }) {
        for(const std::string& line : directory_block(name, 1, name == std::string("app") ? "app/plugins" : "")) {
            std::printf("%s\n", line.c_str());
            std::fflush(stdout);
        }
    }
    std::printf("make: Leaving directory 'demo'\n");
}

static void parallel()
/* RETURN: nothing. Builds 'lib' and 'app' at once. Each job prints its block
 *         whole when done ('make -O'), every line tagged with the job;
 *         which job finishes first is the scheduler's.                   */
{
    configure();
    std::mutex lock;
    auto job = [&](int slot, const std::string& name, const std::string& inner) {
        std::vector<std::string> block = directory_block(name, 1, inner);
        std::lock_guard<std::mutex> guard(lock);
        for(const std::string& line : block) {
            std::printf("job%d: %s\n", slot, line.c_str());
            std::fflush(stdout);
        }
    };
    std::thread first(job, 1, "lib", ""), second(job, 2, "app", "app/plugins");
    first.join();
    second.join();
    std::printf("make: Leaving directory 'demo'\n");
}

int main(int argc, char** argv)
/* RETURN: 0, the build log of the choice 'argv[1]' printed;
 *         1, where no known choice is named (the choices are printed).   */
{
    rng.seed((uint64_t)std::chrono::system_clock::now().time_since_epoch().count());
    const std::string choice = argc > 1 ? argv[1] : "";
    if     ( choice == "serial" )   serial();
    else if( choice == "parallel" ) parallel();
    else { std::printf("choices: serial, parallel\n"); return 1; }
    return 0;
}
