from dataclasses import dataclass
import os
import re
from typing import List, Optional

@dataclass
class LyricLine:
    time_sec: float
    text: str

_SQUARE_TIMESTAMP_REGEX = re.compile(r'\[(\d+):(\d{2})(?:[.:](\d{1,3}))?\]')
_ANGLE_TIMESTAMP_REGEX = re.compile(r'<(\d+):(\d{2})(?:[.:](\d{1,3}))?>')

def clean_lyric_text(text: str) -> str:
    """
    Cleans raw lyric text by stripping:
    1. Syllable/word timing tags inside angle brackets: <00:54.041>
    2. Voice or singer prefix tags: v1:, v2:, V1: etc.
    3. Any stray bracketed timestamps.
    """
    if not text:
        return ""
    # Strip voice tags like v1:, v2:, V1: at start
    text = re.sub(r'^[vV]\d+:\s*', '', text)
    # Strip syllable/word timestamps <...>
    text = re.sub(r'<[^>]*>', '', text)
    # Strip any remaining bracketed timestamps
    text = re.sub(r'\[\d+:\d{2}(?:[.:]\d+)?\]', '', text)
    return text.strip()

def parse_lrc(content: str) -> List[LyricLine]:
    """
    Parses LRC content (standard or Enhanced/Karaoke LRC) and returns
    a chronologically sorted list of LyricLine objects with clean, human-readable text.
    Filters out empty timing markers and syllable artifacts.
    """
    if not content:
        return []

    lines: List[LyricLine] = []
    
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Find timestamp matches (first check square brackets, then angle brackets if none)
        matches = list(_SQUARE_TIMESTAMP_REGEX.finditer(line))
        used_angle = False
        if not matches:
            # Check if line begins with an angle bracket timestamp (e.g. <00:12.34>)
            matches = list(_ANGLE_TIMESTAMP_REGEX.finditer(line))
            used_angle = True

        if not matches:
            continue

        # The text is everything after the last line timestamp
        last_match = matches[-1]
        raw_text = line[last_match.end():].strip()
        cleaned_text = clean_lyric_text(raw_text)

        # Skip lines that contain no actual lyric text (e.g. empty intro/break timestamps like <00:47.841>)
        if not cleaned_text:
            continue

        for match in matches:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            frac_str = match.group(3)
            
            if frac_str:
                if len(frac_str) == 1:
                    frac = int(frac_str) / 10.0
                elif len(frac_str) == 2:
                    frac = int(frac_str) / 100.0
                else:
                    frac = int(frac_str[:3]) / 1000.0
            else:
                frac = 0.0

            total_sec = minutes * 60.0 + seconds + frac
            lines.append(LyricLine(time_sec=total_sec, text=cleaned_text))

    # Sort lines chronologically
    lines.sort(key=lambda item: item.time_sec)
    return lines

def find_active_lyric_index(lyrics: List[LyricLine], position_sec: float) -> int:
    """
    Finds the index of the currently active lyric line for the given playback time.
    Returns -1 if playback position is before the first lyric line.
    """
    if not lyrics:
        return -1

    active_idx = -1
    for idx, item in enumerate(lyrics):
        if position_sec >= item.time_sec:
            active_idx = idx
        else:
            break

    return active_idx

def load_lyrics_for_file(audio_path: str) -> List[LyricLine]:
    """
    Attempts to load synced lyrics for an audio file:
    1. Checks for a .lrc file in the same directory with the same basename.
    2. Checks for embedded 'LYRICS' or 'UNSYNCEDLYRICS' Vorbis tags in the audio file.
    """
    if not audio_path or not os.path.exists(audio_path):
        return []

    base, _ = os.path.splitext(audio_path)
    lrc_candidate = base + ".lrc"

    if os.path.isfile(lrc_candidate):
        try:
            with open(lrc_candidate, "r", encoding="utf-8", errors="replace") as f:
                return parse_lrc(f.read())
        except Exception:
            pass

    try:
        from mutagen.flac import FLAC
        audio = FLAC(audio_path)
        for tag in ("lyrics", "unsyncedlyrics"):
            values = audio.get(tag) or audio.get(tag.upper())
            if values and values[0]:
                parsed = parse_lrc(values[0])
                if parsed:
                    return parsed
    except Exception:
        pass

    return []
