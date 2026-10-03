#!/usr/bin/env bash
# Pakker ut filmer og episoder som ligger i RAR-arkiver (nedlastingsmapper med .rar/.r00 …).
# Bare arkiver som inneholder en videofil pakkes ut – programmer, spill o.l. blir urørt.
# Videoen havner i samme mappe som arkivet; kjør sort-media.py etterpå.
#
#   ./scripts/unpack-rar.sh "/srv/media/disk1/Det siste nye"
#   ./scripts/unpack-rar.sh --slett-rar "/srv/media/disk1/Det siste nye"
#
# --slett-rar      sletter RAR-filene i en mappe etter at den er pakket ut uten feil.
# --min-alder N    hopper over mapper der noe er endret de siste N minuttene (lastes ned).
set -euo pipefail

delete=0 min_age=0
while [[ ${1:-} == --* ]]; do
  case $1 in
    --slett-rar) delete=1; shift ;;
    --min-alder) min_age=$2; shift 2 ;;
    *) echo "Ukjent valg: $1" >&2; exit 1 ;;
  esac
done
if [[ $# -lt 1 ]]; then
  echo "Bruk: $0 [--slett-rar] [--min-alder MINUTTER] <mappe> …" >&2
  exit 1
fi
if ! command -v unrar >/dev/null; then
  echo "Installer unrar først: sudo apt install -y unrar" >&2
  exit 1
fi

video_ext='mkv|mp4|avi|m4v|mov|wmv|ts|m2ts|mpg|mpeg'
ok=0 already=0 skipped=0 failed=0

delete_rars() {
  find "$1" -maxdepth 1 -type f \( -iname '*.rar' -o -iregex '.*\.[rs][0-9][0-9]' \) -delete
}

# Skriver «størrelse<TAB>filnavn» for hver videofil i arkivet.
list_videos() {
  unrar lt "$1" 2>/dev/null | awk -v ext="$video_ext" '
    /^ *Name: / { name = substr($0, index($0, ": ") + 2) }
    /^ *Size: / { if (tolower(name) ~ ("\\.(" ext ")$")) print $2 "\t" name }' | sort -u
}

for top in "$@"; do
  top=${top%/}
  while IFS= read -r -d '' dir; do
    name=${dir#"$top"/}
    # Første volum: «x.part01.rar» i nyere arkiver, ellers «x.rar» (med .r00, .r01 … ved siden av).
    first=$(find "$dir" -maxdepth 1 -type f -iregex '.*\.part0*1\.rar' | sort | head -n1)
    if [[ -z $first ]]; then
      first=$(find "$dir" -maxdepth 1 -type f -iname '*.rar' ! -iregex '.*\.part[0-9]+\.rar' | sort | head -n1)
    fi
    [[ -n $first ]] || continue
    if ((min_age)) && [[ -n $(find "$dir" -type f -mmin "-$min_age" -print -quit) ]]; then
      echo "  venter (endret nylig): $name"
      continue
    fi

    videos=$(list_videos "$first")
    if [[ -z $videos ]]; then
      # Reserve: navnelisten uten størrelser (da pakkes det alltid ut).
      videos=$(unrar lb "$first" 2>/dev/null | grep -iE "\.($video_ext)$" | sed 's/^/?\t/' || true)
    fi
    if [[ -z $videos ]]; then
      echo "  hopper over (ingen video i arkivet): $name"
      skipped=$((skipped + 1))
      continue
    fi

    # Er videoen allerede pakket ut (riktig størrelse)? Da trengs ikke arkivet lenger.
    complete=1
    while IFS=$'\t' read -r size file; do
      [[ -f "$dir/$file" && $(stat -c %s "$dir/$file") == "$size" ]] || complete=0
    done <<< "$videos"
    if ((complete)); then
      echo "  allerede pakket ut: $name"
      already=$((already + 1))
      if ((delete)); then delete_rars "$dir"; fi
      continue
    fi

    echo "==> Pakker ut: $name"
    # -o+ : overskriv halvferdige filer fra tidligere forsøk.
    if out=$(unrar x -o+ -idq "$first" "$dir/" 2>&1); then
      ok=$((ok + 1))
      if ((delete)); then delete_rars "$dir"; fi
    else
      rc=$?
      reason=$(grep -v '^[[:space:]]*$' <<< "$out" | tail -n1)
      echo "  FEIL ($rc): $name: ${reason:-ukjent feil}" >&2
      failed=$((failed + 1))
    fi
  done < <(find "$top" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
done

echo
echo "Ferdig: $ok pakket ut, $already var allerede pakket ut, $skipped hoppet over (ikke video), $failed feilet."
