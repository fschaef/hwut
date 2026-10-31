// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- the port of
//          'python/hwut_vterm.py', a thin face over '../c/hwut_vterm.c':
//          libvterm, loaded at run time.
//
//     try {
//         hwut::vterm::Screen screen(24, 80);
//         screen.feed("\x1b[1mbold\x1b[0m plain");
//         screen.line(0);                       -- "bold plain"
//         screen.cell(0, 0).bold_f;             -- true
//     } catch( const hwut::vterm::LibraryMissing& error ) {
//         std::printf("NOT PROBED: %s\n", error.what());
//     }
//
// NO HEADER OF THE LIBRARY IS NEEDED to build this: the library is FOUND at
// run time -- under the name HWUT_LIBVTERM gives, or as the system knows it
// ('libvterm.so.0'; Debian: 'libvterm0'). Where neither loads, a constructor
// throws LibraryMissing, whose text says how to install it.
//
// TWO CLASSES:
//     Screen      the grid alone: bytes in, cells out. No process.
//     Terminal    a Screen an APPLICATION RUNS IN, on a pseudo-terminal it
//                 cannot tell from a person's; observed by callbacks
//                 ('on_event', 'on_change') that may be lambdas.
//
// EXCEPTIONS, Python's: LibraryMissing, KeyError, TimeoutError, RuntimeError
// derive from hwut::vterm::Error (whose 'kind()' is Python's name); a place
// off the screen throws hwut::vterm::IndexError, a std::out_of_range.
// Their what() is Python's text.
// _____________________________________________________________________________
#ifndef HWUT_VTERM_HPP
#define HWUT_VTERM_HPP

#include <array>
#include <cstdint>
#include <functional>
#include <list>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include <sys/types.h>

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/types.h>
namespace hwut { namespace c {       // the C core, out of the global namespace
extern "C" {
#include "../c/hwut_vterm.h"
}
} }

namespace hwut {
namespace vterm {

extern const char* const LIBRARY_VARIABLE;              // "HWUT_LIBVTERM"
extern const char* const INSTALL_HINT;
extern const std::array<const char*, 7> ATTRIBUTE_NAME; // bold italic underline blink reverse conceal strike
extern const std::array<const char*, 7> ATTRIBUTE_SGR;  // "1" "3" "4" "5" "7" "8" "9"

class Error : public std::runtime_error {
public:
    Error(std::string kind, const std::string& message) : std::runtime_error(message), kind_(std::move(kind)) {}
    const std::string& kind() const { return kind_; }
private:
    std::string kind_;
};
struct LibraryMissing : Error { explicit LibraryMissing(const std::string& m) : Error("LibraryMissing", m) {} };
struct KeyError       : Error { explicit KeyError(const std::string& m)       : Error("KeyError", m) {} };
struct TimeoutError   : Error { explicit TimeoutError(const std::string& m)   : Error("TimeoutError", m) {} };
struct RuntimeError   : Error { explicit RuntimeError(const std::string& m)   : Error("RuntimeError", m) {} };
struct IndexError     : std::out_of_range { explicit IndexError(const std::string& m) : std::out_of_range(m) {} };

using Rgb = std::array<uint8_t, 3>;

struct Cell {
    std::string        text;            // UTF-8; '' unwritten, and the right half of a wide one
    int                width = 1;
    bool               bold_f = false, italic_f = false, underline_f = false, blink_f = false,
                       reverse_f = false, conceal_f = false, strike_f = false;
    std::optional<Rgb> foreground;      // nullopt: the default
    std::optional<Rgb> background;
    std::string attribute_text() const; // 'bold reverse'; '' where none
};

struct Event {                          // ONE THING THE TERMINAL DID (the RAW layer)
    std::string        kind;            // "damage", "cursor", "property", "bell"
    int                row = 0, column = 0, row_end = 0, column_end = 0;
    std::string        name;            // a property's
    std::optional<int> value;           // nullopt where a property's value is a text
    std::string to_string() const;      // the event on one line, as a test prints it
};

std::string detection_text();
void        reset_library();

class Screen {
public:
    explicit Screen(int row_n = 24, int column_n = 80);
    virtual ~Screen();
    Screen(const Screen&)            = delete;
    Screen& operator=(const Screen&) = delete;

    int                      row_n() const    { return screen_->row_n; }
    int                      column_n() const { return screen_->column_n; }
    virtual size_t           feed(const std::string& data);
    std::pair<int, int>      cursor();
    Cell                     cell(int row, int column);
    std::string              line(int row);
    std::vector<std::string> line_list();
    virtual void             close();

    c::VtermScreen* c() { return screen_; }

protected:
    explicit Screen(c::VtermScreen* screen) : screen_(screen) {}
    c::VtermScreen* screen_;
};

class Terminal : public Screen {
public:
    using EventF  = std::function<void(const Event& event)>;
    using ChangeF = std::function<void(const std::string& name, const std::vector<std::string>& line_list)>;

    explicit Terminal(int row_n = 24, int column_n = 80, double settle_s = 0.1);
    ~Terminal() override;

    void                     on_event(EventF callback);
    void                     on_change(ChangeF callback);
    void                     region(const std::string& name, int row, int row_n = 1, int column = 0,
                                    std::optional<int> column_n = std::nullopt);
    std::vector<std::string> region_text(const std::string& name);
    size_t                   report();
    size_t                   feed(const std::string& data) override;
    std::string              answer();
    bool                     send(const std::string& text, double react_s = 1.0);
    bool                     press(const std::string& key, const std::string& modifier = "", double react_s = 1.0);
    bool                     run(const std::vector<std::string>& argv, const std::optional<std::string>& cwd = std::nullopt,
                                 double start_s = 10.0);
    bool                     pump(double first_s = 1.0);
    std::pair<int, int>      expect(const std::string& text, double timeout_s = 10.0);
    std::optional<int>       wait(double timeout_s = 10.0);
    void                     close() override;

    c::VtermTerminal* c_terminal() { return terminal_; }

private:
    explicit Terminal(c::VtermTerminal* terminal);
    static void event_through(void* context, const c::VtermEvent* event);
    static void change_through(void* context, const char* name, char** line_list, size_t line_n);
    [[noreturn]] void raise();

    c::VtermTerminal*   terminal_;
    std::list<EventF>  event_f_;        // a list: the C core holds their addresses
    std::list<ChangeF> change_f_;
};

} // namespace vterm
} // namespace hwut

#endif
