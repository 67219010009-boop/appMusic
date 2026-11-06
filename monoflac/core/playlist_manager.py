from dataclasses import dataclass, asdict
import json
import os
import urllib.parse
from typing import List, Dict, Optional, Any

SUPPORTED_AUDIO_EXTENSIONS = {".flac", ".wav", ".wave", ".ogg", ".oga"}

def format_file_size(size_bytes: int) -> str:
    """Formats file size in bytes to a human-readable string (e.g. 82.4 MB)."""
    if size_bytes <= 0:
        return "—"
    mb = size_bytes / (1024 * 1024)
    if mb >= 1000:
        gb = mb / 1024
        return f"{gb:.2f} GB"
    return f"{mb:.1f} MB"

def format_bitrate(bitrate_bps: int) -> str:
    """Formats bitrate in bits per second to kbit/s string (e.g. 2854 kbps)."""
    if bitrate_bps <= 0:
        return "—"
    kbps = int(round(bitrate_bps / 1000.0))
    return f"{kbps} kbps"

@dataclass
class TrackInfo:
    path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0
    sample_rate: int = 0
    bit_depth: int = 0
    channels: int = 2
    file_size: int = 0
    bitrate: int = 0

    @property
    def is_hi_res(self) -> bool:
        return self.bit_depth > 16 or self.sample_rate > 48000

    def format_badge(self) -> str:
        ext = os.path.splitext(self.path)[1].upper().replace(".", "") or "AUDIO"
        rate_khz = f"{self.sample_rate / 1000.0:.1f} kHz" if self.sample_rate else "Unknown"
        bits = f"{self.bit_depth}-bit" if self.bit_depth else ""
        if bits and rate_khz != "Unknown":
            res_str = f"{bits} / {rate_khz}"
        else:
            res_str = rate_khz

        details = []
        if self.bitrate > 0:
            details.append(format_bitrate(self.bitrate))
        if self.file_size > 0:
            details.append(format_file_size(self.file_size))

        extra_str = f" • {' • '.join(details)}" if details else ""
        return f"{'[HI-RES] ' if self.is_hi_res else ''}{res_str} {ext}{extra_str}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrackInfo":
        return cls(
            path=data.get("path", ""),
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            album=data.get("album", ""),
            duration=float(data.get("duration", 0.0)),
            sample_rate=int(data.get("sample_rate", 0)),
            bit_depth=int(data.get("bit_depth", 0)),
            channels=int(data.get("channels", 2)),
            file_size=int(data.get("file_size", 0)),
            bitrate=int(data.get("bitrate", 0)),
        )

def parse_uri_list(uri_data: str) -> List[str]:
    """
    Parses a text/uri-list string received from drag-and-drop actions.
    Decodes file:// URIs and URL-encoded characters.
    """
    paths: List[str] = []
    for line in uri_data.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("file://"):
            line = line[7:]
            if line.startswith("localhost/"):
                line = line[9:]
        path = urllib.parse.unquote(line)
        if path:
            paths.append(path)
    return paths

def extract_track_info(file_path: str) -> TrackInfo:
    """
    Extracts audio metadata, file size, bitrate, and stream specifications from audio files.
    """
    basename = os.path.basename(file_path)
    title = os.path.splitext(basename)[0]
    artist = "Unknown Artist"
    album = "Unknown Album"
    duration = 0.0
    sample_rate = 0
    bit_depth = 0
    channels = 2
    file_size = 0
    bitrate = 0

    if not os.path.isfile(file_path):
        return TrackInfo(
            path=file_path,
            title=basename,
            artist=artist,
            album=album,
            duration=duration,
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            channels=channels,
            file_size=file_size,
            bitrate=bitrate,
        )

    try:
        file_size = os.path.getsize(file_path)
    except Exception:
        file_size = 0

    try:
        from mutagen.flac import FLAC
        audio = FLAC(file_path)
        if audio.info:
            duration = float(audio.info.length)
            sample_rate = int(audio.info.sample_rate)
            bit_depth = int(audio.info.bits_per_sample)
            channels = int(audio.info.channels)
            if hasattr(audio.info, "bitrate") and audio.info.bitrate:
                bitrate = int(audio.info.bitrate)

        if audio.get("title"):
            title = audio["title"][0]
        if audio.get("artist"):
            artist = audio["artist"][0]
        if audio.get("album"):
            album = audio["album"][0]
    except Exception:
        try:
            import mutagen
            gen_audio = mutagen.File(file_path)
            if gen_audio and gen_audio.info:
                duration = float(getattr(gen_audio.info, "length", 0.0))
                sample_rate = int(getattr(gen_audio.info, "sample_rate", 0))
                bit_depth = int(getattr(gen_audio.info, "bits_per_sample", 16))
                channels = int(getattr(gen_audio.info, "channels", 2))
                bitrate = int(getattr(gen_audio.info, "bitrate", 0))
                if gen_audio.tags:
                    for k in ("title", "TITLE"):
                        if k in gen_audio.tags:
                            title = str(gen_audio.tags[k][0])
                    for k in ("artist", "ARTIST"):
                        if k in gen_audio.tags:
                            artist = str(gen_audio.tags[k][0])
                    for k in ("album", "ALBUM"):
                        if k in gen_audio.tags:
                            album = str(gen_audio.tags[k][0])
        except Exception:
            pass

    # If bitrate was not directly provided by decoder, calculate from file size and duration
    if bitrate <= 0 and file_size > 0 and duration > 0:
        bitrate = int(round((file_size * 8.0) / duration))

    return TrackInfo(
        path=file_path,
        title=title,
        artist=artist,
        album=album,
        duration=duration,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        channels=channels,
        file_size=file_size,
        bitrate=bitrate,
    )

