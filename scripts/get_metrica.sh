#!/usr/bin/env bash
# Download Metrica Sports open sample tracking data (25fps, all 22 players +
# ball) for the live tracking feed. Files are large (~30MB each) and gitignored.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)/data/metrica"
mkdir -p "$DIR"
BASE="https://raw.githubusercontent.com/metrica-sports/sample-data/master/data"

for g in 1 2; do
  for f in RawTrackingData_Home_Team RawTrackingData_Away_Team RawEventsData; do
    echo "Downloading Game $g: $f ..."
    curl -fsSL "$BASE/Sample_Game_$g/Sample_Game_${g}_${f}.csv" \
      -o "$DIR/g${g}_${f}.csv"
  done
done
echo "Done. Files in $DIR"
