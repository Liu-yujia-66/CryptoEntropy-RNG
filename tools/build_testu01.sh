#!/usr/bin/env bash
#
# build_testu01.sh -- build the vendored TestU01 1.2.3 C library.
#
# TestU01 has no pip package and no root-free system package, so its source is
# vendored under vendor/TestU01-1.2.3/ and built by this script.
#
# IMPORTANT: TestU01's libtool-based build does NOT tolerate a space anywhere
# in the build path, and this repository lives under ".../Master Thesis/...".
# The script therefore copies the source into a SPACE-FREE staging directory
# under $HOME, builds and installs it there, and tools/Makefile links against
# that install. Nothing is built inside the repository.
#
# Usage (run from anywhere):
#   bash tools/build_testu01.sh            # build
#   bash tools/build_testu01.sh clean      # remove the staging/install dir
#
# Layout (override the root with the TESTU01_HOME environment variable):
#   $TESTU01_HOME/src       space-free copy of the TestU01 source
#   $TESTU01_HOME/lib       static archives (libtestu01.a, libprobdist.a, ...)
#   $TESTU01_HOME/include   headers
#   default TESTU01_HOME = ~/.cache/cryptoentropy-rng/testu01
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_REPO="$REPO_ROOT/vendor/TestU01-1.2.3"

TESTU01_HOME="${TESTU01_HOME:-$HOME/.cache/cryptoentropy-rng/testu01}"

if [ "${1:-}" = "clean" ]; then
    rm -rf "$TESTU01_HOME"
    echo "[build_testu01] removed $TESTU01_HOME"
    exit 0
fi

# The build path must not contain a space (libtool limitation).
case "$TESTU01_HOME" in
    *" "*)
        echo "[build_testu01] ERROR: build path contains a space:" >&2
        echo "  $TESTU01_HOME" >&2
        echo "  Set TESTU01_HOME to a space-free directory and retry." >&2
        exit 1 ;;
esac

if [ ! -f "$SRC_REPO/configure" ]; then
    echo "[build_testu01] ERROR: TestU01 source not found." >&2
    echo "  expected: $SRC_REPO/configure" >&2
    echo "  Download TestU01 1.2.3 from" >&2
    echo "    http://simul.iro.umontreal.ca/testu01/tu01.html" >&2
    echo "  and unpack it so that the path above exists." >&2
    exit 1
fi

SRC_BUILD="$TESTU01_HOME/src"
echo "[build_testu01] repo source  : $SRC_REPO"
echo "[build_testu01] build+install: $TESTU01_HOME"

# Copy a clean source tree (no prior build artifacts) into the space-free
# staging area. tar handles spaces in the source path; the destination is
# guaranteed space-free by the check above.
echo "[build_testu01] copying source to staging ..."
rm -rf "$SRC_BUILD"
mkdir -p "$SRC_BUILD"
( cd "$SRC_REPO" && tar cf - \
    --exclude='*.o' --exclude='*.lo' --exclude='*.a' --exclude='*.la' \
    --exclude='*.so*' --exclude='*.dylib*' \
    --exclude='.libs' --exclude='.deps' \
    --exclude='config.status' --exclude='config.log' --exclude='libtool' \
    --exclude='./Makefile' . ) | ( cd "$SRC_BUILD" && tar xf - )

cd "$SRC_BUILD"

echo "[build_testu01] configuring (static libraries) ..."
sh ./configure --prefix="$TESTU01_HOME" \
    --disable-shared --disable-dependency-tracking

# Maintainer-mode guard: a copy does not preserve mtimes, which can leave
# configure.ac / Makefile.am looking newer than the generated configure /
# config.h.in / Makefile.in. make would then try to re-run autoconf /
# autoheader / automake -- not needed for a plain build and often absent.
# Stamp the generated files newest so make never tries.
find . \( -name 'configure.ac' -o -name 'configure.in' \
         -o -name 'Makefile.am' -o -name 'acinclude.m4' \) \
    -exec touch -t 197001020000 {} + 2>/dev/null || true
find . \( -name 'aclocal.m4' -o -name 'configure' \
         -o -name 'config.h.in' -o -name 'Makefile.in' \) \
    -exec touch {} + 2>/dev/null || true

echo "[build_testu01] compiling ..."
make

echo "[build_testu01] installing ..."
make install

echo
echo "[build_testu01] done. static archives in $TESTU01_HOME/lib :"
ok=1
for a in libtestu01.a libprobdist.a libmylib.a; do
    if [ -f "$TESTU01_HOME/lib/$a" ]; then
        echo "  OK       lib/$a"
    else
        echo "  MISSING  lib/$a" >&2
        ok=0
    fi
done
if [ "$ok" -ne 1 ]; then
    echo "[build_testu01] ERROR: some archives are missing -- build failed." >&2
    exit 1
fi
echo
echo "[build_testu01] next: build the tools with"
echo "  make -C \"$SCRIPT_DIR\""
