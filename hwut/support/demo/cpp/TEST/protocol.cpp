/* @hwut {
 *     title   = "Demo: an order law, stated as modes (a pype)"
 *     build   { framework = "make", target = "%.exe" }
 *     features = ["demo-cpp", "demo-cpp+cover-order-law-by-pype", "demo-cpp+cover-pype-owns-terminal-token"]
 *     choices { clean  { }
 *               broken { features = ["demo-cpp+cover-law-breach-verdict"] }
 *               slow   { features = ["demo-cpp+cover-pype-tick", "demo-cpp+cover-pype-time-guard"] } }
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * Five clients talk to a service at once, each a thread. The order of the
 * lines is the scheduler's. 'protocol.pype' holds the LAW -- every request
 * answered, once, before shutdown; nothing before its request; nothing after
 * shutdown -- and prints one verdict per exchange, sorted. The producer
 * reports as it happens and prints no '<hwut-end>': the pype's '<eof>' does
 * (pype manual 1b).
 *
 * THE PRODUCER IS THIS PROGRAM; the pype is started by it, its stdin a pipe
 * from this program, its stdout this program's -- what 'producer | hwut.pype
 * protocol.pype' does in the Python demonstration's 'protocol.sh'.
 *
 * 'broken' feeds the same pype a stream that breaks the law on purpose --
 * answered twice, never answered, an answer without its request, a request
 * after shutdown. The pype names each breach and says 'law: BROKEN'; that
 * report is the GOOD.
 *
 * 'slow' answers request 2 only after 3 s. The pype is fed LIVE, so its clock
 * is the service's: 'tick:' wakes it while no line arrives, and a wait guard
 * marks a request open for over 1 s as late.
 * _____________________________________________________________________________
 */
#include <chrono>
#include <cstdio>
#include <mutex>
#include <random>
#include <string>
#include <thread>
#include <vector>
#include <sys/wait.h>
#include <unistd.h>
#include <limits.h>

static std::string here()
/* RETURN: std::string, the directory this executable stands in. */
{
    char path[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", path, sizeof(path) - 1);
    std::string self = n > 0 ? std::string(path, (size_t)n) : std::string(".");
    size_t slash = self.rfind('/');
    return slash == std::string::npos ? "." : self.substr(0, slash);
}

static FILE* pype_open()
/* RETURN: FILE*, the stdin of 'hwut.pype protocol.pype', started; nullptr
 *         where it cannot be started.
 * THE PYPE IS THE FACE ON PATH in an installed hwut; in the clone, the
 * module 'hwut.services.pype' of the tree this directory stands in.      */
{
    const std::string script = "'" + here() + "/protocol.pype'";
    const std::string command =
        "if command -v hwut.pype > /dev/null 2>&1; then exec hwut.pype " + script + "; "
        "else ROOT=$(cd '" + here() + "/../../../../..' && pwd); "
        "export PYTHONPATH=\"$ROOT${PYTHONPATH:+:$PYTHONPATH}\"; "
        "exec python3 -m hwut.services.pype " + script + "; fi";
    std::fflush(stdout);
    return popen(command.c_str(), "w");
}

static void say(FILE* pype, std::mutex& lock, const std::string& text)
/* RETURN: nothing. 'text' given to the pype as one line, at once. */
{
    std::lock_guard<std::mutex> guard(lock);
    std::fprintf(pype, "%s\n", text.c_str());
    std::fflush(pype);
}

static void producer(FILE* pype)
/* RETURN: nothing. Five clients, each a thread, send a request and receive
 *         its response; then the service shuts down.                     */
{
    std::mutex lock;
    std::mt19937_64 rng((uint64_t)std::chrono::system_clock::now().time_since_epoch().count());
    std::uniform_int_distribution<int> delay_us(0, 20000);
    std::vector<std::thread> pool;
    for(int n = 1; n <= 5; ++n) {
        int before = delay_us(rng), between = delay_us(rng);
        pool.emplace_back([&, n, before, between] {
            std::this_thread::sleep_for(std::chrono::microseconds(before));
            say(pype, lock, "request " + std::to_string(n));
            std::this_thread::sleep_for(std::chrono::microseconds(between));
            say(pype, lock, "response " + std::to_string(n));
        });
    }
    for(auto& thread : pool) thread.join();
    say(pype, lock, "shutdown");
}

static void breaking(FILE* pype)
/* RETURN: nothing. A stream that breaks the law, four ways. */
{
    std::mutex lock;
    for(const char* line : { "request 1", "response 1", "response 1", "request 2",
                             "response 3", "shutdown", "request 4" })
        say(pype, lock, line);
}

static void slow(FILE* pype)
/* RETURN: nothing. Request 2 answered only after 3 s. */
{
    std::mutex lock;
    for(const char* line : { "request 1", "response 1", "request 2", "request 3", "response 3" })
        say(pype, lock, line);
    std::this_thread::sleep_for(std::chrono::seconds(3));
    say(pype, lock, "response 2");
    say(pype, lock, "shutdown");
}

int main(int argc, char** argv)
/* RETURN: int, the pype's exit status, the choice 'argv[1]' fed to it;
 *         1, where no known choice is named (the choices are printed)
 *            or the pype cannot be started.                              */
{
    const std::string choice = argc > 1 ? argv[1] : "";
    void (*feed)(FILE*) = choice == "clean"  ? producer
                        : choice == "broken" ? breaking
                        : choice == "slow"   ? slow
                        :                      nullptr;
    if( ! feed ) { std::printf("choices: clean, broken, slow\n"); return 1; }
    FILE* pype = pype_open();
    if( ! pype ) { std::perror("protocol.exe: popen"); return 1; }
    feed(pype);
    int status = pclose(pype);
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}
