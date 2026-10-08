#!/bin/sh
# Re-run every 04-analysis experiment (about 3 minutes).
#
#   cp -r prototype /tmp/bw-proto            # work on a COPY of prototype/ (nothing in it is modified,
#                                            # but importing it would otherwise write __pycache__)
#   BW_PROTOTYPE=/tmp/bw-proto PY=/path/to/python sh run_all.sh
#
# Needs only the prototype's own dependencies (no numpy/pandas). Outputs go to ./out/
# and to ../features.csv and ../normal-stats.csv.
set -e
cd "$(dirname "$0")"
PY="${PY:-python3}"
export PYTHONDONTWRITEBYTECODE=1
: "${BW_PROTOTYPE:?set BW_PROTOTYPE to a copy of prototype/}"
"$PY" floors.py        > out/floors.log
"$PY" features.py      > out/features.log
"$PY" normal_stats.py  > out/normal_stats.log
"$PY" sweep.py         > out/sweep.log
"$PY" fa_examples.py   > out/fa_examples.log
"$PY" coverage.py      > out/coverage.log
"$PY" pattern_counts.py > out/pattern_counts.log
"$PY" dust_tests.py     > out/dust_tests.log
echo "done: see out/ and ../features.csv ../normal-stats.csv"
