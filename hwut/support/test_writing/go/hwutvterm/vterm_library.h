/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The C side of 'hwutvterm': libvterm loaded by 'dlopen', its
 *          functions called through the pointers 'dlsym' found, its callbacks
 *          handed on to Go ('vterm_library.c'). NO HEADER OF libvterm is
 *          needed: its few structures are declared here, as the Python
 *          binding declares them for 'ctypes'.
 * _____________________________________________________________________________
 */
#ifndef HWUT_GO_VTERM_LIBRARY_H
#define HWUT_GO_VTERM_LIBRARY_H

#include <stddef.h>
#include <stdint.h>

int    hv_load(const char* name, char* why, size_t why_size);
void   hv_unload(void);
int    hv_convert_f(void);

void*  hv_new(int row_n, int column_n);
void   hv_free(void* vt);
void*  hv_obtain_screen(void* vt);
void*  hv_obtain_state(void* vt);
size_t hv_input_write(void* vt, const char* data, size_t length);
void   hv_cursor(void* state, int* row, int* column);
void   hv_get_cell(void* screen, int row, int column, unsigned char* out, size_t out_size,
                   int convert_f, int foreground_i, int background_i);
void   hv_keyboard_unichar(void* vt, uint32_t code, int modifier);
void   hv_keyboard_key(void* vt, int key, int modifier);
void   hv_flush_damage(void* screen);
void*  hv_observe(void* vt, void* screen, uintptr_t handle);

#endif
