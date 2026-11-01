/* drive.c -- per stdin line: a case number and the block in hex ('-' empty).
 * The block is copied to the END of a page whose successor page is
 * PROT_NONE (the Electric-Fence trick): the first byte read past the block
 * faults. The fault is caught (SIGSEGV -> siglongjmp), the case is reported
 * as an overread, and the run goes on with the next case.
 * Prints 'case result' with result = records, -1 rejected, or 'OVERREAD'. */
#include <setjmp.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
int tlv_walk(const uint8_t *buf, size_t len, unsigned *sum);

static sigjmp_buf fence;
static void on_fault(int sig) { (void)sig; siglongjmp(fence, 1); }

int main(void)
{
    long page = sysconf(_SC_PAGESIZE);
    uint8_t *area = mmap(NULL, 2 * page, PROT_READ | PROT_WRITE,
                         MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    mprotect(area + page, page, PROT_NONE);
    struct sigaction sa = { 0 };
    sa.sa_handler = on_fault;
    sigaction(SIGSEGV, &sa, NULL);

    char line[4096];
    while (fgets(line, sizeof line, stdin)) {
        int k; char hex[4000] = "";
        if (sscanf(line, "%d %3999s", &k, hex) < 1) continue;
        if (strcmp(hex, "-") == 0) hex[0] = 0;
        size_t len = strlen(hex) / 2;
        uint8_t *buf = area + page - len;              /* ends at the fence */
        for (size_t i = 0; i < len; ++i) sscanf(hex + 2 * i, "%2hhx", &buf[i]);
        unsigned sum;
        if (sigsetjmp(fence, 1) == 0) printf("%d %d\n", k, tlv_walk(buf, len, &sum));
        else                          printf("%d OVERREAD\n", k);
    }
    return 0;
}
