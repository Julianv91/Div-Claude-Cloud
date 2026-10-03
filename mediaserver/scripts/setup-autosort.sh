#!/usr/bin/env bash
# Lager en Innboks-mappe på hver mediedisk og en systemd-timer som hvert 15. minutt
# pakker ut og sorterer det som legges der inn i Filmer/ og Serier/.
#   sudo ./scripts/setup-autosort.sh
# Se hva den har gjort:  journalctl -u mediaserver-autosort -n 50
set -euo pipefail

MEDIA_DIR=/srv/media

if [[ $EUID -ne 0 || -z ${SUDO_USER:-} ]]; then
  echo "Kjør med sudo fra din vanlige bruker: sudo $0" >&2
  exit 1
fi
user=$SUDO_USER
dir=$(cd "$(dirname "$0")/.." && pwd)
chmod +x "$dir"/scripts/*.sh "$dir"/scripts/*.py

if ! command -v unrar >/dev/null; then
  apt-get install -y unrar
fi

for disk in "$MEDIA_DIR"/*/; do
  if mountpoint -q "$disk"; then
    sudo -u "$user" mkdir -p "${disk}Innboks"
    echo "Innboks: ${disk}Innboks"
  fi
done

cat > /etc/systemd/system/mediaserver-autosort.service <<UNIT
[Unit]
Description=Pakk ut og sorter nye filmer og serier i Innboks
After=local-fs.target

[Service]
Type=oneshot
User=$user
Nice=10
IOSchedulingClass=idle
ExecStart=$dir/scripts/autosort.sh
UNIT

cat > /etc/systemd/system/mediaserver-autosort.timer <<UNIT
[Unit]
Description=Sorter Innboks hvert 15. minutt

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now mediaserver-autosort.timer

echo
echo "Ferdig! Legg nedlastinger i Innboks på en av diskene (\\\\<server-ip>\\media\\disk1\\Innboks)."
echo "Hvert 15. minutt pakkes RAR-filer ut og filmer/serier flyttes til Filmer/ og Serier/."
echo "Se hva som har skjedd:  journalctl -u mediaserver-autosort -n 50"
