# Hjemmekino med Jellyfin – komplett oppsettguide

En steg-for-steg-guide for å gjøre en gammel PC om til en mediaserver som strømmer filmer og
serier til PC-er, TV og mobil – hjemme og ute. Alt er gratis, og ingenting sendes til andre
enn deg selv.

**Det du ender opp med:**

- **Jellyfin** – «egen Netflix» med plakater, beskrivelser, undertekster og «fortsett der du slapp»
- **Nettverksdeling** – serverens disker som en vanlig stasjon (f.eks. `M:`) i Windows
- **Automatisk innboks** – legg nedlastinger i en mappe, så pakkes de ut og sorteres av seg selv
- **Tilgang utenfra** via Tailscale – uten å åpne porter i ruteren
- **Eksternt skrivebord** – styr serveren fra Windows, så den kan stå uten skjerm og tastatur

> Regn med 1–2 timer første gang, mest venting på installasjoner.

---

## Innhold

1. [Hva du trenger](#1-hva-du-trenger)
2. [Installer Linux Mint](#2-installer-linux-mint)
3. [Grunnoppsett etter installasjon](#3-grunnoppsett-etter-installasjon)
4. [Hent skriptene](#4-hent-skriptene)
5. [Koble til diskene](#5-koble-til-diskene)
6. [Installer Jellyfin](#6-installer-jellyfin)
7. [Sett opp Jellyfin i nettleseren](#7-sett-opp-jellyfin-i-nettleseren)
8. [Rydd og sorter samlingen du har](#8-rydd-og-sorter-samlingen-du-har)
9. [Nettverksdeling til Windows](#9-nettverksdeling-til-windows)
10. [Automatisk innboks](#10-automatisk-innboks)
11. [Se på film – apper og TV](#11-se-på-film--apper-og-tv)
12. [Tilgang utenfra med Tailscale](#12-tilgang-utenfra-med-tailscale)
13. [Eksternt skrivebord og drift uten skjerm](#13-eksternt-skrivebord-og-drift-uten-skjerm)
14. [Vedlikehold](#14-vedlikehold)
15. [Feilsøking](#15-feilsøking)

---

## 1. Hva du trenger

**Maskinvare**

| Del | Anbefaling |
|---|---|
| PC | Helst Intel-prosessor fra **7. generasjon eller nyere** (har *QuickSync* for videokonvertering). En brukt kontor-PC eller mini-PC (f.eks. Intel N100) er perfekt. |
| Systemdisk | En liten SSD (120 GB+) til Linux |
| Mediedisker | Én eller flere harddisker med filmene dine. **Diskene formateres ikke** – NTFS-disker fra Windows fungerer fint. |
| Nettverk | **Kabel** til ruteren anbefales sterkt |
| Til installasjonen | Skjerm, tastatur, mus og en minnepinne på minst 8 GB |

Et eget skjermkort trengs ikke. Moderne Intel-grafikk konverterer video like godt og bruker mindre strøm.

**Programvare (lastes ned underveis):** Linux Mint, balenaEtcher eller Rufus.

---

## 2. Installer Linux Mint

Linux Mint ligner mye på Windows og kan brukes som vanlig PC i tillegg til å være server.

1. Last ned **Linux Mint – Cinnamon Edition** fra [linuxmint.com](https://linuxmint.com/download.php).
2. Skriv ISO-filen til minnepinnen med [balenaEtcher](https://etcher.balena.io) eller
   [Rufus](https://rufus.ie) (velg *ISO-modus* hvis Rufus spør).
3. **Koble fra mediediskene** så de ikke kan slettes ved et uhell.
4. Start PC-en fra minnepinnen: trykk **F12 / F11 / F7 / Esc** gjentatte ganger ved oppstart for
   oppstartsmenyen og velg minnepinnen (helst den som starter med «UEFI»).
5. Velg **Start Linux Mint**, og deretter **Install Linux Mint** på skrivebordet.
6. Kryss av for å installere multimediakodeker, og installer på **systemdisken**.
7. Lag en bruker med **små bokstaver** i brukernavnet (f.eks. `ola`) – det gjør livet lettere senere.

> **Feilmelding om `mmx64.efi`, «MokManager» eller «import_mok_state»?** Gå inn i BIOS
> (Del/F2 ved oppstart) og slå **Secure Boot** av. Se [Feilsøking](#15-feilsøking).

---

## 3. Grunnoppsett etter installasjon

Alle kommandoer skrives i **Terminal** (Ctrl+Alt+T). Lim inn med **Ctrl+Shift+V**. Når du
skriver passord vises ingenting – det er normalt.

**Oppdater systemet** og start på nytt:

```bash
sudo apt update && sudo apt upgrade -y
```

**Slå av hvilemodus** – ellers sovner serveren og blir borte for de andre enhetene. Sett
*Innstillinger → Strømstyring → Hvilemodus* til **Aldri**, og kjør i tillegg:

```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

**Finn IP-adressen** (det første tallet):

```bash
hostname -I
```

> **Viktig:** Lag en **DHCP-reservasjon** i ruteren slik at serveren alltid får samme adresse.
> Ellers kan den bytte adresse etter en omstart, og da må alt kobles til på nytt.

---

## 4. Hent skriptene

Skriptene gjør det meste av jobben. Hent dem og legg dem i hjemmemappen:

```bash
sudo apt install -y git
git clone -b claude/local-video-sharing-server-9bzbsz https://github.com/Julianv91/Div-Claude-Cloud.git
mv Div-Claude-Cloud/mediaserver ~/mediaserver
rm -rf Div-Claude-Cloud
cd ~/mediaserver
chmod +x scripts/*.sh scripts/*.py
```

Alle kommandoene videre kjøres fra `~/mediaserver`.

| Skript | Hva det gjør |
|---|---|
| `add-disk.sh` | Monterer en disk fast under `/srv/media/<navn>` (formaterer ikke) |
| `install.sh` | Installerer Docker og starter Jellyfin, med maskinvare-transkoding om mulig |
| `sort-media.py` | Sorterer løse filmer/episoder inn i `Filmer/` og `Serier/` – kan angres |
| `unpack-rar.sh` | Pakker ut filmer/episoder som ligger i RAR-filer |
| `setup-samba.sh` | Deler diskene på hjemmenettet |
| `setup-autosort.sh` | Lager automatisk innboks som sorterer nye nedlastinger |

---

## 5. Koble til diskene

Koble til mediediskene, men **ikke åpne dem i filbehandleren** (da monteres de automatisk på
feil sted). Se hva maskinen ser:

```bash
lsblk -f
```

Finn de store partisjonene (f.eks. `sdb1` med `ntfs` og flere TB). **Ikke** velg systemdisken
(den med `/` og `/boot/efi`), og ikke små «reserverte» partisjoner uten filsystem.

Monter hver disk med et kort navn:

```bash
sudo ./scripts/add-disk.sh /dev/sdb1 disk1
sudo ./scripts/add-disk.sh /dev/sdc1 disk2
```

Diskene havner fast under `/srv/media/disk1`, `/srv/media/disk2` osv. – også etter omstart, og
selv om bokstavene `sdb`/`sdc` bytter plass. Maskinen starter normalt selv om en disk mangler.

> **Montering feilet på en NTFS-disk?** Den ble ikke lukket riktig i Windows. Kjør
> `sudo apt install -y ntfs-3g && sudo ntfsfix -d /dev/sdb1` og prøv igjen.

---

## 6. Installer Jellyfin

```bash
./scripts/install.sh
```

Kjøres **uten** `sudo` (den spør selv). Den installerer Docker, laster ned Jellyfin, slår på
maskinvare-transkoding hvis den finner Intel/AMD-grafikk, og skriver til slutt ut adressen,
f.eks. `http://192.168.1.50:8096`.

Sjekk at den kjører:

```bash
sudo docker ps --filter name=jellyfin --format "{{.Names}}: {{.Status}}"
```

Du skal se `jellyfin: Up …`.

---

## 7. Sett opp Jellyfin i nettleseren

Åpne `http://<server-ip>:8096` (eller `http://localhost:8096` på selve serveren) og følg
veiviseren:

1. Velg språk og lag en **administratorbruker**.
2. **Legg til mediebibliotek** – ett for filmer og ett for serier:
   - Innholdstype **Filmer** → mapper `/media/disk1/Filmer` (og `/media/disk2/Filmer` …)
   - Innholdstype **Serier** → mapper `/media/disk1/Serier` (og `/media/disk2/Serier` …)
   - Språk: Norsk, land: Norge

   Inne i Jellyfin heter diskene `/media/<navn>`, ikke `/srv/media/<navn>`. Ett bibliotek kan
   hente fra flere disker. Mappene `Filmer` og `Serier` lages av sorteringsskriptet i steg 8 –
   har du dem ikke ennå, legg til bibliotekene etter at du har sortert.
3. **Ekstern tilgang:** la «Tillat eksterne tilkoblinger» stå på, men **ikke** slå på
   automatisk port-videresending (UPnP).
4. Fullfør og logg inn.

**Maskinvare-transkoding:** *Kontrollpanel → Avspilling → Transkoding*

| Grafikk | Innstilling |
|---|---|
| Intel 7.–10. gen | **Intel QuickSync (QSV)**. Kryss av H264, HEVC, MPEG2, VC1, VP8, VP9, HEVC 10bit, VP9 10bit. *Low-Power*-koderne: **av** |
| Intel 11. gen og nyere / N100 | **QSV**, kryss også av AV1. *Low-Power*-koderne: **på** for 12. gen og nyere (inkl. N100), ellers av |
| AMD | **VAAPI** |

Lag gjerne egne brukere til familien under *Kontrollpanel → Brukere* – da husker Jellyfin hva
hver enkelt har sett.

---

## 8. Rydd og sorter samlingen du har

Jellyfin vil ha filer i en bestemt struktur:

```
Filmer/
  Inception (2010)/
    Inception.2010.1080p.mkv
    Inception.2010.1080p.en.srt
Serier/
  Breaking Bad/
    Season 01/
      Breaking.Bad.S01E01.720p.mkv
```

Ligger samlingen din hulter til bulter, gjør skriptene jobben. Alt flyttes innenfor samme
disk (tar sekunder), **ingenting slettes**, og alt kan angres.

**a) Pakk ut RAR-filer** (bare arkiver med video pakkes ut; programmer o.l. røres ikke):

```bash
sudo apt install -y unrar
./scripts/unpack-rar.sh --slett-rar "/srv/media/disk1/Nedlastinger"
```

`--slett-rar` sletter RAR-filene *bare* der utpakkingen gikk uten feil. Mapper der videoen
allerede er pakket ut fra før, ryddes også – det kan frigjøre mye plass.

**b) Se hva sorteringen vil gjøre** (ingenting flyttes ennå):

```bash
./scripts/sort-media.py "/srv/media/disk1/Nedlastinger" /srv/media/disk1/Serier > ~/forslag.txt
grep "^FILM" ~/forslag.txt                 # filmene den fant
sed -n '/BLIR LIGGENDE/,$p' ~/forslag.txt  # det som ikke blir flyttet, og hvorfor
```

Bytt ut mappene med dine egne – du kan gi flere mapper på én gang.

**c) Sorter for alvor:**

```bash
./scripts/sort-media.py --utfør "/srv/media/disk1/Nedlastinger" /srv/media/disk1/Serier | tail -4
```

Til slutt skrives en `--angre`-kommando som setter alt tilbake slik det var.

**Det skriptet håndterer:**

- Episoder (`S01E02`, `1x02`, `102`, `2of5`) → `Serier/<Navn>/Season NN/`
- Filmer med årstall → `Filmer/<Tittel (År)>/`
- Episodefiler uten navn (`x.mkv`) får navnet til mappen de lå i
- Mapper som «Vikings Season 1» med filer som `S01E01 Tittel.avi`
- **Undertekster** ved siden av videoen *og* i `Subs`-mapper – får navn som `<video>.en.srt`
- **Duplikater:** beholder den største versjonen, lister resten som «dårligere kopi – kan slettes»
- Programmer, musikk, spill o.l. blir liggende urørt

Ting den ikke kjenner igjen (spesialepisoder, rare navn) flytter du for hånd.

---

## 9. Nettverksdeling til Windows

```bash
sudo ./scripts/setup-samba.sh
```

Du velger et eget **Samba-passord** (ikke det samme som Linux-passordet). I Windows:
høyreklikk *Denne PC-en → Koble til nettverksstasjon*, velg f.eks. `M:` og skriv
`\\<server-ip>\media`. Logg inn med Linux-brukernavnet og Samba-passordet.

Alle diskene vises som undermapper (`disk1`, `disk2` …). Jellyfin oppdager nye filer av seg selv.

> Delingen gir tilgang til **hele** diskene. Den er passordbeskyttet og bare for hjemmenettet.

---

## 10. Automatisk innboks

```bash
sudo ./scripts/setup-autosort.sh
```

Lager en `Innboks`-mappe på hver disk (`M:\disk1\Innboks`). Med jevne mellomrom pakkes RAR-filer
ut og innholdet sorteres inn i `Filmer/` og `Serier/` – undertekster inkludert. Det som ikke
gjenkjennes blir liggende.

Standard: sjekk **hvert 15. minutt**, og ting som er endret de siste **30 minuttene** får
ligge (så pågående nedlastinger ikke flyttes).

> **Last ned lokalt først!** La nedlastingsprogrammet laste ned til PC-ens egen disk og
> *flytte ferdige filer* til innboksen. Mange samtidige småskrivinger over nettverket til en
> vanlig harddisk går **svært** tregt.

Flytter du bare inn ferdige filer, kan du korte ned ventetiden (hvert 5. min, 10 min venting):

```bash
sudo sed -i 's/OnUnitActiveSec=.*/OnUnitActiveSec=5min/' /etc/systemd/system/mediaserver-autosort.timer
sudo mkdir -p /etc/systemd/system/mediaserver-autosort.service.d
printf '[Service]\nEnvironment=MIN_AGE=10\n' | sudo tee /etc/systemd/system/mediaserver-autosort.service.d/ventetid.conf
sudo systemctl daemon-reload && sudo systemctl restart mediaserver-autosort.timer
```

Se hva innboksen har gjort: `journalctl -u mediaserver-autosort -n 50`

---

## 11. Se på film – apper og TV

| Enhet | Hvordan |
|---|---|
| PC | Nettleser: `http://<server-ip>:8096`, eller appen [Jellyfin Media Player](https://github.com/jellyfin/jellyfin-media-player) |
| Android TV / Google TV / Fire TV | «Jellyfin» i app-butikken |
| LG (webOS) | «Jellyfin» i LG Content Store |
| Samsung | Sjekk app-butikken; ellers DLNA (under) eller en billig Google TV-dongle |
| Mobil | Jellyfin-appen (iOS/Android) |

**Eldre TV uten app – DLNA:** *Kontrollpanel → Plugins → Katalog → DLNA*, installer og start
Jellyfin på nytt (`cd ~/mediaserver && sudo docker compose restart`). Serveren dukker opp i
TV-ens kilde-/mediemeny.

**4K:** spilles en 4K-fil av direkte på en 4K-TV med Jellyfin-app, jobber serveren nesten ikke.
Må den regne om 4K HDR til en eldre 1080p-skjerm, tar det mye kraft – regn med én strøm om
gangen på eldre maskinvare.

---

## 12. Tilgang utenfra med Tailscale

**Ikke åpne port 8096 i ruteren** – da går passord og video ukryptert over internett.
Tailscale lager et privat, kryptert nettverk mellom dine egne enheter, uten åpne porter.
Gratis til privat bruk, og virker også hos leverandører uten egen offentlig IP.

**På serveren:**

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Åpne lenken som vises, logg inn og godkjenn maskinen. Gå så til
[login.tailscale.com/admin/machines](https://login.tailscale.com/admin/machines), klikk **⋯** ved
serveren → **Disable key expiry** (ellers logges den ut etter 6 måneder).

**På mobil/laptop:** installer Tailscale-appen, logg inn med **samme konto**, slå den på. I
Jellyfin-appen bruker du `http://<servernavn>:8096` (eller `100.x.x.x`-adressen fra
`tailscale ip -4`). Test med Wi-Fi av.

Tips: sett en grense under *Kontrollpanel → Avspilling → Strømming → Begrensning av bitrate
for internettstrømming* (f.eks. 8 Mbps) så du ikke bruker opp mobildata.

---

## 13. Eksternt skrivebord og drift uten skjerm

Gir hele skrivebordet i et vindu på Windows via innebygd **Tilkobling til eksternt skrivebord**
(`mstsc`):

```bash
sudo apt install -y xrdp
sudo adduser xrdp ssl-cert
cat > ~/.xsession <<'EOF'
export XDG_SESSION_DESKTOP=cinnamon
export XDG_CURRENT_DESKTOP=X-Cinnamon
export XDG_SESSION_TYPE=x11
exec cinnamon-session
EOF
chmod +x ~/.xsession
sudo systemctl enable --now xrdp
```

**Slå av automatisk pålogging:** *Meny → Påloggingsvindu → Brukere* – tøm brukernavnet for
automatisk pålogging.

**Koble til fra Windows:** `mstsc` → server-IP → økt **Xorg** → brukernavn med **små
bokstaver** og passord. Lukk vinduet (krysset) når du er ferdig – da fortsetter du der du slapp.

> Du må være **logget ut** på selve serveren – ellers lukker den eksterne økten seg med en
> gang. Påloggingsskjermen bruker **amerikansk tastatur**, så `æøå@"` i passordet kan bli feil.

**Valgfritt – SSH** (terminal fra Windows, nyttig som reserve):
`sudo apt install -y openssh-server`, deretter `ssh <bruker>@<server-ip>` fra Windows Terminal.

**Før du kobler fra skjerm og tastatur – i BIOS:**

- *Restore on AC Power Loss* → **Power On** (starter av seg selv etter strømbrudd)
- *Halt on errors* → **No errors** (stopper ikke uten tastatur)

Start på nytt med `sudo reboot` – unngå å slå av, for da må noen trykke på knappen.

---

## 14. Vedlikehold

| Hva | Kommando |
|---|---|
| Oppdatere Jellyfin | `cd ~/mediaserver && sudo docker compose pull && sudo docker compose up -d` |
| Oppdatere Linux | Oppdateringsbehandleren, eller `sudo apt update && sudo apt upgrade` |
| Ledig plass | `df -h /srv/media/*` |
| Hva tar plass | `sudo apt install -y ncdu && ncdu /srv/media/disk1` |
| Diskhelse | `sudo apt install -y smartmontools && sudo smartctl -H -A /dev/sdb` |
| Jellyfin-logg | `cd ~/mediaserver && sudo docker compose logs --tail 50` |

**Diskhelse:** står det `PASSED` og `0` på *Reallocated_Sector*, *Current_Pending* og
*Offline_Uncorrectable*, er disken frisk. Tall over 0 betyr at det er på tide å bytte.

**Backup:** ta kopi av `~/mediaserver/config/` (brukere, hva som er sett, biblioteker), og av
alt på diskene som ikke kan lastes ned igjen (bilder, dokumenter).

---

## 15. Feilsøking

| Problem | Løsning |
|---|---|
| Oppstart fra minnepinne: `mmx64.efi not found` / `MokManager` / `import_mok_state() failed` | Slå av **Secure Boot** i BIOS. Hjelper ikke det: «Restore Factory Keys» i BIOS, eller kopier `EFI\boot\grubx64.efi` til `mmx64.efi` på minnepinnen. |
| `Permission denied` når du kjører et skript | `chmod +x scripts/*.sh scripts/*.py` |
| `docker: permission denied` | Logg ut og inn igjen, eller bruk `sudo` foran |
| Disk vil ikke montere (NTFS) | `sudo ntfsfix -d /dev/sdX1`, eller kjør `chkdsk /f` på disken i Windows |
| Biblioteket er tomt | Sjekk `findmnt /srv/media/disk1`. I Jellyfin heter stien `/media/disk1/...` |
| Hakker under avspilling | *Kontrollpanel → Aktivitet* viser om den transkoder. Slå på maskinvare-transkoding, eller bruk en klient som spiller direkte |
| Treg nedlasting til serveren | Last ned lokalt først og flytt ferdige filer til innboksen |
| Fildeling avviser passordet | Samba har **eget** passord: `sudo smbpasswd <bruker>` |
| Eksternt skrivebord: «feil påloggingsinfo» | Brukernavn med **små bokstaver**; sjekk tastaturoppsett. Se `sudo tail -n 20 /var/log/xrdp-sesman.log` |
| Eksternt skrivebord lukker seg med en gang | Logg ut på selve serveren; sjekk `~/.xsession` (steg 13); se `tail -n 25 ~/.xsession-errors` |
| Fil kan ikke slettes fra Windows | Slett fra Linux: `sudo rm -v "/srv/media/disk1/sti/til/fil"` (bruk **Tab** for å fullføre navnet) |
| Serveren har fått ny IP | `hostname -I` for å se den nye; lag DHCP-reservasjon i ruteren |
| Feilsortert | `./scripts/sort-media.py --angre logs/sortering-<tidspunkt>.tsv` |
| Undertekster mangler for ting sortert tidligere | `./scripts/sort-media.py --undertekster-fra-logg logs/*.tsv --utfør` (virker så lenge de gamle nedlastingsmappene finnes) |

Mer teknisk dokumentasjon av hvert skript finnes i `README.md` i samme mappe.

**Lykke til, og god film!** 🍿
