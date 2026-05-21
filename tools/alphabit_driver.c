/*
 * alphabit_driver.c -- batch driver for the TestU01 Alphabit battery.
 *
 * Runs Alphabit on many bit streams in a single process invocation, so the
 * process-startup / library-load cost is amortised across a whole Exp 3 cell
 * (its ~ell* offset streams) or an Exp 4 fused-stream set, rather than paid
 * once per stream.
 *
 * Usage:
 *   alphabit_driver <manifest> <output_csv>
 *
 *   <manifest>    text file, one stream per line, TAB-separated:
 *                     <stream_id>\t<bit_file>\t<nb_bits>
 *                 Blank lines and lines starting with '#' are ignored.
 *                 <stream_id> must not contain a tab, comma, quote or newline.
 *                 <bit_file> is a FULLY PACKED bit file (8 data bits per byte,
 *                 nb_bits/8 bytes) -- produce it with numpy.packbits. See
 *                 alphabit_probe.c for the format rationale.
 *
 *   <output_csv>  CSV written by this driver, columns:
 *                     stream_id,test_name,p_value
 *                 test_name is double-quoted because TestU01's names contain
 *                 commas (e.g. "MultinomialBitsOver, L = 4"). One row per
 *                 (stream, real test). Tests TestU01 did not run hold a
 *                 p-value < 0 and are skipped here -- mirroring TestU01's own
 *                 WriteReport(). A stream whose tests were all skipped, or
 *                 whose bit file was unreadable, simply contributes no rows;
 *                 the Python wrapper detects that by stream_id absence.
 *
 * TestU01 prints a verbose report to stdout; this driver redirects stdout to
 * /dev/null so that noise is discarded. The CSV is written straight to
 * <output_csv>; progress and warnings go to stderr.
 *
 * Note on indices: TestU01 fills bbattery_pVal[] sequentially and skips slots
 * for tests it did not run, so a slot's index is NOT a stable test identifier.
 * Always map results by test_name, never by position.
 *
 * Build via tools/Makefile (target: alphabit_driver).
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "bbattery.h"
#include "swrite.h"

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s <manifest> <output_csv>\n", argv[0]);
        return 2;
    }
    const char *manifest_path = argv[1];
    const char *out_path = argv[2];

    FILE *mf = fopen(manifest_path, "r");
    if (!mf) {
        fprintf(stderr, "alphabit_driver: cannot open manifest: %s\n",
                manifest_path);
        return 2;
    }
    FILE *out = fopen(out_path, "w");
    if (!out) {
        fprintf(stderr, "alphabit_driver: cannot open output: %s\n", out_path);
        fclose(mf);
        return 2;
    }
    fprintf(out, "stream_id,test_name,p_value\n");

    /* Discard TestU01's verbose stdout report and trim its per-test chatter.
     * The CSV goes to <output_csv>; this redirection keeps stdout silent. */
    if (freopen("/dev/null", "w", stdout) == NULL) {
        /* non-fatal: TestU01 chatter would just reappear on stdout */
    }
    swrite_Basic = 0;

    char line[8192];
    int n_ok = 0, n_skipped = 0;

    while (fgets(line, sizeof line, mf)) {
        line[strcspn(line, "\r\n")] = '\0';
        if (line[0] == '\0' || line[0] == '#')
            continue;

        char *id = strtok(line, "\t");
        char *bitfile = strtok(NULL, "\t");
        char *nbstr = strtok(NULL, "\t");
        if (!id || !bitfile || !nbstr) {
            fprintf(stderr, "alphabit_driver: WARN malformed manifest line\n");
            n_skipped++;
            continue;
        }

        double nb = strtod(nbstr, NULL);
        if (nb <= 0.0) {
            fprintf(stderr, "alphabit_driver: WARN bad nb_bits for '%s'\n", id);
            n_skipped++;
            continue;
        }

        /* Pre-check: a missing/unreadable file would make TestU01 abort the
         * whole process, so verify it opens before handing it to Alphabit. */
        FILE *bf = fopen(bitfile, "rb");
        if (!bf) {
            fprintf(stderr, "alphabit_driver: WARN cannot read bit file for "
                    "'%s': %s\n", id, bitfile);
            n_skipped++;
            continue;
        }
        fclose(bf);

        bbattery_AlphabitFile(bitfile, nb);

        /* Scan [0, NTests) and skip p < 0, exactly as TestU01's WriteReport. */
        for (int i = 0; i < bbattery_NTests; i++) {
            if (bbattery_pVal[i] < 0.0)
                continue;
            const char *nm =
                bbattery_TestNames[i] ? bbattery_TestNames[i] : "";
            fprintf(out, "%s,\"%s\",%.10g\n", id, nm, bbattery_pVal[i]);
        }
        fflush(out);
        n_ok++;
    }

    fclose(mf);
    fclose(out);
    fprintf(stderr, "alphabit_driver: %d stream(s) processed, %d skipped -> %s\n",
            n_ok, n_skipped, out_path);
    return 0;
}
