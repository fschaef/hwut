#include <stddef.h>
#include <stdint.h>
enum { HDR_OK, HDR_VERSION, HDR_HDRLEN, HDR_TOTLEN, HDR_TRUNCATED, HDR_TYPE };
int hdr_check(const uint8_t *buf, size_t received);
