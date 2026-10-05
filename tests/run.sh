#!/bin/bash
# tests/run.sh -- the pdf package: build every test program here with
# `scaly build`, run it with freed memory poisoned, and compare its output
# with its "; Expected:" line. Then the generated width table against its
# generator.
#
#   tests/run.sh [scaly]      default: the `scaly` on the PATH, or SCALY
#
# The compiler finds the standard library in its installation and the
# package in ./packages of the directory it runs in, so this runs from the
# repository root.
cd "$(dirname "$0")/.." || exit 2
SCALY="${1:-${SCALY:-scaly}}"
if ! command -v "$SCALY" > /dev/null 2>&1; then
  echo "no scaly on the PATH: install Scaly (https://scaly.io) or set SCALY" >&2
  exit 2
fi
set -u

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

pass=0; fail=0; failures=()
for f in tests/*.scaly; do
  t=$(basename "$f" .scaly)
  expected=$(sed -n 's/^; Expected: //p' "$f")
  if ! "$SCALY" build "$f" -o "$TMP/$t" > "$TMP/$t.log" 2>&1; then
    fail=$((fail+1)); failures+=("$t(compile): $(grep -m1 error "$TMP/$t.log")"); continue
  fi
  out=$(SCALY_POISON=1 "$TMP/$t" 2>"$TMP/$t.err"); rc=$?
  if [ "$rc" = 0 ] && [ "$out" = "$expected" ]; then
    pass=$((pass+1))
  else
    fail=$((fail+1)); failures+=("$t(rc=$rc): '$out' $(head -1 "$TMP/$t.err")")
  fi
done
if python3 tools/metrics.py --check > "$TMP/metrics.log" 2>&1; then
  pass=$((pass+1))
else
  fail=$((fail+1)); failures+=("metrics: $(head -1 "$TMP/metrics.log")")
fi
echo "pdf: $pass PASS, $fail FAIL"
for x in "${failures[@]+"${failures[@]}"}"; do echo "  $x"; done
[ "$fail" = 0 ]
