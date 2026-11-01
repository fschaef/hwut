// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: THE FEW C FUNCTIONS the support calls that Rust's 'std' does not
//          offer -- declared here, by hand, since no crate is used: the
//          process ('fork', 'waitpid', '_exit'), descriptors ('dup2'), the
//          pseudo-terminal ('openpty', 'ioctl', 'setsid', 'poll') and the
//          loader ('dlopen', 'dlsym'). Linux, glibc: the constants are its.
//______________________________________________________________________________
#![allow(non_camel_case_types, dead_code)]

use std::os::raw::{c_char, c_int, c_long, c_short, c_uint, c_ulong, c_void};

pub type pid_t = c_int;

pub const O_WRONLY: c_int = 0o1;
pub const O_CREAT:  c_int = 0o100;
pub const O_TRUNC:  c_int = 0o1000;
pub const WNOHANG:  c_int = 1;
pub const EINTR:    c_int = 4;
pub const SIGKILL:  c_int = 9;
pub const SIGPIPE:  c_int = 13;
pub const SIG_DFL:  usize = 0;
pub const POLLIN:   c_short = 1;
pub const RTLD_NOW: c_int = 2;
pub const TIOCSWINSZ: c_ulong = 0x5414;
pub const TIOCSCTTY:  c_ulong = 0x540E;

#[repr(C)]
pub struct pollfd { pub fd: c_int, pub events: c_short, pub revents: c_short }

#[repr(C)]
pub struct winsize { pub ws_row: u16, pub ws_col: u16, pub ws_xpixel: u16, pub ws_ypixel: u16 }

extern "C" {
    pub fn fork() -> pid_t;
    pub fn _exit(status: c_int) -> !;
    pub fn waitpid(pid: pid_t, status: *mut c_int, options: c_int) -> pid_t;
    pub fn kill(pid: pid_t, signal: c_int) -> c_int;
    pub fn open(path: *const c_char, flags: c_int, mode: c_uint) -> c_int;
    pub fn close(fd: c_int) -> c_int;
    pub fn dup(fd: c_int) -> c_int;
    pub fn dup2(fd: c_int, fd2: c_int) -> c_int;
    pub fn read(fd: c_int, buffer: *mut c_void, n: usize) -> isize;
    pub fn write(fd: c_int, buffer: *const c_void, n: usize) -> isize;
    pub fn mkstemp(template: *mut c_char) -> c_int;
    pub fn setsid() -> pid_t;
    pub fn ioctl(fd: c_int, request: c_ulong, ...) -> c_int;
    pub fn poll(fds: *mut pollfd, n: c_ulong, timeout_ms: c_int) -> c_int;
    pub fn signal(signal: c_int, handler: usize) -> usize;
    pub fn chdir(path: *const c_char) -> c_int;
    pub fn execvpe(file: *const c_char, argv: *const *const c_char, envp: *const *const c_char) -> c_int;
    pub fn __errno_location() -> *mut c_int;
    pub fn strerror(errno: c_int) -> *const c_char;
    pub fn usleep(us: c_uint) -> c_int;
    pub fn sysconf(name: c_int) -> c_long;
}

#[link(name = "util")]
extern "C" {
    pub fn openpty(master: *mut c_int, slave: *mut c_int, name: *mut c_char,
                   termios: *const c_void, size: *const winsize) -> c_int;
}

#[link(name = "dl")]
extern "C" {
    pub fn dlopen(file: *const c_char, mode: c_int) -> *mut c_void;
    pub fn dlsym(handle: *mut c_void, name: *const c_char) -> *mut c_void;
    pub fn dlclose(handle: *mut c_void) -> c_int;
    pub fn dlerror() -> *mut c_char;
}

/// RETURN: c_int, the 'errno' of the calling thread.
pub fn errno() -> c_int { unsafe { *__errno_location() } }

/// RETURN: i32, the exit status a child ended with, from waitpid's 'status';
///         minus the signal that ended it.
pub fn exit_code_of(status: c_int) -> i32 {
    let signal = status & 0x7f;
    if signal == 0 { (status >> 8) & 0xff }          // WIFEXITED
    else if signal != 0x7f { -signal }                // WIFSIGNALED
    else { 1 }
}
