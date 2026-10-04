#!/usr/bin/env python3
"""Sorterer løse filmer og serieepisoder inn i mappene Jellyfin forventer.

    Serier/<Navn>/Season NN/<episodefil>
    Filmer/<Tittel (År)>/<filmfil>

Filene flyttes innenfor samme disk (tar ingen tid, ingenting kopieres eller slettes).
Ting som ikke gjenkjennes som film eller serie (programmer, musikk, spill …) blir liggende.

Se først hva som vil skje (ingenting flyttes):
    ./scripts/sort-media.py "/srv/media/disk1/Det siste nye" /srv/media/disk1/Serier
Flytt:
    ./scripts/sort-media.py --utfør "/srv/media/disk1/Det siste nye" /srv/media/disk1/Serier
Angre en sortering:
    ./scripts/sort-media.py --angre logs/sortering-<tidspunkt>.tsv
"""
import argparse
import os
import re
import sys
import time
from collections import Counter, namedtuple
from datetime import datetime
from pathlib import Path

VIDEO_EXT = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".ts", ".m2ts",
             ".mpg", ".mpeg", ".webm", ".flv", ".divx", ".vob"}
SUB_EXT = {".srt", ".sub", ".idx", ".ass", ".ssa", ".vtt", ".sup"}
# Filmer må være større enn dette, så samples og småklipp ikke tolkes som film.
MIN_MOVIE_BYTES = 300 * 1024 * 1024

SEP = r"[ ._\-]"
EPISODE_PATTERNS = [
    re.compile(rf"^(?P<show>.+?){SEP}+S(?P<season>\d{{1,2}}){SEP}?E(?P<episode>\d{{1,3}})", re.I),
    re.compile(rf"^(?P<show>.+?){SEP}+(?P<season>\d{{1,2}})x(?P<episode>\d{{2,3}})(?!\d)", re.I),
    # «fresh.off.the.boat.108.hdtv-lol» – sesong 1, episode 08.
    re.compile(rf"^(?P<show>.+?){SEP}+(?P<season>[1-9])(?P<episode>\d{{2}})(?={SEP}"
               r"(hdtv|pdtv|web|webrip|web-dl|proper|repack|internal|720p|1080p|xvid|x264|h264)\b)",
               re.I),
    # «BBC.Wonders.of.Life.2of5.…» – miniserier uten sesongnummer.
    re.compile(rf"^(?P<show>.+?){SEP}+(?P<episode>\d{{1,2}})of\d{{1,2}}(?!\d)", re.I),
]
MOVIE_PATTERN = re.compile(
    r"^(?P<title>.+)[ ._(\[\-]+(?P<year>19[2-9]\d|20[0-3]\d)(?=[ ._)\]\-]|$)")
OF_PATTERN = re.compile(r"(?<!\d)(\d{1,2})of\d{1,2}(?!\d)", re.I)
SAMPLE_PATTERN = re.compile(r"(^|[ ._\-])sample([ ._\-]|$)", re.I)
TRAILING_YEAR = re.compile(r"^(?P<name>.+?) (?P<year>19\d\d|20\d\d)$")
SEASON_DIR = re.compile(r"^(season|sesong|s)\s*0*(?P<n>\d+)$", re.I)
# Episodefil uten serienavn, f.eks. «S01E01 Rites of Passage.avi» – serien hentes fra mappen.
BARE_EPISODE = re.compile(rf"^S(?P<season>\d{{1,2}}){SEP}?E\d{{1,3}}", re.I)
# Sesongmappe, f.eks. «Vikings Season 1» eller «The.Wire.S02.720p.BluRay».
SHOW_SEASON_DIR = re.compile(
    rf"^(?P<show>.+?){SEP}+(?:season|sesong|S){SEP}*(?P<season>\d{{1,2}})(?!\d|{SEP}?E\d)", re.I)
