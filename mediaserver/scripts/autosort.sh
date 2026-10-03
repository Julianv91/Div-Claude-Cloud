#!/usr/bin/env bash
# Pakker ut og sorterer nye nedlastinger i Innboks-mappene (/srv/media/<disk>/Innboks).
# Kjøres automatisk hvert 15. minutt av systemd-timeren som setup-autosort.sh lager.
# Ting som er endret de siste MIN_AGE minuttene (lastes fortsatt ned) får ligge til neste runde.
set -uo pipefail

cd "$(dirname "$0")/.."
MEDIA_DIR=${MEDIA_DIR:-/srv/media}
MIN_AGE=${MIN_AGE:-30}

shopt -s nullglob
for inbox in "$MEDIA_DIR"/*/Innboks; do
  [[ -n $(ls -A "$inbox") ]] || continue
  echo "== $inbox"
  if command -v unrar >/dev/null; then
    ./scripts/unpack-rar.sh --slett-rar --min-alder "$MIN_AGE" "$inbox"
  fi
  ./scripts/sort-media.py --utfør --min-alder "$MIN_AGE" "$inbox"
done
