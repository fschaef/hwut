/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: WHAT 'hwut_runner.sv' WANTS OF THE OPERATING SYSTEM, through DPI-C:
 *          the command line, the end of the process, and -- for the
 *          interactive protocol -- the UP channel, a line of stdin, a child
 *          process per choice and its exit status. SystemVerilog has none of
 *          these; everything else of the runner (the info block, the
 *          dispatch, the protocol's words) is SystemVerilog.
 *
 * THE COMMAND LINE is read from '/proc/self/cmdline': the simulator's 'main'
 * keeps 'argv' to itself, and '$value$plusargs' sees '+name=value' alone,
 * while hwut calls 'test-x.exe <choice>', '--hwut-info', '--interactive'.
 *
 * THE END is '_exit' after both streams are flushed: the simulation does not
 * run to '$finish' (which would print its own line), and no destructor of a
 * suspended SystemVerilog process runs.
 * _____________________________________________________________________________
 */
#define _POSIX_C_SOURCE 200809L
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static char  _cmdline[1 << 16];
static char* _argv[256];
static int   _argc = -1;
static int   _control_fd = -1;

static void
_load(void)
/* RETURN: nothing; '_argv' holds the words of this process's command line,
 *         '_argc' their number (0 where '/proc' cannot be read).            */
{
    FILE*  file;
    size_t n = 0, i = 0;
    if( _argc >= 0 ) return;
    _argc = 0;
    if( (file = fopen("/proc/self/cmdline", "rb")) == NULL ) return;
    n = fread(_cmdline, 1, sizeof(_cmdline) - 1, file);
    fclose(file);
    _cmdline[n] = '\0';
    while( i < n && _argc < 256 ) { _argv[_argc++] = _cmdline + i; i += strlen(_cmdline + i) + 1; }
}

int
hwut_sv_argc(void)
/* RETURN: the number of words on the command line, the program's name the
 *         first.                                                           */
{ _load(); return _argc; }

const char*
hwut_sv_argv(int i)
/* RETURN: the i-th word of the command line; '' where there is none.       */
{ _load(); return i >= 0 && i < _argc ? _argv[i] : ""; }

void
hwut_sv_exit(int status)
/* RETURN: never; stdout and stderr are flushed, the process ends with
 *         'status'.                                                        */
{ fflush(stdout); fflush(stderr); _exit(status); }

void
hwut_sv_flush(void)
/* RETURN: nothing; stdout and stderr are flushed.                          */
{ fflush(stdout); fflush(stderr); }

int
hwut_sv_env_defined(const char* name)
/* RETURN: 1 where the environment holds 'name'; 0 else.                    */
{ return getenv(name) != NULL; }

int
hwut_sv_interactive_begin(void)
/* RETURN: 0; the original stdout is the UP channel, fd 1 and fd 2 point at
 *         a stray sink -- what a choice's run does not send to its own
 *         sinks is not mistaken for the protocol.                          */
{
    char path[] = "/tmp/hwut_stray_XXXXXX";
    int  stray;
    fflush(stdout); fflush(stderr);
    _control_fd = dup(1);
    stray = mkstemp(path);
    if( stray >= 0 ) { dup2(stray, 1); dup2(stray, 2); close(stray); }
    return 0;
}

void
hwut_sv_up(const char* message)
/* RETURN: nothing; 'message' and a newline are written on the UP channel.  */
{
    size_t n = strlen(message);
    if( write(_control_fd, message, n) < 0 || write(_control_fd, "\n", 1) < 0 ) {}
}

int
hwut_sv_read_line(const char** line)
/* RETURN: 1, '*line' is the next line of stdin without its trailing blanks
 *         and newline; 0, the input has ended.                             */
{
    static char*  buffer = NULL;
    static size_t capacity = 0;
    ssize_t       got = getline(&buffer, &capacity, stdin);
    if( got < 0 ) { *line = ""; return 0; }
    while( got > 0 && isspace((unsigned char)buffer[got - 1]) ) buffer[--got] = '\0';
    *line = buffer;
    return 1;
}

int
hwut_sv_fork_into_sinks(const char* sink_out, const char* sink_err)
/* RETURN: 0 in the CHILD, whose stdout and stderr now write 'sink_out' and
 *         'sink_err' (an unopenable sink ends the child with 1); the
 *         child's pid in the parent; -1 where no child could be made.       */
{
    int pid;
    fflush(stdout); fflush(stderr);
    pid = fork();
    if( pid != 0 ) return pid;
    {
        int out = open(sink_out, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        int err = open(sink_err, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if( out < 0 || err < 0 ) _exit(1);
        dup2(out, 1); dup2(err, 2); close(out); close(err);
        if( _control_fd >= 0 ) close(_control_fd);
        _control_fd = -1;
    }
    return 0;
}

int
hwut_sv_reap(int pid, int block_f, int* status)
/* RETURN: the pid of a child that ended -- 'pid', or any where 'pid' is -1
 *         -- and '*status' its exit status (minus the signal that ended
 *         it); 0 where none has ended and 'block_f' is 0; -1 where no child
 *         is left to wait for.                                             */
{
    int raw, got;
    do got = waitpid(pid, &raw, block_f ? 0 : WNOHANG); while( got < 0 && errno == EINTR );
    if( got <= 0 ) return got;
    if( WIFEXITED(raw) )        *status = WEXITSTATUS(raw);
    else if( WIFSIGNALED(raw) ) *status = -WTERMSIG(raw);
    else                        *status = 1;
    return got;
}