# Del 1/2 osv. – to ulike deler av samme tittel er ikke duplikater.
PART_PATTERN = re.compile(rf"(?:^|{SEP})(?:part|pt|cd|disc|del){SEP}*(\d+|one|two|three|four|i{{1,3}}|iv)(?:{SEP}|$)", re.I)
ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*]')
# Undertekstmapper i nedlastinger, f.eks. «Subs/South.Park.S20E01…/2_English.srt».
SUBS_DIR = re.compile(r"^(subs?|subtitles?|undertekster)$", re.I)
EP_KEY = re.compile(r"S(\d{1,2})[ ._\-]?E(\d{1,3})", re.I)
# Språknavn/-koder i undertekstfilnavn -> koden Jellyfin forstår.
LANG_CODES = {
    "english": "en", "eng": "en", "en": "en",
    "norwegian": "no", "norsk": "no", "nor": "no", "nob": "no", "nb": "no", "no": "no",
    "swedish": "sv", "svenska": "sv", "swe": "sv", "sv": "sv",
    "danish": "da", "dansk": "da", "dan": "da", "da": "da",
    "finnish": "fi", "fin": "fi", "fi": "fi",
    "german": "de", "ger": "de", "deu": "de", "de": "de",
    "french": "fr", "fre": "fr", "fra": "fr", "fr": "fr",
    "spanish": "es", "spa": "es", "es": "es",
    "italian": "it", "ita": "it", "it": "it",
    "dutch": "nl", "dut": "nl", "nld": "nl", "nl": "nl",
    "portuguese": "pt", "por": "pt", "pt": "pt",
    "polish": "pl", "pol": "pl", "pl": "pl",
    "russian": "ru", "rus": "ru", "ru": "ru",
    "icelandic": "is", "ice": "is", "isl": "is",
}


def clean_name(raw):
    name = re.sub(r"[._]+", " ", raw)
    name = re.sub(r"\s+", " ", name).strip(" -")
    return ILLEGAL_CHARS.sub("", name)


