# MonoFLAC - Hi-Res Lossless Audio Player Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight, bit-perfect, monochrome desktop music player for Linux that plays Hi-Res FLAC files, displays synced LRC lyrics, manages multiple playlists with drag-and-drop support, persists state, and packages as an AppImage/standalone runner.

**Architecture:** A decoupled architecture with a core engine layer (`audio_engine`, `lyrics_parser`, `playlist_manager`) and a GTK3 presentation layer (`main_window`, `widgets`, `theme.css`). GStreamer is used for native lossless FLAC decoding and direct ALSA hardware output; Mutagen handles metadata parsing; state is persisted as JSON in `~/.config/monoflac/playlists.json`.

**Tech Stack:** Python 3.12, PyGObject (GTK 3, Gdk, Gst), Mutagen, Python `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-05-monoflac-design.md`

## Global Constraints

- **Theme:** Strict monochrome (black `#000000`, dark grey `#181818`/`#282828`, pure white `#ffffff`), no rainbow accents.
- **Performance:** Zero CSS transitions or animations; instantaneous responsiveness; target < 40MB idle RAM.
- **Audio Fidelity:** Bit-perfect capable, preserving original sample rate and bit depth without software resampling unless explicitly requested or unsupported by hardware.
- **Dependencies:** Standard system packages only (`python3-gi`, `gir1.2-gtk-3.0`, `gstreamer1.0`, `mutagen`); no heavy web runtimes.

## Review Focus

1. **Missing or Malformed LRC File:** Lyric parser encounters blank, non-existent, or unsynced lyric formats without crashing, gracefully falling back to empty lyrics or plain text.
   - Test: `test_parse_malformed_lrc` in Task 1.
2. **Missing or Corrupted Audio File in Playlist:** When a file in the saved playlist has been moved or deleted, player does not crash; it skips to the next valid track or marks it gracefully.
   - Test: `test_missing_file_handling` in Task 2.
3. **Hi-Res Audio Metadata Extraction:** 24-bit/96kHz or 24-bit/192kHz FLAC files correctly report bit depth, sample rate, and channels.
   - Test: `test_flac_metadata_extraction` in Task 2.
4. **Drag-and-Drop URI Scheme Parsing:** Handles `file://` URIs with percent-encoded characters, spaces, and directories recursively.
   - Test: `test_parse_drag_drop_uris` in Task 2.
5. **Exact Timestamp Lyric Seeking:** Seeking audio forwards/backwards accurately updates the highlighted lyric line index immediately.
   - Test: `test_lyrics_sync_index_lookup` in Task 1.

---

### Task 1: Synced Lyrics Parser

**Files:**
- Create: `monoflac/core/lyrics_parser.py`
- Test: `tests/test_lyrics_parser.py`

**Interfaces:**
- Consumes: None
- Produces:
  - `LyricLine(time_sec: float, text: str)`
  - `parse_lrc(content: str) -> list[LyricLine]`
  - `find_active_lyric_index(lyrics: list[LyricLine], position_sec: float) -> int`
  - `load_lyrics_for_file(audio_path: str) -> list[LyricLine]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lyrics_parser.py
import unittest
from monoflac.core.lyrics_parser import LyricLine, parse_lrc, find_active_lyric_index

class TestLyricsParser(unittest.TestCase):
    def test_parse_valid_lrc(self):
        lrc = "[00:12.50]Hello world\n[01:05.00]Second line\n[01:30.250]Third line"
        lines = parse_lrc(lrc)
        self.assertEqual(len(lines), 3)
        self.assertAlmostEqual(lines[0].time_sec, 12.5)
        self.assertEqual(lines[0].text, "Hello world")
        self.assertAlmostEqual(lines[1].time_sec, 65.0)
        self.assertAlmostEqual(lines[2].time_sec, 90.25)

    def test_parse_malformed_lrc(self):
        lrc = "Not a lyric\n[ti:Test Title]\n[invalid:time]Broken\n[00:05.10]Valid line"
        lines = parse_lrc(lrc)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].text, "Valid line")

    def test_lyrics_sync_index_lookup(self):
        lines = [
            LyricLine(time_sec=10.0, text="Line 1"),
            LyricLine(time_sec=20.0, text="Line 2"),
            LyricLine(time_sec=30.0, text="Line 3"),
        ]
        self.assertEqual(find_active_lyric_index(lines, 5.0), -1)
        self.assertEqual(find_active_lyric_index(lines, 10.0), 0)
        self.assertEqual(find_active_lyric_index(lines, 15.0), 0)
        self.assertEqual(find_active_lyric_index(lines, 25.5), 1)
        self.assertEqual(find_active_lyric_index(lines, 40.0), 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_lyrics_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'monoflac'`

- [ ] **Step 3: Implement `monoflac/core/lyrics_parser.py`**

