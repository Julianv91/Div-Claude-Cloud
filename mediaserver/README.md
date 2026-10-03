# Hjemmekino med Jellyfin

Et lite oppsett for å dele filmer og serier på hjemmenettet. Det fungerer omtrent
som Plex, men er basert på [Jellyfin](https://jellyfin.org): gratis, åpen kildekode,
krever ingen konto og alt blir værende hjemme.

```
 Harddisker ──► /srv/media/disk1, disk2 ──► Jellyfin (Docker) ──► PC-er (nettleser / app)
                                                              └──► TV (app eller DLNA)
```

| Fil | Hva den gjør |
|---|---|
| `scripts/add-disk.sh` | Monterer en harddisk fast under `/srv/media/<navn>` (uten å formatere) |
| `scripts/install.sh` | Installerer Docker og starter Jellyfin, og skrur på maskinvare-transkoding når det er mulig |
| `scripts/setup-samba.sh` | Valgfritt: deler mappen på nettet, så du kan kopiere inn nye filmer fra PC-ene |
| `docker-compose.yml` | Selve Jellyfin-tjenesten |

---

## 1. Installer Linux

Du har to valg:

- **A. Vanlig PC med skrivebord.** Maskinen kan brukes som en helt vanlig datamaskin
  (nettleser, filer, se film på den direkte), og Jellyfin går i bakgrunnen.
- **B. Ren server uten skrivebord.** Bruker litt mindre ressurser og styres fra en
  annen PC over SSH.

### A. Med skrivebord (enklest å komme i gang med)

Bruk **Linux Mint 22** (føles mest som Windows) eller **Ubuntu Desktop 24.04 LTS**.

1. Last ned ISO-filen fra [linuxmint.com](https://linuxmint.com/download.php)
   (velg *Cinnamon Edition*) eller [ubuntu.com](https://ubuntu.com/download/desktop).
2. Skriv den til en minnepinne (minst 8 GB) med [balenaEtcher](https://etcher.balena.io)
   eller [Rufus](https://rufus.ie).
3. Start maskinen fra minnepinnen. Trykk F12, F11, F7 eller Esc under oppstart for
   oppstartsmenyen; tasten varierer mellom produsenter.
4. Velg *Installer* og la installasjonen bruke **systemdisken**. **Pass på at du ikke
   velger en av filmdiskene!** Det tryggeste er å koble fra filmdiskene under installasjonen.
5. Når maskinen har startet, åpner du **Terminal** og fortsetter med steg 2 under.

**To ting du må gjøre på en skrivebordsmaskin:**

- **Slå av hvilemodus.** Ellers sovner maskinen og blir borte for de andre PC-ene.
  Gå til *Innstillinger → Strømstyring* og sett «Hvilemodus» til *Aldri*. Skjermen kan
  gjerne slå seg av. Vil du være helt sikker, kjør
  `sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target`.
- **Ikke åpne filmdiskene i filbehandleren før steg 3.** Skrivebordet monterer disker
  automatisk under `/media/<bruker>/...`. `add-disk.sh` sier fra hvis disken allerede er
  montert; da kjører du `sudo umount /dev/sdb1` (eller trykker «Løs ut» i
  filbehandleren) og prøver igjen. Etterpå ligger diskene fast under `/srv/media`.

### B. Uten skrivebord (server)

Bruk **Debian 13** (anbefalt) eller **Ubuntu Server 24.04 LTS**.

1. Last ned [Debian netinst](https://www.debian.org/distrib/netinst) og skriv den til en
   minnepinne med [balenaEtcher](https://etcher.balena.io) eller Rufus.
2. Installer på systemdisken, **ikke** på filmdiskene.
3. Fjern krysset for skrivebordsmiljø under programvarevalg. Kryss av for
   **SSH server** og **standard system utilities**.
4. Lag en vanlig bruker (for eksempel `julian`). Gi den sudo-tilgang hvis installasjonen
   ikke gjorde det: `su -c "usermod -aG sudo julian"`, og logg ut og inn igjen.

Etter installasjonen kan du koble fra skjerm og tastatur og styre maskinen fra
PC-en med `ssh julian@<ip-adresse>`.

> **Tips:** Gi serveren en fast IP-adresse ved å lage en *DHCP-reservasjon* i
> ruteren. Da endrer ikke adressen seg.

## 2. Hent dette oppsettet

```bash
sudo apt install -y git
git clone https://github.com/julianv91/div-claude-cloud.git
cd div-claude-cloud/mediaserver
```

(Er repoet privat, trenger du en GitHub-token som passord. Du kan også kopiere
`mediaserver`-mappen over med `scp -r`.)

## 3. Koble til harddiskene

Koble til diskene og finn partisjonene:

```bash
lsblk -f
```

Se etter de store partisjonene (for eksempel `sdb1` med `ntfs` og 4T). Monter hver av dem
med et kort navn:

```bash
sudo ./scripts/add-disk.sh /dev/sdb1 disk1
sudo ./scripts/add-disk.sh /dev/sdc1 disk2
```

Skriptet **formaterer ingenting**. Det legger disken inn i `/etc/fstab` (via UUID, så
rekkefølgen på USB-portene ikke spiller noen rolle) og monterer den. Maskinen starter
normalt selv om en disk mangler.

Disker fra Windows (NTFS) fungerer fint, både for lesing og skriving. Nekter en
NTFS-disk å montere, ble den ikke lukket riktig i Windows. Koble den til Windows igjen,
slå av *Rask oppstart* og velg *Løs ut* før du flytter den.

## 4. Installer og start Jellyfin

```bash
./scripts/install.sh
```

Skriptet installerer Docker og lager `.env`. Har maskinen Intel- eller AMD-grafikk,
skrur det på maskinvare-transkoding, og så starter det Jellyfin. Til slutt skriver
det ut adressen, for eksempel `http://192.168.1.50:8096`.

## 5. Første gangs oppsett i nettleseren

Åpne adressen fra en PC og følg veiviseren:

1. Velg språk og lag en administrator-bruker.
2. **Legg til mediebibliotek:**
   - *Filmer*: innholdstype **Movies**, mapper `/media/disk1/Filmer` (og `/media/disk2/...`)
   - *Serier*: innholdstype **Shows**, mapper `/media/disk1/Serier` osv.

   Ett bibliotek kan hente fra flere disker.
3. Sett metadataspråk til norsk (eller engelsk) og land til Norge.
4. Fullfør. Jellyfin skanner diskene og henter plakater, beskrivelser og så videre.

**Maskinvare-transkoding** (hvis install.sh fant `/dev/dri`):
Gå til *Kontrollpanel → Avspilling → Transkoding*.

- Intel: velg **Intel QuickSync (QSV)** og kryss av for kodekene under
  *Aktiver maskinvaredekoding*. På nyere Intel (N100/N150, 12. gen og nyere) kan du
  også slå på *Low-Power*-koderne.
- AMD: velg **VAAPI**.

Maskinvare-transkoding trengs bare når en klient ikke kan spille av filen direkte.
PC-er med nettleser klarer som regel det meste uten.

Lag gjerne egne brukere til hver i familien under *Kontrollpanel → Brukere*.
Da husker Jellyfin hva hver enkelt har sett.

## 6. Se på film

| Enhet | Hvordan |
|---|---|
| PC (nettleser) | `http://<server-ip>:8096` |
| Selve servermaskinen (med skrivebord) | `http://localhost:8096` |
| PC (app) | [Jellyfin Media Player](https://github.com/jellyfin/jellyfin-media-player): spiller av flere formater direkte uten transkoding |
| Android TV / Google TV / Fire TV | «Jellyfin» i app-butikken |
| LG (webOS) | «Jellyfin» i LG Content Store |
| Samsung (Tizen) | Sjekk app-butikken. Ellers fungerer DLNA (se under) eller en billig Google TV-dongle |
| Mobil | Jellyfin-appen (iOS/Android) |

Appene finner serveren automatisk på hjemmenettet.

**DLNA** (for TV-er uten Jellyfin-app): Installer *DLNA*-pluginen under
*Kontrollpanel → Plugins → Katalog* og start Jellyfin på nytt. TV-en ser da serveren
under kilder/media.

## 7. Legg inn og styr filer fra en annen PC

Med en nettverksdeling (Samba) ser diskene på serveren ut som en vanlig mappe på de
andre PC-ene. Du kan kopiere inn nye filmer, lage mapper, gi nytt navn og slette,
akkurat som på en lokal disk.

```bash
sudo ./scripts/setup-samba.sh
```

Du velger et eget Samba-passord. Alle diskene vises som undermapper (`disk1`, `disk2` …)
i én felles deling som heter `media`.

**Koble til:**

| Fra | Hvordan |
|---|---|
| Windows | Filutforsker → skriv `\\<server-ip>\media` i adressefeltet. For en fast stasjonsbokstav: høyreklikk *Denne PC-en → Koble til nettverksstasjon*, velg for eksempel `M:` og kryss av for *Koble til på nytt ved pålogging* |
| Mac | Finder → *Gå → Koble til tjener* (⌘K) → `smb://<server-ip>/media` |
| Linux | Filbehandleren → *Andre steder* → `smb://<server-ip>/media` |

Logg inn med brukernavnet ditt på serveren og Samba-passordet. Kryss av for
«Husk passord».

Jellyfin oppdager nye filer automatisk etter kort tid. Dukker ikke en film opp, kan
du kjøre *Kontrollpanel → Biblioteker → Skann alle biblioteker*.

**Tips:**
- Store filmfiler går mye raskere over kabel enn over Wi-Fi.
- Får du «ingen tilgang» når du skriver til en Linux-formatert disk (ext4), gi brukeren
  din eierskap: `sudo chown -R $USER: /srv/media/disk1`. Skriptet advarer om dette.
- Jellyfin selv har bare lesetilgang til diskene, så den kan aldri slette filmene dine.

## 8. (Valgfritt) Automatisk innboks for nye nedlastinger

```bash
sudo ./scripts/setup-autosort.sh
```

Lager en `Innboks`-mappe på hver disk (`\\<server-ip>\media\disk1\Innboks`) og en
tidsstyrt jobb som hvert 15. minutt pakker ut RAR-filer og sorterer det som ligger der inn i
`Filmer/` og `Serier/`. Ting som er endret de siste 30 minuttene får ligge til neste runde,
så nedlastinger som pågår ikke flyttes. Det som ikke gjenkjennes, blir liggende i innboksen.

Se hva den har gjort: `journalctl -u mediaserver-autosort -n 50`

## Navngivning av filer

Jellyfin finner riktig film/serie lettest med denne strukturen:

```
Filmer/
  Inception (2010)/
    Inception (2010).mkv
    Inception (2010).no.srt        ← undertekster
Serier/
  Lilyhammer (2012)/
    Season 01/
      Lilyhammer S01E01.mkv
```

Treffer Jellyfin feil film, kan du rette det via *⋯ → Identifiser* på filmen.

**Rydde automatisk:** Ligger filmer og episoder løst og blandet, kan `sort-media.py`
sortere dem inn i `Filmer/` og `Serier/` på samme disk. Den viser først hva den vil gjøre,
flytter bare video (programmer, musikk o.l. blir liggende), sletter ingenting og kan angres:

```bash
./scripts/sort-media.py "/srv/media/disk1/Det siste nye"            # se hva som vil skje
./scripts/sort-media.py --utfør "/srv/media/disk1/Det siste nye"    # flytt
./scripts/sort-media.py --angre logs/sortering-<tidspunkt>.tsv      # angre
```

Ligger noe pakket i RAR-filer (`.rar`, `.r00` …), pakk det ut først. Bare arkiver med video
pakkes ut; `--slett-rar` fjerner RAR-filene etter vellykket utpakking:

```bash
sudo apt install -y unrar
./scripts/unpack-rar.sh "/srv/media/disk1/Det siste nye"
```

Finnes samme film flere ganger, flytter `sort-media.py` den største versjonen og lister de
andre som «dårligere kopi – kan slettes».

## Vedlikehold

```bash
cd ~/div-claude-cloud/mediaserver

docker compose pull && docker compose up -d   # oppdater Jellyfin
docker compose logs -f                        # se loggen
docker compose restart                        # start på nytt
sudo apt update && sudo apt upgrade           # oppdater Linux
```

Automatiske sikkerhetsoppdateringer for Linux:
`sudo apt install unattended-upgrades && sudo dpkg-reconfigure unattended-upgrades`.

Ta gjerne backup av `config/`-mappen. Der ligger brukere, hva som er sett og
bibliotekoppsettet. Selve filmene ligger urørt på diskene dine.

## Feilsøking

| Problem | Løsning |
|---|---|
| `docker: permission denied` | Logg ut og inn igjen (du ble lagt til i docker-gruppen), eller bruk `sudo` |
| Bibliotek er tomt | Sjekk at disken er montert: `findmnt /srv/media/disk1`. Inne i Jellyfin heter stien `/media/disk1` |
| Hakker under avspilling | *Kontrollpanel → Aktivitet* viser om den transkoder. Slå på maskinvare-transkoding, eller bruk Jellyfin Media Player |
| Finner ikke serveren på TV-en | Sjekk at TV og server er på samme nett (ikke gjestenett) |