def key(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


# stem: nytt filnavn (uten endelse) når det originale ikke har SxxEyy, ellers None.
Episode = namedtuple("Episode", "show season stem")


def clean_show(raw):
    show = clean_name(raw)
    if show.islower():
        show = show.title()
    y = TRAILING_YEAR.match(show)
    return f"{y.group('name')} ({y.group('year')})" if y else show


def parse_episode(name):
    """Episode, eller None. show er None når filnavnet ikke har serienavn (se BARE_EPISODE)."""
    for pattern in EPISODE_PATTERNS:
        m = pattern.match(name)
        if m:
            show = clean_show(m.group("show"))
            season = int(m.groupdict().get("season") or 1)
            stem = None
            if pattern is EPISODE_PATTERNS[2]:
                e = m.group("episode")
                stem = f"{name[:m.start('season')]}S{season:02d}E{e}{name[m.end('episode'):]}"
            if pattern is EPISODE_PATTERNS[3]:
                stem = OF_PATTERN.sub(lambda o: f"S01E{int(o.group(1)):02d}", name, count=1)
            return Episode(show, season, stem)
    if m := BARE_EPISODE.match(name):
        return Episode(None, int(m.group("season")), None)
    return None


def dir_show(name):
    """Serienavnet fra en mappe som «Barry.S01E02…» eller «Vikings Season 1»."""
    if (ep := parse_episode(name)) and ep.show:
        return ep
    if m := SHOW_SEASON_DIR.match(name):
        return Episode(clean_show(m.group("show")), int(m.group("season")), None)
    return None


def parse_movie(name):
    m = MOVIE_PATTERN.match(name)
    if not m:
        return None
    title = clean_name(m.group("title")).rstrip(" (")
    return f"{title} ({m.group('year')})" if title else None


def is_video(path):
    return path.suffix.lower() in VIDEO_EXT and not SAMPLE_PATTERN.search(path.stem)


def video_size(path):
    if path.is_file():
        return path.stat().st_size
    return sum(v.stat().st_size for v in path.rglob("*") if v.is_file() and is_video(v))


def newest_mtime(path):
    """Nyeste endring av filene (ikke mappene – de endres også når vi pakker ut eller flytter)."""
    if path.is_file():
        return path.stat().st_mtime
    times = [f.stat().st_mtime for f in path.rglob("*") if f.is_file()]
    return max(times) if times else path.stat().st_mtime


def disk_root(path):
    """Monteringspunktet (disken) en sti ligger på – vi flytter aldri mellom disker."""
    p = path.resolve()
    while not os.path.ismount(p):
        p = p.parent
    if p == Path("/"):
        sys.exit(f"{path} ligger ikke på en egen mediedisk – avbryter.")
    return p


def ep_key(text):
    m = EP_KEY.search(text)
    return (int(m.group(1)), int(m.group(2))) if m else None


def subs_dirs(video, top):
    """Subs-mapper i videoens mappe og hver mappe over den, til og med top."""
    d = video.parent
    while True:
        if d.is_dir():
            yield from (s for s in sorted(d.iterdir()) if s.is_dir() and SUBS_DIR.match(s.name))
        if d == top or d == d.parent:
            return
        d = d.parent


def folder_subs(video, top, key_v, single):
    """Undertekster i Subs-mapper som hører til videoen: samme SxxEyy i filnavnet eller
    undermappen, eller – når det bare er én video i nedlastingen – undertekster uten SxxEyy."""
    found = []
    for d in subs_dirs(video, top):
        for s in sorted(d.rglob("*")):
            if not (s.is_file() and s.suffix.lower() in SUB_EXT):
                continue
            k = ep_key(s.stem) or ep_key(str(s.parent.relative_to(d)))
            if (k is not None and k == key_v) or (k is None and single):
                found.append(s)
    return found


def sub_tags(sub, video_stem):
    """[språk, sdh, forced] fra f.eks. «2_English.srt» eller «Episode.eng.forced.srt»."""
    stem = sub.stem
    rest = stem[len(video_stem):] if stem.lower().startswith(video_stem.lower()) else stem
    tokens = [t.lower() for t in re.split(r"[ ._\-\[\]()]+", rest) if t]
    flags = [t for t in tokens if t in ("sdh", "cc", "forced")]
    words = [t for t in tokens if t not in flags]
    tags = [LANG_CODES[words[-1]]] if words and words[-1] in LANG_CODES else []
    if {"sdh", "cc"} & set(flags):
        tags.append("sdh")
    if "forced" in flags:
        tags.append("forced")
    return tags


def matching_subs(video):
    return [s for s in video.parent.iterdir()
            if s.is_file() and s.suffix.lower() in SUB_EXT and s.name.startswith(video.stem)]


class Planner:
    def __init__(self, min_age_minutes=0):
        self.min_age = min_age_minutes * 60
        self.moves = []        # (kilde, mål, beskrivelse)
        self.skipped = []      # (sti, grunn)
        self.taken = set()     # mål som allerede er planlagt
        self.show_dirs = {}    # (disk, nøkkel) -> mappe for serien
        self.season_dirs = {}  # (seriemappe, sesong) -> mappe
        self.movie_unit = {}   # (kilde, mål) -> filmen flyttingen hører til (mappe eller videofil)

    def resolve_duplicate_movies(self):
        """Flere kopier av samme film: behold den største, la resten ligge.
        Ulike deler (Part One/Two, CD1/CD2) er ikke kopier – da flyttes ingen av dem."""
        units = {}
        for src, dst, label in self.moves:
            if label.startswith("FILM"):
                units.setdefault(label, set()).add(self.movie_unit[src, dst])
        drop = set()
        for label, us in units.items():
            if len(us) < 2:
                continue
            title = label[7:]
            parts = {(m.group(1).lower() if (m := PART_PATTERN.search(u.name)) else None) for u in us}
            if len(parts) > 1:
                for u in sorted(us):
                    self.skipped.append((u, f"flere deler ville blitt «{title}» – sorter for hånd"))
                drop |= us
                continue
            best = max(us, key=video_size)
            for u in sorted(us - {best}):
                self.skipped.append((u, f"dårligere kopi av «{title}» – kan slettes"))
                drop.add(u)
        self.moves = [m for m in self.moves if self.movie_unit.get(m[:2]) not in drop]

    def add(self, src, dst, label, unit=None):
        if unit is not None:
            self.movie_unit[src, dst] = unit
        if dst in self.taken and label.startswith("FILM"):
            self.moves.append((src, dst, label))  # fanges opp av resolve_duplicate_movies()
            return
        if dst.exists() or dst in self.taken:
            self.skipped.append((src, f"finnes allerede: {dst}"))
            return
        self.taken.add(dst)
        self.moves.append((src, dst, label))

    def plan_subs(self, subs, target_dir, new_stem, old_stem, label, unit=None, src_of=None):
        """Flytt undertekster til target_dir med navn Jellyfin kjenner igjen:
        «<video>.en.srt», «<video>.en.sdh.srt», «<video>.2.en.srt» …"""
        groups = {}
        for sub in subs:  # .idx/.sub hører sammen og må få samme navn
            groups.setdefault((sub.parent, sub.stem), []).append(sub)
        for files in groups.values():
            tags = sub_tags(files[0], old_stem)
            for n in range(1, 100):
                base = ".".join([new_stem] + ([str(n)] if n > 1 else []) + tags)
                dsts = [target_dir / (base + f.suffix.lower()) for f in files]
                if not any(d.exists() or d in self.taken for d in dsts):
                    break
            for f, d in zip(files, dsts):
                self.add(src_of(f) if src_of else f, d, label, unit)

    def show_dir(self, root, show):
        series = root / "Serier"
        k = (root, key(show))
        if k not in self.show_dirs:
            existing = [d for d in series.iterdir() if d.is_dir()] if series.is_dir() else []
            match = next((d for d in existing if key(d.name) == key(show)), None)
            self.show_dirs[k] = match or series / show
        return self.show_dirs[k]

    def season_dir(self, show_dir, season):
        k = (show_dir, season)
        if k not in self.season_dirs:
            existing = [d for d in show_dir.iterdir() if d.is_dir()] if show_dir.is_dir() else []
            match = next((d for d in existing
                          if (m := SEASON_DIR.match(d.name)) and int(m.group("n")) == season), None)
            self.season_dirs[k] = match or show_dir / f"Season {season:02d}"
        return self.season_dirs[k]

    def plan_episode_file(self, root, video, ep, top=None, single=False):
        show_dir = self.show_dir(root, ep.show)
        target = self.season_dir(show_dir, ep.season)
        label = f"SERIE  {show_dir.name} – sesong {ep.season}"
        for f in [video, *matching_subs(video)]:
            name = ep.stem + f.name[len(video.stem):] if ep.stem else f.name
            self.add(f, target / name, label)
        if top is not None:
            new_stem = ep.stem or video.stem
            subs = folder_subs(video, top, ep_key(new_stem), single)
            self.plan_subs(subs, target, new_stem, video.stem, label)

    def plan_movie_file(self, root, video, title):
        target = root / "Filmer" / title
        for f in [video, *matching_subs(video)]:
            self.add(f, target / f.name, f"FILM   {title}", unit=video)

    def plan(self, source):
        root = disk_root(source)
        for entry in sorted(source.iterdir()):
            if self.min_age and time.time() - newest_mtime(entry) < self.min_age:
                self.skipped.append((entry, "endret nylig – venter (lastes kanskje ned)"))
                continue
            if entry.is_file():
                self.plan_file(root, entry)
            elif entry.is_dir():
                self.plan_dir(root, entry)

    def plan_file(self, root, entry):
        if not is_video(entry):
            if entry.suffix.lower() not in SUB_EXT:
                self.skipped.append((entry, "ikke en videofil"))
            return
        if (ep := parse_episode(entry.stem)) and ep.show:
            self.plan_episode_file(root, entry, ep)
        elif (title := parse_movie(entry.stem)) and entry.stat().st_size >= MIN_MOVIE_BYTES:
            self.plan_movie_file(root, entry, title)
        else:
            self.skipped.append((entry, "kjente ikke igjen navnet"))

    def plan_dir(self, root, entry):
        if entry.name in ("Serier", "Filmer"):
            return
        if entry.parent.name == "Serier":
            return  # en seriemappe som allerede ligger riktig
        try:
            videos = sorted(v for v in entry.rglob("*") if v.is_file() and is_video(v))
        except OSError as e:
            self.skipped.append((entry, f"kunne ikke leses ({e.strerror})"))
            return
        if not videos:
            files = [f for f in entry.rglob("*") if f.is_file()]
            if any(re.search(r"\.(rar|r\d\d)$", f.name, re.I) for f in files):
                self.skipped.append((entry, "RAR-arkiv – pakk ut med unpack-rar.sh hvis det er video"))
            elif not any(f.stat().st_size > 1024 * 1024 for f in files):
                self.skipped.append((entry, "tom mappe / bare småfiler"))
            else:
                self.skipped.append((entry, "ingen videofiler"))
            return
        dir_ep = parse_episode(entry.name)
        folder = dir_show(entry.name)
        episodes = []
        for v in videos:
            ep = parse_episode(v.stem)
            if ep and folder:
                ep = ep._replace(show=folder.show)  # mappenavnet har som regel penest serienavn
            elif ep and not ep.show:
                ep = None  # «S01E01.avi» i en mappe uten serienavn
            elif dir_ep and dir_ep.show:
                # Filen mangler SxxEyy (f.eks. «x.mkv») – gi den mappens navn.
                ep = dir_ep._replace(stem=dir_ep.stem or entry.name)
            episodes.append((v, ep))
        if any(ep for _, ep in episodes):
            # Episoder i en nedlastings- eller seriemappe: flytt videofilene, resten blir liggende.
            for v, ep in episodes:
                if ep:
                    self.plan_episode_file(root, v, ep, entry, single=len(videos) == 1)
                else:
                    self.skipped.append((v, "kjente ikke igjen navnet"))
            return
        title = parse_movie(entry.name)
        if title and max(v.stat().st_size for v in videos) >= MIN_MOVIE_BYTES:
            # Filmmappe: hele mappen flyttes og får navnet «Tittel (År)».
            target = root / "Filmer" / title
            label = f"FILM   {title}"
            self.add(entry, target, label, unit=entry)
            if self.moves and self.moves[-1][0] == entry:
                # Undertekster i Subs-mappen legges ved siden av filmen (etter at mappen er flyttet).
                main = max(videos, key=lambda v: v.stat().st_size)
                subs = folder_subs(main, entry, None, True)
                self.plan_subs(subs, target / main.parent.relative_to(entry), main.stem, main.stem,
                               label, unit=entry, src_of=lambda f: target / f.relative_to(entry))
            return
        self.skipped.append((entry, "kjente ikke igjen mappen (allerede en seriemappe?)"))


def plan_subs_from_logs(planner, logs):
    """Hent undertekster fra Subs-mappene i de opprinnelige nedlastingsmappene til filer
    som allerede er sortert (ifølge sorteringsloggene)."""
    lines = [(Path(a), Path(b)) for log in logs for l in open(log, encoding="utf-8")
             if l.strip() for a, b in [l.rstrip("\n").split("\t")]]
    per_folder = Counter(src.parent for src, _ in lines if is_video(src))
    for src, dst in lines:
        if not dst.exists():
            continue
        if dst.is_dir():  # en flyttet filmmappe
            videos = [v for v in dst.rglob("*") if v.is_file() and is_video(v)]
            if videos:
                main = max(videos, key=lambda v: v.stat().st_size)
                subs = folder_subs(main, dst, None, True)
                planner.plan_subs(subs, main.parent, main.stem, main.stem, f"UNDERTEKST  {dst.name}")
        elif is_video(dst) and src.parent.is_dir():
            subs = folder_subs(src, src.parent, ep_key(dst.stem), per_folder[src.parent] == 1)
            planner.plan_subs(subs, dst.parent, dst.stem, src.stem,
                              f"UNDERTEKST  {dst.parent.parent.name} – {dst.parent.name}")


def apply(moves, log_path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    done = 0
    with open(log_path, "a", encoding="utf-8") as log:
        for src, dst, _ in moves:
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    raise FileExistsError(dst)
                os.rename(src, dst)
            except OSError as e:
                print(f"  FEIL: {src} -> {dst}: {e}", file=sys.stderr)
                continue
            log.write(f"{src}\t{dst}\n")
            log.flush()
            done += 1
    return done


def undo(log_path):
    lines = [l.rstrip("\n").split("\t") for l in open(log_path, encoding="utf-8") if l.strip()]
    restored = 0
    for src, dst in map(lambda p: (Path(p[0]), Path(p[1])), reversed(lines)):
        if not dst.exists() or src.exists():
            print(f"  Hopper over {dst} (mangler, eller {src} finnes allerede)")
            continue
        src.parent.mkdir(parents=True, exist_ok=True)
        os.rename(dst, src)
        restored += 1
        # Rydd bort mapper skriptet laget og som nå er tomme.
        for d in (dst.parent, dst.parent.parent, dst.parent.parent.parent):
            try:
                d.rmdir()
            except OSError:
                pass
    print(f"Flyttet {restored} av {len(lines)} tilbake.")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mapper", nargs="*", type=Path, help="mapper som skal ryddes")
    parser.add_argument("--utfør", action="store_true", help="flytt filene (ellers bare visning)")
    parser.add_argument("--min-alder", type=int, default=0, metavar="MINUTTER",
                        help="hopp over ting som er endret de siste MINUTTER minuttene")
    parser.add_argument("--angre", type=Path, metavar="LOGG", help="angre en tidligere sortering")
    parser.add_argument("--undertekster-fra-logg", type=Path, nargs="+", metavar="LOGG",
                        help="hent undertekster fra Subs-mapper for det som allerede er sortert")
    args = parser.parse_args()

    if args.angre:
        undo(args.angre)
        return
    planner = Planner(args.min_alder)
    if args.undertekster_fra_logg:
        plan_subs_from_logs(planner, args.undertekster_fra_logg)
    else:
        if not args.mapper:
            parser.error("oppgi minst én mappe")
        for folder in args.mapper:
            if not folder.is_dir():
                sys.exit(f"Finner ikke mappen {folder}")
            planner.plan(folder)
        planner.resolve_duplicate_movies()

    label = None
    for src, dst, what in planner.moves:
        if what != label:
            print(f"\n{what}  ->  {dst.parent}")
            label = what
        print(f"    {src.name}")
    if planner.skipped:
        print("\nBLIR LIGGENDE:")
        for path, reason in planner.skipped:
            print(f"    {path}  ({reason})")

    films = len({planner.movie_unit[s, d] for s, d, w in planner.moves if w.startswith("FILM")})
    episodes = sum(1 for s, _, w in planner.moves if w.startswith("SERIE") and is_video(s))
    subs = sum(1 for s, _, _ in planner.moves if s.suffix.lower() in SUB_EXT)
    print(f"\nTotalt: {films} filmer, {episodes} episoder og {subs} undertekster blir flyttet, "
          f"{len(planner.skipped)} ting blir liggende.")

    if not args.utfør:
        print("\nDette var bare en visning – ingenting er flyttet. Legg til --utfør for å flytte.")
        return
    if not planner.moves:
        return
    log_path = (Path(__file__).resolve().parent.parent / "logs"
                / f"sortering-{datetime.now():%Y%m%d-%H%M%S}.tsv")
    done = apply(planner.moves, log_path)
    print(f"\nFlyttet {done} filer/mapper. Angre med:\n  {sys.argv[0]} --angre {log_path}")


if __name__ == "__main__":
    main()