def scan_paths_recursively(paths: List[str]) -> List[str]:
    """
    Recursively scans list of paths (files and directories) for supported audio files.
    """
    found: List[str] = []
    for p in paths:
        if os.path.isfile(p):
            ext = os.path.splitext(p)[1].lower()
            if ext in SUPPORTED_AUDIO_EXTENSIONS:
                found.append(p)
        elif os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in sorted(files):
                    ext = os.path.splitext(f)[1].lower()
                    if ext in SUPPORTED_AUDIO_EXTENSIONS:
                        found.append(os.path.join(root, f))
    return found

class PlaylistManager:
    """
    Manages multiple named playlists, handles addition, deletion,
    reordering, and persists them to JSON in the user's config directory.
    """
    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = config_path
        else:
            candidate_dirs = [
                os.path.expanduser("~/.config/monoflac"),
                os.path.join(os.getcwd(), ".monoflac_data"),
                "/tmp/monoflac",
            ]
            chosen_dir = None
            for d in candidate_dirs:
                try:
                    os.makedirs(d, exist_ok=True)
                    test_file = os.path.join(d, ".write_test")
                    with open(test_file, "w") as f:
                        f.write("ok")
                    os.remove(test_file)
                    chosen_dir = d
                    break
                except OSError:
                    continue
            if not chosen_dir:
                chosen_dir = "/tmp"
            self.config_path = os.path.join(chosen_dir, "playlists.json")

        self.playlists: Dict[str, List[TrackInfo]] = {}
        self.active_playlist_name: str = "Default"
        self.load()

    def get_playlist_names(self) -> List[str]:
        return list(self.playlists.keys())

    def get_active_playlist_name(self) -> str:
        return self.active_playlist_name

    def set_active_playlist(self, name: str) -> None:
        if name in self.playlists:
            self.active_playlist_name = name

    def create_playlist(self, name: str) -> bool:
        clean_name = name.strip()
        if not clean_name:
            return False
        if clean_name not in self.playlists:
            self.playlists[clean_name] = []
            return True
        return False

    def remove_playlist(self, name: str) -> bool:
        if name in self.playlists:
            del self.playlists[name]
            if not self.playlists:
                self.playlists["Default"] = []
                self.active_playlist_name = "Default"
            elif self.active_playlist_name == name:
                self.active_playlist_name = list(self.playlists.keys())[0]
            return True
        return False

    def get_tracks(self, playlist_name: Optional[str] = None) -> List[TrackInfo]:
        target = playlist_name or self.active_playlist_name
        return self.playlists.get(target, [])

    def add_track_to_playlist(self, playlist_name: str, track: TrackInfo) -> None:
        if playlist_name not in self.playlists:
            self.create_playlist(playlist_name)
        self.playlists[playlist_name].append(track)

    def add_paths_to_playlist(self, playlist_name: str, paths: List[str]) -> int:
        audio_files = scan_paths_recursively(paths)
        if playlist_name not in self.playlists:
            self.create_playlist(playlist_name)
        
        added_count = 0
        for f in audio_files:
            track = extract_track_info(f)
            self.playlists[playlist_name].append(track)
            added_count += 1
        
        if added_count > 0:
            self.save()
        return added_count

    def remove_track(self, playlist_name: str, index: int) -> bool:
        tracks = self.playlists.get(playlist_name)
        if tracks is not None and 0 <= index < len(tracks):
            tracks.pop(index)
            return True
        return False

    def move_track(self, playlist_name: str, src_index: int, dest_index: int) -> bool:
        tracks = self.playlists.get(playlist_name)
        if tracks is None:
            return False
        if not (0 <= src_index < len(tracks)):
            return False
        if not (0 <= dest_index < len(tracks)):
            return False
        if src_index == dest_index:
            return True
        track = tracks.pop(src_index)
        tracks.insert(dest_index, track)
        self.save()
        return True

    def save(self) -> None:
        data = {
            "active_playlist": self.active_playlist_name,
            "playlists": {
                name: [t.to_dict() for t in tracks]
                for name, tracks in self.playlists.items()
            }
        }
        try:
            parent = os.path.dirname(self.config_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def load(self) -> None:
        if not os.path.isfile(self.config_path):
            self.playlists = {"Default": []}
            self.active_playlist_name = "Default"
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded_playlists: Dict[str, List[TrackInfo]] = {}
            for name, track_list in data.get("playlists", {}).items():
                loaded_tracks = []
                for t in track_list:
                    track_obj = TrackInfo.from_dict(t)
                    # Self-heal missing file_size or bitrate from older configs
                    if (track_obj.file_size <= 0 or track_obj.bitrate <= 0) and os.path.isfile(track_obj.path):
                        fresh = extract_track_info(track_obj.path)
                        track_obj.file_size = fresh.file_size
                        track_obj.bitrate = fresh.bitrate
                    loaded_tracks.append(track_obj)
                loaded_playlists[name] = loaded_tracks

            if not loaded_playlists:
                loaded_playlists = {"Default": []}

            self.playlists = loaded_playlists
            active = data.get("active_playlist", "Default")
            if active in self.playlists:
                self.active_playlist_name = active
            else:
                self.active_playlist_name = list(self.playlists.keys())[0]
        except Exception:
            self.playlists = {"Default": []}
            self.active_playlist_name = "Default"
