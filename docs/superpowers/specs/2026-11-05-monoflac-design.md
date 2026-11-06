# MonoFLAC - Hi-Res Lossless Audio Player Design Document

## 1. Goal & Intent
Build an ultra-lightweight, bit-perfect, monochrome desktop music player specifically designed for FLAC and Hi-Res audio (up to 24-bit/192kHz or higher) on Linux. The player emphasizes pure audio fidelity, zero animations, sub-50MB RAM footprint, synced LRC lyrics display, multi-playlist management with drag-and-drop, and state persistence.

## 2. Requirements & Features
1. **Audio Engine & Hi-Res Bit-Perfect Output**:
   - Native FLAC decoding via GStreamer / libflac.
   - Bit-perfect output support (direct ALSA hardware passthrough bypass or auto sink without resampling or software tone alteration).
   - Display detailed audio specs: Bit depth (e.g. 16-bit, 24-bit), Sample Rate (e.g. 44.1 kHz, 96.0 kHz, 192.0 kHz), Bitrate, and Channels.
   - Transport controls: Play, Pause, Stop, Previous, Next, Seek (precise nanosecond seek), Volume.
2. **Synced Lyrics (.lrc)**:
   - Synchronized line-by-line lyrics display.
   - Auto-detection from local `.lrc` files in the same directory, or embedded `LYRICS` Vorbis tags in FLAC.
   - Current line highlighting with active cursor marker (`▶ `) without smooth animation.
   - Click-to-seek: clicking a lyric line jumps directly to that timestamp.
3. **Playlist Management & Drag-and-Drop**:
   - Multiple named playlists (e.g., Default, Favorites, Custom).
   - Add/Remove/Switch playlists.
   - Drag and drop audio files and directories from file managers (e.g. Nautilus, Dolphin, PCManFM).
   - Persistence: Automatically save playlists and tracks to `~/.config/monoflac/playlists.json` so state is restored on next launch.
4. **UI & Aesthetics**:
   - Pure black & white / monochrome theme (`#000000` pitch black, `#ffffff` pure white, `#222222` dark grey borders).
   - Sharp, high-contrast, instant UI response. Zero animations or CSS transitions.
5. **Portability & Packaging**:
   - Linux standalone executable and AppImage packaging script (`build_appimage.sh`).

## 3. Tech Stack
- **Language**: Python 3.12
- **GUI Framework**: GTK 3 (via PyGObject `gi.repository.Gtk`), Gdk, Pango
- **Audio Pipeline**: GStreamer 1.0 (`Gst`) with `flacparse`, `flacdec`, `alsasink` / `autoaudiosink`
- **Metadata**: `mutagen.flac` / `mutagen`
- **Testing**: Python `unittest`
