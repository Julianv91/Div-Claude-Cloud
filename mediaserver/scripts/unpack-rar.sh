#!/usr/bin/env bash
# Pakker ut filmer og episoder som ligger i RAR-arkiver (nedlastingsmapper med .rar/.r00 …).
# Bare arkiver som inneholder en videofil pakkes ut – programmer, spill o.l. blir urørt.
# Videoen havner i samme mappe som arkivet; kjør sort-media.py etterpå.
#
#   ./scripts/unpack-rar.sh "/srv/media/disk1/Det siste nye"
#   ./scripts/unpack-rar.sh --slett-rar "/srv/media/disk1/Det siste nye"
#
# --slett-rar sletter RAR-filene i en mappe etter at den er pakket ut uten feil.
set -euo pipefail

delete=0
if [[ ${1:-} == --slett-rar ]]; then
  delete=1
  shift
fi
if [[ $# -lt 1 ]]; then
  echo "Bruk: $0 [--slett-rar] <mappe> …" >&2
  exit 1
fi
if ! command -v unrar >/dev/null; then
  echo "Installer unrar først: sudo apt install -y unrar" >&2
  exit 1
fi

video_re='\.(mkv|mp4|avi|m4v|mov|wmv|ts|m2ts|mpg|mpeg)$'
ok=0 skipped=0 failed=0

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

    if ! unrar lb "$first" 2>/dev/null | grep -qiE "$video_re"; then
      echo "  hopper over (ingen video i arkivet): $name"
      skipped=$((skipped + 1))
      continue
    fi

    echo "==> Pakker ut: $name"
    # -o- : overskriv aldri – trygt å kjøre flere ganger.
    if unrar x -o- -idq "$first" "$dir/"; then
      ok=$((ok + 1))
      if ((delete)); then
        find "$dir" -maxdepth 1 -type f \
          \( -iname '*.rar' -o -iregex '.*\.[rs][0-9][0-9]' \) -delete
      fi
    else
      echo "  FEIL: kunne ikke pakke ut $name (ødelagt eller ufullstendig arkiv?)" >&2
      failed=$((failed + 1))
    fi
  done < <(find "$top" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
done

echo
echo "Ferdig: $ok pakket ut, $skipped hoppet over (ikke video), $failed feilet."
