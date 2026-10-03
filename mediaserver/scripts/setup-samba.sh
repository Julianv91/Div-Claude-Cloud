#!/usr/bin/env bash
# Deler /srv/media på hjemmenettet, så du kan legge inn nye filmer fra andre PC-er.
#   sudo ./scripts/setup-samba.sh
# I Windows: skriv \\<serverens-ip>\media i Filutforsker.
set -euo pipefail

MEDIA_DIR=/srv/media
CONF=/etc/samba/smb.conf

if [[ $EUID -ne 0 || -z ${SUDO_USER:-} ]]; then
  echo "Kjør med sudo fra din vanlige bruker: sudo $0" >&2
  exit 1
fi
user=$SUDO_USER

apt-get update
apt-get install -y samba

if ! grep -q '^\[media\]' "$CONF"; then
  cp "$CONF" "$CONF.bak.$(date +%Y%m%d%H%M%S)"
  cat >> "$CONF" <<SMB

[media]
   comment = Filmer og serier
   path = $MEDIA_DIR
   browseable = yes
   read only = no
   valid users = $user
   force user = $user
   create mask = 0644
   directory mask = 0755
SMB
fi

testparm -s >/dev/null

echo "Velg et Samba-passord for '$user' (brukes når du kobler til fra andre PC-er):"
smbpasswd -a "$user"

systemctl enable --now smbd
systemctl restart smbd

if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow samba
fi

# Advar om disker brukeren ikke kan skrive til (typisk ext4-disker formatert på en annen maskin).
for dir in "$MEDIA_DIR"/*/; do
  [[ -d $dir ]] || continue
  if ! sudo -u "$user" test -w "$dir"; then
    echo "Advarsel: $user kan ikke skrive til $dir. Rett det med:"
    echo "  sudo chown -R $user: $dir"
  fi
done

ip=$(hostname -I | awk '{print $1}')
echo
echo "Ferdig! Koble til fra Windows med \\\\${ip}\\media (bruker: $user)."
