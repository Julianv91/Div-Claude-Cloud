#!/usr/bin/env bash
# Installerer Docker og starter Jellyfin.
# Kjør som vanlig bruker (ikke root) fra mediaserver-mappen:  ./scripts/install.sh
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ $EUID -eq 0 ]]; then
  echo "Kjør skriptet som din vanlige bruker (uten sudo). Det spør om sudo-passord selv." >&2
  exit 1
fi
if ! command -v apt-get >/dev/null; then
  echo "Dette skriptet støtter bare Debian/Ubuntu." >&2
  exit 1
fi

MEDIA_DIR=/srv/media

echo "==> Oppdaterer pakker"
sudo apt-get update
sudo apt-get install -y ca-certificates curl

if ! command -v docker >/dev/null; then
  echo "==> Installerer Docker"
  . /etc/os-release
  if [[ $ID == debian || $ID == ubuntu ]]; then
    curl -fsSL https://get.docker.com | sudo sh
  else
    # Linux Mint, Pop!_OS, Zorin o.l. støttes ikke av get.docker.com –
    # bruk Docker-pakkene fra distroens egne arkiver i stedet.
    if apt-cache show docker-compose-v2 >/dev/null 2>&1; then
      compose_pkg=docker-compose-v2
    else
      compose_pkg=docker-compose
    fi
    sudo apt-get install -y docker.io "$compose_pkg"
  fi
fi
sudo systemctl enable --now docker
if ! id -nG "$USER" | grep -qw docker; then
  sudo usermod -aG docker "$USER"
  echo "    (Du er lagt til i docker-gruppen – logg ut og inn igjen for å kjøre docker uten sudo.)"
fi

echo "==> Lager mapper"
sudo mkdir -p "$MEDIA_DIR"
mkdir -p config cache

if [[ ! -f .env ]]; then
  echo "==> Skriver .env"
  render_gid=$(getent group render | cut -d: -f3 || true)
  tz=$(timedatectl show -p Timezone --value 2>/dev/null || echo Europe/Oslo)
  cat > .env <<ENV
PUID=$(id -u)
PGID=$(id -g)
TZ=${tz:-Europe/Oslo}
MEDIA_DIR=$MEDIA_DIR
RENDER_GID=${render_gid:-105}
ENV
fi

if [[ -e /dev/dri/renderD128 ]]; then
  echo "==> Fant grafikkbrikke (/dev/dri) – slår på maskinvare-transkoding"
  cp hwaccel.override.yml docker-compose.override.yml
else
  echo "==> Fant ingen /dev/dri – Jellyfin bruker CPU til transkoding"
  rm -f docker-compose.override.yml
fi

if command -v ufw >/dev/null && sudo ufw status | grep -q "Status: active"; then
  echo "==> Åpner brannmur for Jellyfin (8096/tcp, 7359/udp)"
  sudo ufw allow 8096/tcp
  sudo ufw allow 7359/udp
fi

echo "==> Starter Jellyfin"
sudo docker compose pull
sudo docker compose up -d

ip=$(hostname -I | awk '{print $1}')
echo
echo "Ferdig! Åpne http://${ip}:8096 i nettleseren for å fullføre oppsettet."
