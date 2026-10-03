#!/usr/bin/env bash
# Monterer en eksisterende harddisk/partisjon fast under /srv/media/<navn>.
# Disken formateres IKKE – innholdet beholdes.
#
#   sudo ./scripts/add-disk.sh /dev/sdb1 disk1
#
# Finn riktig partisjon med:  lsblk -f
set -euo pipefail

MEDIA_DIR=/srv/media

if [[ $EUID -ne 0 ]]; then
  echo "Kjør med sudo: sudo $0 <partisjon> <navn>" >&2
  exit 1
fi
if [[ $# -ne 2 ]]; then
  echo "Bruk: sudo $0 <partisjon, f.eks. /dev/sdb1> <navn, f.eks. disk1>" >&2
  exit 1
fi

dev=$1
name=$2

if [[ ! -b $dev ]]; then
  echo "$dev er ikke en blokkenhet. Se 'lsblk -f'." >&2
  exit 1
fi
if [[ ! $name =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "Navnet kan bare inneholde bokstaver (a-z), tall, - og _." >&2
  exit 1
fi

uuid=$(blkid -s UUID -o value "$dev" || true)
fstype=$(blkid -s TYPE -o value "$dev" || true)
if [[ -z $uuid || -z $fstype ]]; then
  echo "Fant ikke noe filsystem på $dev. Velg en partisjon (f.eks. /dev/sdb1), ikke hele disken." >&2
  exit 1
fi
if grep -q "UUID=$uuid" /etc/fstab; then
  echo "Disken (UUID=$uuid) står allerede i /etc/fstab." >&2
  exit 1
fi
if findmnt -rn -S "$dev" >/dev/null; then
  echo "$dev er allerede montert ($(findmnt -rn -S "$dev" -o TARGET | head -n1))." >&2
  echo "Avmonter den først med: sudo umount $dev" >&2
  exit 1
fi

# Eier av filene på disker uten Linux-rettigheter (NTFS/exFAT/FAT).
owner_uid=${SUDO_UID:-1000}
owner_gid=${SUDO_GID:-1000}
perm_opts="uid=$owner_uid,gid=$owner_gid,umask=022"
# nofail + kort timeout: maskinen starter normalt selv om disken mangler.
common_opts="nofail,x-systemd.device-timeout=10s"

case $fstype in
  ext4|ext3|xfs|btrfs)
    mount_type=$fstype
    opts="defaults,$common_opts"
    ;;
  ntfs)
    if ! modprobe ntfs3 2>/dev/null; then
      echo "Kjernen mangler ntfs3-driveren. Installer ntfs-3g eller oppdater kjernen." >&2
      exit 1
    fi
    mount_type=ntfs3
    opts="$perm_opts,$common_opts"
    ;;
  exfat|vfat)
    mount_type=$fstype
    opts="$perm_opts,$common_opts"
    ;;
  *)
    echo "Filsystemet '$fstype' støttes ikke av dette skriptet." >&2
    exit 1
    ;;
esac

target="$MEDIA_DIR/$name"
if mountpoint -q "$target"; then
  echo "$target er allerede et monteringspunkt." >&2
  exit 1
fi
mkdir -p "$target"
if [[ -n $(ls -A "$target") ]]; then
  echo "$target er ikke tom. Velg et annet navn." >&2
  exit 1
fi
# Gjør den tomme mappen skrivebeskyttet, så ingenting havner på systemdisken
# hvis mediedisken ikke er tilkoblet.
chattr +i "$target" 2>/dev/null || true

cp /etc/fstab "/etc/fstab.bak.$(date +%Y%m%d%H%M%S)"
printf '\n# mediaserver: %s (%s)\nUUID=%s  %s  %s  %s  0  0\n' \
  "$name" "$dev" "$uuid" "$target" "$mount_type" "$opts" >> /etc/fstab
systemctl daemon-reload || true

if ! mount "$target"; then
  echo "Montering feilet – fjerner linjen fra /etc/fstab igjen." >&2
  latest_backup=$(ls -t /etc/fstab.bak.* | head -n1)
  cp "$latest_backup" /etc/fstab
  systemctl daemon-reload || true
  if [[ $fstype == ntfs ]]; then
    echo "Tips: NTFS-disker som ikke ble lukket riktig i Windows (hurtigoppstart) nektes." >&2
    echo "Koble disken til Windows, slå av hurtigoppstart og velg 'Løs ut' før du prøver igjen." >&2
  fi
  exit 1
fi

echo "Montert $dev ($fstype) på $target:"
ls "$target" | head -n 20
echo
echo "I Jellyfin finner du disken under /media/$name."
