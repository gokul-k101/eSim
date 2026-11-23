#!/bin/bash
# Quick verification for the Task 4 installer fixes.
# Usage: ./verify.sh <path-to-eSim-checkout>   (defaults to ./eSim)
set -u

ROOT=${1:-/home/gokulk/esim-task4/eSim}
BASE="$ROOT/Ubuntu"
if [[ ! -d "$BASE" ]]; then
    BASE="$ROOT"
fi

echo "== Checking shell syntax"
bash -n "$BASE/install-eSim.sh" || exit 1
for f in "$BASE"/install-eSim-scripts/*.sh; do
    bash -n "$f" || exit 1
done
echo "OK"

echo "== Checking dispatcher version logic"
grep -q 'VERSION_ID=$(. /etc/os-release' "$BASE/install-eSim.sh" || exit 1
grep -q '"25.04")' "$BASE/install-eSim.sh" || exit 1
echo "OK"

echo "== Checking python3-distutils guard"
# The 2.5 release scripts that still request python3-distutils must guard it.
for f in "$BASE"/install-eSim.sh "$BASE"/install-eSim-scripts/*.sh; do
    if grep -q 'python3-distutils' "$f"; then
        grep -q 'apt-cache show python3-distutils' "$f" || exit 1
    fi
done
echo "OK"

echo "== Checking Plucky NGHDL/LLVM fixes"
grep -q 'function configureNgHdlForPlucky' "$BASE/install-eSim-scripts/install-eSim-25.04.sh" || exit 1
grep -q 'llvm-18' "$BASE/install-eSim-scripts/install-eSim-25.04.sh" || exit 1
grep -q 'llvm-config-18' "$BASE/install-eSim-scripts/install-eSim-25.04.sh" || exit 1
echo "OK"

echo "== Checking dynamic KiCad config directory"
grep -q 'latest_version=' "$BASE/install-eSim-scripts/install-eSim-25.04.sh" || exit 1
echo "OK"

echo "== Checking KiCad 8 PPA on 25.04"
grep -q '25.04.*kicad-8.0-releases\|24.04.*||.*25.04' "$BASE/install-eSim-scripts/install-eSim-25.04.sh" || exit 1
if grep -A1 'KiCad 8.0 is already installed' "$BASE/install-eSim-scripts/install-eSim-25.04.sh" | grep -q 'exit 0'; then exit 1; fi
echo "OK"

echo "== Runtime version detection (unprivileged)"
printf 'n\n' | timeout 10s "$BASE/install-eSim.sh" --install 2>&1 | head -n 2

echo "ALL CHECKS PASSED"
