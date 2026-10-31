// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: A terminal's screen, read by a test -- see 'hwut_vterm.hpp'.
//
// A CALLBACK'S EXCEPTION DOES NOT CROSS THE C CORE: the shim keeps the first
// one; the Terminal call that drove the callbacks throws it on return.
// _____________________________________________________________________________
#include "hwut_vterm.hpp"

#include <cstdlib>
#include <cstring>
#include <exception>

using namespace hwut::c;

namespace hwut {
namespace vterm {

const char* const LIBRARY_VARIABLE = VTERM_LIBRARY_VARIABLE;
const char* const INSTALL_HINT     = VTERM_INSTALL_HINT;
const std::array<const char*, 7> ATTRIBUTE_NAME = { { "bold", "italic", "underline", "blink", "reverse",
                                                      "conceal", "strike" } };
const std::array<const char*, 7> ATTRIBUTE_SGR = { { "1", "3", "4", "5", "7", "8", "9" } };

namespace {

std::exception_ptr pending;          // what a callback threw, not yet rethrown

void
rethrow_pending()
/* RETURN: nothing where no callback threw; else what it threw is thrown
 *         again, and forgotten here.                                       */
{
    if( ! pending ) return;
    std::exception_ptr e = pending;
    pending = nullptr;
    std::rethrow_exception(e);
}

[[noreturn]] void
throw_error(const c::VtermError& error)
/* RETURN: never; the C error is thrown as the exception Python raises:
 *         'kind' picks the class, 'message' is its text.                   */
{
    std::string kind = error.kind, message = error.message;
    if( kind == "LibraryMissing" ) throw LibraryMissing(message);
    if( kind == "IndexError" )     throw IndexError(message);
    if( kind == "KeyError" )       throw KeyError(message);
    if( kind == "TimeoutError" )   throw TimeoutError(message);
    if( kind == "RuntimeError" )   throw RuntimeError(message);
    throw Error(kind, message);
}

Cell
cell_of(const c::VtermCell& c)
/* RETURN: the C++ cell holding what 'c' holds.                             */
{
    Cell cell;
    cell.text  = c.text;  cell.width = c.width;
    cell.bold_f    = c.bold_f;    cell.italic_f  = c.italic_f;  cell.underline_f = c.underline_f;
    cell.blink_f   = c.blink_f;   cell.reverse_f = c.reverse_f; cell.conceal_f   = c.conceal_f;
    cell.strike_f  = c.strike_f;
    if( c.foreground_f ) cell.foreground = Rgb{ { c.foreground[0], c.foreground[1], c.foreground[2] } };
    if( c.background_f ) cell.background = Rgb{ { c.background[0], c.background[1], c.background[2] } };
    return cell;
}

std::vector<std::string>
lines_taken(char** line_list, size_t line_n)
/* RETURN: the C lines as texts; the C list is given back.                  */
{
    std::vector<std::string> result(line_list, line_list + line_n);
    VtermTerminal_lines_free(line_list, line_n);
    return result;
}

} // namespace

/* --------------------------------------------------------- Cell, Event */
std::string
Cell::attribute_text() const
/* RETURN: the attributes that are set, by name and in one fixed order,
 *         separated by blanks -- 'bold reverse'; '' where none.           */
{
    const bool  set_f[7] = { bold_f, italic_f, underline_f, blink_f, reverse_f, conceal_f, strike_f };
    std::string result;
    for(size_t i = 0; i < 7; ++i)
        if( set_f[i] ) result += (result.empty() ? "" : " ") + std::string(ATTRIBUTE_NAME[i]);
    return result;
}

std::string
Event::to_string() const
/* RETURN: the event on one line, as a test prints it (Python's 'str').     */
{
    c::VtermEvent c = { kind.c_str(), row, column, row_end, column_end, name.c_str(),
                       value ? 1 : 0, value ? *value : 0 };
    char buffer[512];
    return VtermEvent_to_string(&c, buffer, sizeof(buffer));
}

std::string
detection_text()
/* RETURN: 'libvterm found: <name>' where the library loads; else the text
 *         of LibraryMissing -- what is wrong and how to install it.      */
{ char buffer[4096]; return Vterm_detection_text(buffer, sizeof(buffer)); }

void
reset_library()
/* RETURN: nothing; the library is looked for again at the next screen, and
 *         its layout measured again -- as 'hwut_vterm._library = None'.   */
{ Vterm_reset_library(); }

/* -------------------------------------------------------------- Screen */
Screen::Screen(int row_n, int column_n)
/* RETURN: Screen of 'row_n' rows and 'column_n' columns, blank, the cursor
 *         at (0, 0); throws LibraryMissing where libvterm is not found.  */
{
    c::VtermError error;
    std::memset(&error, 0, sizeof(error));
    screen_ = VtermScreen_new(row_n, column_n, &error);
    if( ! screen_ ) throw_error(error);
}

Screen::~Screen()
/* RETURN: nothing; the screen is closed and given back.                    */
{ if( screen_ ) VtermScreen_free(screen_); }

size_t
Screen::feed(const std::string& data)
/* RETURN: the number of bytes the terminal took -- all of them, where it
 *         works as documented. 'data' is what a program wrote (UTF-8).   */
{ return VtermScreen_feed(screen_, data.data(), data.size()); }

std::pair<int, int>
Screen::cursor()
/* RETURN: (row, column), the cursor's place, from 0.                       */
{
    int row, column;
    VtermScreen_cursor(screen_, &row, &column);
    return { row, column };
}

Cell
Screen::cell(int row, int column)
/* RETURN: what stands at that place; throws IndexError where the place is
 *         not on the screen.                                               */
{
    c::VtermCell c;
    if( VtermScreen_cell(screen_, row, column, &c) ) throw_error(screen_->error);
    return cell_of(c);
}

std::string
Screen::line(int row)
/* RETURN: the row's characters, blanks at its end dropped; a cell nothing
 *         was written to reads as a blank.                                */
{
    std::string buffer(32 * (size_t)screen_->column_n + 8, '\0');
    return VtermScreen_line(screen_, row, &buffer[0], buffer.size());
}

std::vector<std::string>
Screen::line_list()
/* RETURN: every row as 'line' gives it, top to bottom.                     */
{
    std::vector<std::string> result;
    for(int row = 0; row < screen_->row_n; ++row) result.push_back(line(row));
    return result;
}

void
Screen::close()
/* RETURN: nothing; the terminal's memory is freed -- a second call does
 *         nothing.                                                         */
{ VtermScreen_close(screen_); }

/* ------------------------------------------------------------ Terminal */
namespace {

c::VtermTerminal*
terminal_new(int row_n, int column_n, double settle_s)
/* RETURN: a new C terminal; throws LibraryMissing where libvterm is not
 *         found.                                                           */
{
    c::VtermError error;
    std::memset(&error, 0, sizeof(error));
    c::VtermTerminal* t = VtermTerminal_new(row_n, column_n, settle_s, &error);
    if( ! t ) throw_error(error);
    return t;
}

} // namespace

Terminal::Terminal(int row_n, int column_n, double settle_s)
/* RETURN: Terminal, blank, nothing running in it; throws LibraryMissing
 *         where libvterm is not found. 'settle_s' is how long the
 *         application must write nothing before its screen is taken as
 *         drawn.                                                           */
    : Terminal(terminal_new(row_n, column_n, settle_s))
{}

Terminal::Terminal(c::VtermTerminal* terminal)
/* RETURN: Terminal owning 'terminal'.                                      */
    : Screen(&terminal->base), terminal_(terminal)
{}

Terminal::~Terminal()
/* RETURN: nothing; an application still running is killed, the terminal
 *         closed and all it holds given back.                              */
{
    VtermTerminal_free(terminal_);
    screen_ = nullptr;                               // given back with it
}

[[noreturn]] void
Terminal::raise()
/* RETURN: never; the terminal's last error is thrown.                      */
{ throw_error(terminal_->base.error); }

void
Terminal::event_through(void* context, const c::VtermEvent* event)
/* RETURN: nothing; 'event' reached the callback 'context' points to.       */
{
    try {
        Event e;
        e.kind = event->kind;  e.row = event->row;  e.column = event->column;
        e.row_end = event->row_end;  e.column_end = event->column_end;
        if( event->name ) e.name = event->name;
        if( event->value_f || std::strcmp(event->kind, "property") ) e.value = event->value;
        (*static_cast<EventF*>(context))(e);
    } catch( ... ) {
        if( ! pending ) pending = std::current_exception();
    }
}

void
Terminal::change_through(void* context, const char* name, char** line_list, size_t line_n)
/* RETURN: nothing; the region's change reached the callback 'context'
 *         points to.                                                       */
{
    try {
        (*static_cast<ChangeF*>(context))(name, std::vector<std::string>(line_list, line_list + line_n));
    } catch( ... ) {
        if( ! pending ) pending = std::current_exception();
    }
}

void
Terminal::on_event(EventF callback)
/* RETURN: nothing; 'callback(event)' is called with every raw event from
 *         now on (at most VTERM_CALLBACK_MAX callbacks).                   */
{
    event_f_.push_back(std::move(callback));
    VtermTerminal_on_event(terminal_, event_through, &event_f_.back());
}

void
Terminal::on_change(ChangeF callback)
/* RETURN: nothing; 'callback(name, line_list)' is called for every region
 *         whose text changed, once the screen is quiet (at most
 *         VTERM_CALLBACK_MAX callbacks).                                   */
{
    change_f_.push_back(std::move(callback));
    VtermTerminal_on_change(terminal_, change_through, &change_f_.back());
}

void
Terminal::region(const std::string& name, int row, int row_n, int column, std::optional<int> column_n)
/* RETURN: nothing; the rectangle 'name' is observed from now on: 'row_n'
 *         rows from 'row', 'column_n' columns from 'column' -- to the right
 *         edge where nullopt. A NEGATIVE 'row' counts from the bottom: -1 is
 *         the last row. What stands there now is known, not news.        */
{ VtermTerminal_region(terminal_, name.c_str(), row, row_n, column, column_n ? *column_n : -1); }

std::vector<std::string>
Terminal::region_text(const std::string& name)
/* RETURN: the region's rows as they stand now, blanks at each row's end
 *         dropped; throws KeyError where no such region was declared.    */
{
    size_t line_n = 0;
    char** line   = VtermTerminal_region_text(terminal_, name.c_str(), &line_n);
    if( ! line ) raise();
    return lines_taken(line, line_n);
}

size_t
Terminal::report()
/* RETURN: the number of regions whose text differs from what was last told
 *         -- each told to every 'on_change' callback, in the order of
 *         declaration.                                                     */
{ size_t n = VtermTerminal_report(terminal_); rethrow_pending(); return n; }

size_t
Terminal::feed(const std::string& data)
/* RETURN: the number of bytes the terminal took; the raw events of what was
 *         fed fired before this returns, what the terminal answered went
 *         to the application, where one runs.                             */
{ size_t n = VtermTerminal_feed(terminal_, data.data(), data.size()); rethrow_pending(); return n; }

std::string
Terminal::answer()
/* RETURN: what the terminal said since the last call and no application
 *         took -- bytes.                                                   */
{
    size_t      length = 0;
    char*       data   = VtermTerminal_answer(terminal_, &length);
    std::string result(data ? data : "", data ? length : 0);
    std::free(data);
    return result;
}

bool
Terminal::send(const std::string& text, double react_s)
/* RETURN: true, the application still runs after 'text' (UTF-8) was typed
 *         character by character, as a keyboard sends it, and the screen
 *         read until quiet ('react_s' to begin answering); false, it does
 *         not.                                                             */
{ int r = VtermTerminal_send(terminal_, text.c_str(), react_s); rethrow_pending(); return r > 0; }

bool
Terminal::press(const std::string& key, const std::string& modifier, double react_s)
/* RETURN: true, the application still runs after 'key' was pressed; false,
 *         it does not; throws KeyError where 'key' or a modifier has no
 *         name here. 'key' is 'enter', 'up', 'f5', ... or one character;
 *         'modifier' names 'shift', 'alt', 'ctrl' separated by blanks.   */
{
    int r = VtermTerminal_press(terminal_, key.c_str(), modifier.empty() ? nullptr : modifier.c_str(), react_s);
    rethrow_pending();
    if( r < 0 ) raise();
    return r > 0;
}

bool
Terminal::run(const std::vector<std::string>& argv, const std::optional<std::string>& cwd, double start_s)
/* RETURN: true, the application 'argv' still runs once its first screen
 *         stands; false, it does not; throws RuntimeError where one was
 *         already run here. It is started on a pseudo-terminal of this
 *         terminal's size, in 'cwd' where given.                          */
{
    std::vector<char*> c_argv;
    for(const auto& a : argv) c_argv.push_back(const_cast<char*>(a.c_str()));
    c_argv.push_back(nullptr);
    int r = VtermTerminal_run(terminal_, c_argv.data(), cwd ? cwd->c_str() : nullptr, start_s);
    rethrow_pending();
    if( r < 0 ) raise();
    return r > 0;
}

bool
Terminal::pump(double first_s)
/* RETURN: true, the application still runs; false, it does not. READ UNTIL
 *         QUIET: up to 'first_s' for the application to write at all, then
 *         on until it wrote nothing for 'settle_s'; then the changed
 *         regions are reported.                                            */
{ int r = VtermTerminal_pump(terminal_, first_s); rethrow_pending(); return r > 0; }

std::pair<int, int>
Terminal::expect(const std::string& text, double timeout_s)
/* RETURN: (row, column) where 'text' stands on the screen (counted in
 *         characters); throws TimeoutError, carrying the screen, where it
 *         did not appear within 'timeout_s'.                               */
{
    int row = 0, column = 0;
    int r = VtermTerminal_expect(terminal_, text.c_str(), timeout_s, &row, &column);
    rethrow_pending();
    if( r < 0 ) raise();
    return { row, column };
}

std::optional<int>
Terminal::wait(double timeout_s)
/* RETURN: the application's exit status (negative: the signal that ended
 *         it), once it ended and its last words are on the screen; nullopt
 *         where no application was run; throws TimeoutError where it still
 *         ran after 'timeout_s' -- it is killed first.                     */
{
    int status = 0;
    int r = VtermTerminal_wait(terminal_, timeout_s, &status);
    rethrow_pending();
    if( r < 0 ) raise();
    if( r == 0 ) return std::nullopt;
    return status;
}

void
Terminal::close()
/* RETURN: nothing; an application still running is killed, the
 *         pseudo-terminal closed, the terminal's memory freed -- a second
 *         call does nothing.                                               */
{ VtermTerminal_close(terminal_); }

} // namespace vterm
} // namespace hwut