Implement regex-based timestamp matching `\[(\d{2}):(\d{2})(?:\.(\d+))?\]`, sorting by `time_sec`, binary search / linear lookup for active lyric line, and file/embedded tag reader.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_lyrics_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add monoflac/core/lyrics_parser.py tests/test_lyrics_parser.py
git commit -m "feat: add synced LRC lyrics parser"
```

---

### Task 2: Playlist & Metadata Manager

**Files:**
- Create: `monoflac/core/playlist_manager.py`
- Test: `tests/test_playlist_manager.py`

**Interfaces:**
- Consumes: `mutagen`
- Produces:
  - `TrackInfo(path: str, title: str, artist: str, album: str, duration: float, sample_rate: int, bit_depth: int, channels: int)`
  - `extract_track_info(file_path: str) -> TrackInfo`
  - `Playlist(name: str, tracks: list[TrackInfo])`
  - `PlaylistManager(config_path: str | None)` with methods:
    - `create_playlist(name: str)`
    - `remove_playlist(name: str)`
    - `add_paths_to_playlist(name: str, paths: list[str])`
    - `remove_track(name: str, index: int)`
    - `save()`, `load()`
    - `parse_uri_list(uri_data: str) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_playlist_manager.py
import unittest
import tempfile
import os
from monoflac.core.playlist_manager import PlaylistManager, parse_uri_list

class TestPlaylistManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "playlists.json")
        self.manager = PlaylistManager(config_path=self.config_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_switch_playlist(self):
        self.manager.create_playlist("Hi-Res Favorites")
        self.assertIn("Hi-Res Favorites", self.manager.get_playlist_names())

    def test_parse_drag_drop_uris(self):
        uri_data = "file:///home/user/Music/Song%20One.flac\r\nfile:///home/user/Music/Song%20Two.flac\r\n"
        paths = parse_uri_list(uri_data)
        self.assertEqual(paths, ["/home/user/Music/Song One.flac", "/home/user/Music/Song Two.flac"])

    def test_missing_file_handling(self):
        info = self.manager.extract_track_info("/non/existent/audio.flac")
        self.assertEqual(info.title, "audio.flac")
        self.assertEqual(info.duration, 0.0)

    def test_save_and_load_persistence(self):
        self.manager.create_playlist("Jazz")
        self.manager.save()
        manager2 = PlaylistManager(config_path=self.config_path)
        self.assertIn("Jazz", manager2.get_playlist_names())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_playlist_manager.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `monoflac/core/playlist_manager.py`**

Implement `TrackInfo`, `PlaylistManager` with JSON serialization to config path, URI decoding via `urllib.parse.unquote`, recursive directory scanning for `.flac` and `.wav` audio files, and metadata extraction with `mutagen.flac.FLAC`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_playlist_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add monoflac/core/playlist_manager.py tests/test_playlist_manager.py
git commit -m "feat: add playlist manager with persistence and URI parsing"
```

---

### Task 3: Hi-Res Audio Engine

**Files:**
- Create: `monoflac/core/audio_engine.py`
- Test: `tests/test_audio_engine.py`

**Interfaces:**
- Consumes: GStreamer 1.0 (`Gst`)
- Produces:
  - `AudioEngine(output_mode: str = "auto", alsa_device: str = "default")` with methods:
    - `load(file_path: str)`
    - `play()`
    - `pause()`
    - `stop()`
    - `seek(position_sec: float)`
    - `get_position() -> float`
    - `get_duration() -> float`
    - `set_volume(volume: float)`
    - `set_on_eos(callback)`
    - `get_audio_format() -> dict` (sample_rate, channels, bit_depth)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_audio_engine.py
import unittest
from monoflac.core.audio_engine import AudioEngine

class TestAudioEngine(unittest.TestCase):
    def test_engine_init(self):
        engine = AudioEngine(output_mode="auto")
        self.assertFalse(engine.is_playing)
        self.assertEqual(engine.get_position(), 0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_audio_engine.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `monoflac/core/audio_engine.py`**

Implement GStreamer pipeline `playbin` or custom bin with `flacparse ! flacdec ! alsasink` or `autoaudiosink`, bus watching, accurate state query, nanosecond duration & position queries, and EOS (end of stream) signal emission.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_audio_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add monoflac/core/audio_engine.py tests/test_audio_engine.py
git commit -m "feat: add GStreamer Hi-Res audio engine with direct ALSA support"
```

---

### Task 4: Monochrome CSS & Theme

**Files:**
- Create: `monoflac/ui/theme.css`
- Create: `monoflac/ui/theme.py`
- Test: `tests/test_theme.py`

**Interfaces:**
- Consumes: GTK 3 `Gtk.CssProvider`
- Produces:
  - `apply_monochrome_theme()`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_theme.py
import unittest
from monoflac.ui.theme import get_css_content

class TestTheme(unittest.TestCase):
    def test_theme_css_contains_monochrome_colors(self):
        css = get_css_content()
        self.assertIn("#000000", css)
        self.assertIn("#ffffff", css)
        # Ensure transitions and animations are explicitly turned off
        self.assertIn("transition: none;", css)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_theme.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `theme.css` and `theme.py`**

Define CSS with zero transitions, pure black background `#000000`, white borders `#ffffff` or muted `#333333`, mono monospace fonts for timestamps and sample rates, clean buttons, and active highlight colors.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_theme.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add monoflac/ui/theme.css monoflac/ui/theme.py tests/test_theme.py
git commit -m "feat: add strict monochrome high-contrast theme"
```

---

### Task 5: Lyrics & Playlist GUI Widgets

**Files:**
- Create: `monoflac/ui/lyrics_view.py`
- Create: `monoflac/ui/playlist_view.py`
- Test: `tests/test_widgets.py`

**Interfaces:**
- Consumes: `monoflac.core.lyrics_parser`, `monoflac.core.playlist_manager`, `gi.repository.Gtk`
- Produces:
  - `LyricsView(on_line_clicked_callback)`
  - `PlaylistView(on_track_activated_callback, on_files_dropped_callback)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_widgets.py
import unittest
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from monoflac.ui.lyrics_view import LyricsView
from monoflac.core.lyrics_parser import LyricLine

class TestWidgets(unittest.TestCase):
    def test_lyrics_view_set_lines(self):
        view = LyricsView(on_line_clicked=lambda t: None)
        lines = [LyricLine(10.0, "Lyric 1"), LyricLine(20.0, "Lyric 2")]
        view.set_lyrics(lines)
        self.assertEqual(len(view.lines), 2)
        view.set_active_time(15.0)
        self.assertEqual(view.active_index, 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_widgets.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `lyrics_view.py` and `playlist_view.py`**

Implement:
- `LyricsView`: Gtk.ScrolledWindow with a ListBox or Gtk.TextView, auto-scrolling to active line without smooth scroll delays, click-to-seek callback.
- `PlaylistView`: Gtk.TreeView with columns for `#`, `Title`, `Artist`, `Duration`, `Format/Hi-Res`. Drag-and-drop target accepting `text/uri-list`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_widgets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add monoflac/ui/lyrics_view.py monoflac/ui/playlist_view.py tests/test_widgets.py
git commit -m "feat: add lyrics view and drag-and-drop playlist view"
```

---

### Task 6: Main Window & System Integration

**Files:**
- Create: `monoflac/ui/main_window.py`
- Test: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `AudioEngine`, `PlaylistManager`, `LyricsView`, `PlaylistView`, `theme`
- Produces:
  - `MainWindow(application)` with full playback loop, timer ticks (updating seek bar and synced lyrics), playlist switching tab bar, and file-open dialogs.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_main_window.py
import unittest
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from monoflac.ui.main_window import MainWindow

class TestMainWindow(unittest.TestCase):
    def test_window_creation(self):
        win = MainWindow()
        self.assertIsNotNone(win)
        self.assertIn("MonoFLAC", win.get_title())
        win.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_main_window.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `monoflac/ui/main_window.py`**

Connect:
- AudioEngine playback events + GObject timeout (100ms) for clock & seek slider.
- Sync active lyric line in real-time.
- Multi-playlist selector (add playlist, switch playlist, delete playlist).
- Drag and drop from file manager directly into playlist.
- Hi-Res status badges (`[HI-RES 24-bit/96kHz]` or `[LOSSLESS 16-bit/44.1kHz]`).
- Bit-perfect output toggle (Direct ALSA vs Auto).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_main_window.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add monoflac/ui/main_window.py tests/test_main_window.py
git commit -m "feat: implement main application window and playback coordination"
```

---

### Task 7: App Entry Point & AppImage Packaging

**Files:**
- Create: `monoflac/__init__.py`
- Create: `monoflac/main.py`
- Create: `monoflac.desktop`
- Create: `build_appimage.sh`
- Test: `tests/test_app_entry.py`

**Interfaces:**
- Consumes: `monoflac.ui.main_window`
- Produces:
  - CLI runner `python3 -m monoflac.main`
  - Shell runner `bin/monoflac`
  - AppImage packaging script `build_appimage.sh`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_app_entry.py
import unittest
import os
import subprocess

class TestAppEntry(unittest.TestCase):
    def test_desktop_file_exists(self):
        self.assertTrue(os.path.exists("monoflac.desktop"))

    def test_build_script_exists_and_executable(self):
        self.assertTrue(os.path.exists("build_appimage.sh"))
        self.assertTrue(os.access("build_appimage.sh", os.X_OK))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_app_entry.py -v`
Expected: FAIL

- [ ] **Step 3: Implement entry point and build script**

Create `monoflac/main.py`, `monoflac.desktop`, launcher script `bin/monoflac`, and `build_appimage.sh` that bundles the application directory with AppRun into a standalone AppImage/portable directory.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_app_entry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add monoflac/ main.py bin/ monoflac.desktop build_appimage.sh tests/test_app_entry.py
git commit -m "feat: add application launcher and AppImage build script"
```
