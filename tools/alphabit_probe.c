/*
 * alphabit_probe.c -- Phase 0 feasibility probe for TestU01 Alphabit.
 *
 * Usage:  alphabit_probe <bit_file> <nb_bits>
 *
 *   <bit_file>  binary file of FULLY PACKED bits: 8 data bits per byte,
 *               so nb_bits / 8 bytes total. TestU01 reads it via
 *               ufile_CreateReadBin(), which consumes 4 bytes at a time
 *               as one 32-bit word. Produce it from a 0/1 array with
 *               numpy.packbits (MSB-first). Do NOT write one byte per
 *               bit -- that layout is wrong and yields garbage p-values.
 *   <nb_bits>   number of bits to consume from the file.
 *
 * Prints, after Alphabit completes:
 *   - bbattery_NTests
 *   - one line per index "i\tname\tpvalue"
 *
 * Intended only as a Phase 0 probe to confirm:
 *   (1) link path to libtestu01 works,
 *   (2) Alphabit on the file API actually returns p-values,
 *   (3) how many distinct p-values Alphabit emits.
 *
 * Build via tools/Makefile (target: alphabit_probe).
 */

#include <stdio.h>
#include <stdlib.h>

#include "bbattery.h"

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s <bit_file> <nb_bits>\n", argv[0]);
        return 2;
    }

    char *filename = argv[1];
    double nb = strtod(argv[2], NULL);
    if (nb <= 0) {
        fprintf(stderr, "nb_bits must be positive, got %s\n", argv[2]);
        return 2;
    }

    /* Run Alphabit on a bit file.  This call is blocking and writes
     * the (verbose) TestU01 report to stdout. */
    bbattery_AlphabitFile(filename, nb);

    /* Dump the structured result to stderr so it is easy to grep
     * separately from the verbose report. */
    fprintf(stderr, "===PROBE===\n");
    fprintf(stderr, "NTests_raw=%d\n", bbattery_NTests);
    /* Iterate exactly as TestU01's own WriteReport() does (bbattery.c):
     * results live in bbattery_pVal[0 .. bbattery_NTests-1]. Two quirks:
     *   - bbattery_NTests is assigned with a pre-increment, so it is one
     *     MORE than the number of real results.
     *   - slots that were not run (including the unused index 0) hold a
     *     p-value of -1; every entry with pVal < 0 must be skipped.
     * The real result count is therefore the number of pVal[i] >= 0. */
    int real = 0;
    for (int i = 0; i < bbattery_NTests; i++) {
        if (bbattery_pVal[i] < 0.0)
            continue;
        real++;
        fprintf(stderr, "%d\t%s\t%.10g\n",
                i,
                bbattery_TestNames[i] ? bbattery_TestNames[i] : "(null)",
                bbattery_pVal[i]);
    }
    fprintf(stderr, "real_results=%d\n", real);
    fprintf(stderr, "===END===\n");
    return 0;
}
