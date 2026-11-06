import os
import random
from typing import Optional, List, Dict, Any
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango

from monoflac.core.audio_engine import AudioEngine, get_available_audio_devices
from monoflac.core.playlist_manager import PlaylistManager, TrackInfo, extract_track_info
from monoflac.core.lyrics_parser import load_lyrics_for_file
from monoflac.ui.playlist_view import PlaylistView, format_seconds
from monoflac.ui.lyrics_view import LyricsView
from monoflac.ui.theme import apply_monochrome_theme
from monoflac.ui.icons import get_icon_pixbuf

class MainWindow(Gtk.Window):
    """
    Main Application Window for MonoFLAC.
    Integrates the Hi-Res audio engine, playlist manager, and synced lyrics view
    within an ultra-responsive, zero-animation monochrome interface.
    """
    def __init__(self, application: Optional[Gtk.Application] = None):
        super().__init__(title="MonoFLAC — Hi-Res Lossless Audio Player")
        if application:
            self.set_application(application)

        self.set_default_size(1020, 660)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.get_style_context().add_class("monoflac-window")

        apply_monochrome_theme()

        # Core Components
        self.audio_engine = AudioEngine(output_mode="alsa", alsa_device="default")
        self.playlist_manager = PlaylistManager()
        self.playing_playlist_name: str = self.playlist_manager.get_active_playlist_name()
        self.current_track_index: int = -1
        self.is_seeking: bool = False
        
        # Dedicated Playback Modes
        # 0 = off, 1 = loop all, 2 = repeat one
        self.play_mode: int = 1  # default: loop all
        self.shuffle_mode: bool = False

        self._build_ui()
        self._load_active_playlist_tracks()

        # Connect signals
        self.audio_engine.set_on_eos(self._on_audio_eos)
        self.connect("destroy", self._on_window_destroy)
        self.connect("key-press-event", self._on_window_key_press)

        # 100ms clock tick for position & lyrics sync
        GLib.timeout_add(100, self._on_clock_tick)

    def _build_ui(self) -> None:
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_box)

        # Top Bar / Controls
        top_bar = self._create_top_bar()
        main_box.pack_start(top_bar, False, False, 0)

        # Center Paned (Left: Playlist, Right: Synced Lyrics)
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.set_position(580)

        # Left: Playlist section
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        left_box.set_margin_start(10)
        left_box.set_margin_end(6)
        left_box.set_margin_top(8)
        left_box.set_margin_bottom(8)

        self.playlist_view = PlaylistView(
            on_track_activated=self._on_track_activated,
            on_files_dropped=self._on_files_dropped,
            on_remove_track=self._on_remove_track,
            on_tracks_reordered=self._on_tracks_reordered,
        )
        left_box.pack_start(self.playlist_view, True, True, 0)
        self.paned.pack1(left_box, resize=True, shrink=False)

        # Right: Lyrics section
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        right_box.set_margin_start(6)
        right_box.set_margin_end(10)
        right_box.set_margin_top(8)
        right_box.set_margin_bottom(8)

        lyrics_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lyrics_title = Gtk.Label(label="SYNCED LYRICS (.lrc)")
        lyrics_title.set_xalign(0.0)
        lyrics_title.get_style_context().add_class("dim-label")
        lyrics_title.get_style_context().add_class("hi-res-badge")
        lyrics_header.pack_start(lyrics_title, False, False, 0)
        right_box.pack_start(lyrics_header, False, False, 0)

        self.lyrics_view = LyricsView(on_line_clicked=self._on_lyric_line_clicked)
        right_box.pack_start(self.lyrics_view, True, True, 0)
        self.paned.pack2(right_box, resize=True, shrink=False)

        main_box.pack_start(self.paned, True, True, 0)

        # Bottom Player Controls & Status
        bottom_bar = self._create_bottom_bar()
        main_box.pack_start(bottom_bar, False, False, 0)

    def _create_top_bar(self) -> Gtk.Box:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.set_margin_start(12)
        bar.set_margin_end(12)
        bar.set_margin_top(8)
        bar.set_margin_bottom(6)
        bar.get_style_context().add_class("titlebar")

        # Brand / App Title
        logo = Gtk.Label(label="MonoFLAC")
        logo.get_style_context().add_class("bitperfect-badge")
        bar.pack_start(logo, False, False, 0)

        # Playlist Combo Selector
        self.playlist_combo = Gtk.ComboBoxText()
        self._refresh_playlist_combo()
        self.playlist_combo.connect("changed", self._on_playlist_combo_changed)
        bar.pack_start(self.playlist_combo, False, False, 0)

        # Add Playlist Button [+]
        btn_add_pl = Gtk.Button(label="+")
        btn_add_pl.set_tooltip_text("Create new playlist")
        btn_add_pl.connect("clicked", self._on_add_playlist_clicked)
        bar.pack_start(btn_add_pl, False, False, 0)

        # Delete Playlist Button [-]
        btn_del_pl = Gtk.Button(label="—")
        btn_del_pl.set_tooltip_text("Delete current playlist")
        btn_del_pl.connect("clicked", self._on_delete_playlist_clicked)
        bar.pack_start(btn_del_pl, False, False, 0)

        # Spacer
        spacer = Gtk.Box()
        bar.pack_start(spacer, True, True, 0)

        # Add Files Button
        btn_add_files = Gtk.Button(label="+ Add Files / Folder")
        btn_add_files.set_tooltip_text("Open file chooser or drag files directly")
        btn_add_files.connect("clicked", self._on_add_files_clicked)
        bar.pack_start(btn_add_files, False, False, 0)

        # DAC / Audio Output Device Selector Button
        self.btn_audio_device = Gtk.Button(label="OUTPUT: ALSA (default) ▾")
        self.btn_audio_device.get_style_context().add_class("hi-res-badge")
        self.btn_audio_device.set_tooltip_text("Click to choose DAC / Sound Card output")
        self.btn_audio_device.connect("clicked", self._on_open_dac_menu)
        bar.pack_start(self.btn_audio_device, False, False, 0)

        return bar

    def _create_bottom_bar(self) -> Gtk.Box:
        bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        bar.set_margin_start(14)
        bar.set_margin_end(14)
        bar.set_margin_top(6)
        bar.set_margin_bottom(10)
        bar.get_style_context().add_class("titlebar")

        # Track Info & Badges Row
        info_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.lbl_now_playing = Gtk.Label(label="Ready to play")
        self.lbl_now_playing.set_xalign(0.0)
        self.lbl_now_playing.set_ellipsize(Pango.EllipsizeMode.END)
        info_row.pack_start(self.lbl_now_playing, True, True, 0)

        self.lbl_audio_badge = Gtk.Label(label="")
        self.lbl_audio_badge.get_style_context().add_class("hi-res-badge")
        info_row.pack_start(self.lbl_audio_badge, False, False, 0)
        bar.pack_start(info_row, False, False, 0)

        # Seek Bar Row
        seek_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.lbl_elapsed = Gtk.Label(label="00:00")
        self.lbl_elapsed.get_style_context().add_class("dim-label")
        seek_row.pack_start(self.lbl_elapsed, False, False, 0)

        self.seek_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 100.0, 1.0)
        self.seek_scale.set_draw_value(False)
        self.seek_scale.connect("button-press-event", self._on_seek_pressed)
        self.seek_scale.connect("button-release-event", self._on_seek_released)
        seek_row.pack_start(self.seek_scale, True, True, 0)

        self.lbl_total = Gtk.Label(label="00:00")
        self.lbl_total.get_style_context().add_class("dim-label")
        seek_row.pack_start(self.lbl_total, False, False, 0)
        bar.pack_start(seek_row, False, False, 0)

        # Controls & Volume Row
        ctrl_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.btn_prev = Gtk.Button(label="|<")
        self.btn_prev.set_tooltip_text("Previous track (or restart if > 5s)")
        self.btn_prev.connect("clicked", lambda b: self.play_previous())
        ctrl_row.pack_start(self.btn_prev, False, False, 0)

        self.btn_play_pause = Gtk.Button(label="▶")
        self.btn_play_pause.set_tooltip_text("Play / Pause (Space)")
        self.btn_play_pause.connect("clicked", lambda b: self.toggle_play_pause())
        ctrl_row.pack_start(self.btn_play_pause, False, False, 0)

        self.btn_stop = Gtk.Button(label="■")
        self.btn_stop.set_tooltip_text("Stop")
        self.btn_stop.connect("clicked", lambda b: self.stop_playback())
        ctrl_row.pack_start(self.btn_stop, False, False, 0)

        self.btn_next = Gtk.Button(label=">|")
        self.btn_next.set_tooltip_text("Next track")
        self.btn_next.connect("clicked", lambda b: self.play_next())
        ctrl_row.pack_start(self.btn_next, False, False, 0)

        # Play mode cycle button (3-state): OFF -> LOOP ALL -> REPEAT 1 -> OFF
        self.btn_play_mode = Gtk.Button()
        self.btn_play_mode.get_style_context().add_class("icon-btn")
        self.img_play_mode = Gtk.Image()
        self.btn_play_mode.set_image(self.img_play_mode)
        self.btn_play_mode.set_always_show_image(True)
        self.btn_play_mode.connect("clicked", self._on_cycle_play_mode)
        ctrl_row.pack_start(self.btn_play_mode, False, False, 0)

        # Shuffle button
        self.btn_shuffle = Gtk.Button()
        self.btn_shuffle.get_style_context().add_class("icon-btn")
        self.img_shuffle = Gtk.Image()
        self.btn_shuffle.set_image(self.img_shuffle)
        self.btn_shuffle.set_always_show_image(True)
        self.btn_shuffle.connect("clicked", self._on_toggle_shuffle)
        ctrl_row.pack_start(self.btn_shuffle, False, False, 0)

        self._update_play_mode_ui()
        self._update_shuffle_ui()

        # Volume Controls
        self.lbl_vol = Gtk.Label(label="VOL")
        self.lbl_vol.get_style_context().add_class("dim-label")
        ctrl_row.pack_start(self.lbl_vol, False, False, 0)

        self.vol_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 1.0, 0.05)
        self.vol_scale.set_value(1.0)
        self.vol_scale.set_size_request(100, -1)
        self.vol_scale.set_draw_value(False)
        self.vol_scale.connect("value-changed", self._on_volume_changed)
        ctrl_row.pack_start(self.vol_scale, False, False, 0)

        bar.pack_start(ctrl_row, False, False, 0)
        return bar

    def _on_open_dac_menu(self, btn: Gtk.Button) -> None:
        """Presents a clean dropdown menu listing detected DACs and audio hardware."""
        devices = get_available_audio_devices()
        menu = Gtk.Menu()

        default_devs = [d for d in devices if d.get("type") == "default"]
        dac_devs = [d for d in devices if d.get("is_dac")]
        no_dac_devs = [d for d in devices if d.get("type") == "none"]
        alsa_devs = [d for d in devices if d.get("type") == "alsa" and not d.get("is_dac")]

        # 1. System Default
        for dev in default_devs:
            item = Gtk.MenuItem(label=dev["name"])
            item.connect("activate", self._on_select_dac, dev)
            menu.append(item)

        menu.append(Gtk.SeparatorMenuItem())

        # 2. DAC section (or 'DAC: ไม่มี')
        if dac_devs:
            for dev in dac_devs:
                item = Gtk.MenuItem(label=dev["name"])
                item.connect("activate", self._on_select_dac, dev)
                menu.append(item)
        else:
            item = Gtk.MenuItem(label="DAC: ไม่มี (ไม่พบ DAC ภายนอก)")
            item.set_sensitive(False)
            menu.append(item)

        # 3. Direct ALSA soundcards & endpoints
        if alsa_devs:
            menu.append(Gtk.SeparatorMenuItem())
            for dev in alsa_devs:
                item = Gtk.MenuItem(label=dev["name"])
                item.connect("activate", self._on_select_dac, dev)
                menu.append(item)

        menu.show_all()
        menu.popup_at_widget(btn, Gdk.Gravity.SOUTH_WEST, Gdk.Gravity.NORTH_WEST, Gtk.get_current_event())

    def _on_select_dac(self, item: Gtk.MenuItem, dev_info: Dict[str, Any]) -> None:
        dev_id = dev_info["device"]
        dev_name = dev_info["name"]

        if dev_id == "default":
            self.audio_engine.set_output_mode("auto")
            short_name = "Auto"
        elif dev_info.get("is_dac"):
            self.audio_engine.set_output_mode("alsa", device=dev_id)
            short_name = f"DAC ({dev_id})"
        else:
            self.audio_engine.set_output_mode("alsa", device=dev_id)
            short_name = f"ALSA ({dev_id})"

        self.btn_audio_device.set_label(f"OUTPUT: {short_name} ▾")

    def _refresh_playlist_combo(self) -> None:
        self.playlist_combo.remove_all()
        names = self.playlist_manager.get_playlist_names()
        active = self.playlist_manager.get_active_playlist_name()
        for idx, name in enumerate(names):
            self.playlist_combo.append_text(name)
            if name == active:
                self.playlist_combo.set_active(idx)

    def _load_active_playlist_tracks(self) -> None:
        tracks = self.playlist_manager.get_tracks()
        self.playlist_view.set_tracks(tracks)
        if self.playlist_manager.get_active_playlist_name() == self.playing_playlist_name:
            if 0 <= self.current_track_index < len(tracks):
                self.playlist_view.set_active_track_index(self.current_track_index)

    def _on_playlist_combo_changed(self, combo: Gtk.ComboBoxText) -> None:
        name = combo.get_active_text()
        if name and name in self.playlist_manager.get_playlist_names():
            self.playlist_manager.set_active_playlist(name)
            self._load_active_playlist_tracks()
            self.playlist_manager.save()

    def _on_add_playlist_clicked(self, btn: Gtk.Button) -> None:
        dialog = Gtk.Dialog(
            title="Create New Playlist",
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)
        )
        content_area = dialog.get_content_area()
        entry = Gtk.Entry()
        entry.set_placeholder_text("Playlist Name")
        entry.set_margin_start(12)
        entry.set_margin_end(12)
        entry.set_margin_top(12)
        entry.set_margin_bottom(12)
        content_area.add(entry)
        dialog.show_all()

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            name = entry.get_text().strip()
            if name:
                if self.playlist_manager.create_playlist(name):
                    self.playlist_manager.set_active_playlist(name)
                    self._refresh_playlist_combo()
                    self._load_active_playlist_tracks()
                    self.playlist_manager.save()
        dialog.destroy()

    def _on_delete_playlist_clicked(self, btn: Gtk.Button) -> None:
        current = self.playlist_manager.get_active_playlist_name()
        names = self.playlist_manager.get_playlist_names()
        if len(names) <= 1:
            return

        if current == self.playing_playlist_name:
            self.stop_playback()
            self.current_track_index = -1

        self.playlist_manager.remove_playlist(current)
        self._refresh_playlist_combo()
        self._load_active_playlist_tracks()
        self.playlist_manager.save()

    def _on_add_files_clicked(self, btn: Gtk.Button) -> None:
        dialog = Gtk.FileChooserDialog(
            title="Add Audio Files to Playlist",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        )
        dialog.set_select_multiple(True)

        flac_filter = Gtk.FileFilter()
        flac_filter.set_name("Lossless Audio (*.flac, *.wav)")
        flac_filter.add_pattern("*.flac")
        flac_filter.add_pattern("*.FLAC")
        flac_filter.add_pattern("*.wav")
        flac_filter.add_pattern("*.WAV")
        dialog.add_filter(flac_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("All Files")
        all_filter.add_pattern("*")
        dialog.add_filter(all_filter)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            files = dialog.get_filenames()
            if files:
                active_pl = self.playlist_manager.get_active_playlist_name()
                self.playlist_manager.add_paths_to_playlist(active_pl, files)
                self._load_active_playlist_tracks()
        dialog.destroy()

    def _on_track_activated(self, index: int) -> None:
        active_pl = self.playlist_manager.get_active_playlist_name()
        self.play_track_at_index(index, playlist_name=active_pl)

    def _on_files_dropped(self, paths: List[str]) -> None:
        active_pl = self.playlist_manager.get_active_playlist_name()
        count = self.playlist_manager.add_paths_to_playlist(active_pl, paths)
        if count > 0:
            self._load_active_playlist_tracks()
            if not self.audio_engine.is_playing and self.current_track_index == -1:
                tracks = self.playlist_manager.get_tracks()
                if tracks:
                    self.play_track_at_index(0, playlist_name=active_pl)

    def _on_remove_track(self, index: int) -> None:
        active_pl = self.playlist_manager.get_active_playlist_name()
        if active_pl == self.playing_playlist_name:
            if index < self.current_track_index:
                self.current_track_index -= 1
            elif index == self.current_track_index:
                self.stop_playback()
                self.current_track_index = -1

        self.playlist_manager.remove_track(active_pl, index)
        self._load_active_playlist_tracks()
        self.playlist_manager.save()

    def play_track_at_index(self, index: int, playlist_name: Optional[str] = None) -> bool:
        target_pl = playlist_name if playlist_name is not None else self.playlist_manager.get_active_playlist_name()
        tracks = self.playlist_manager.get_tracks(target_pl)
        if not (0 <= index < len(tracks)):
            return False

        track = tracks[index]
        self.playing_playlist_name = target_pl
        self.current_track_index = index

        if self.playlist_manager.get_active_playlist_name() == self.playing_playlist_name:
            self.playlist_view.set_active_track_index(index)

        # Load file in audio engine
        if not self.audio_engine.load(track.path):
            self.lbl_now_playing.set_text(f"Error loading: {os.path.basename(track.path)}")
            return False

        # Load lyrics
        lyrics = load_lyrics_for_file(track.path)
        self.lyrics_view.set_lyrics(lyrics)

        # Update labels
        dur = track.duration if track.duration > 0 else self.audio_engine.get_duration()
        self.lbl_total.set_text(format_seconds(dur))
        self.seek_scale.set_range(0.0, max(1.0, dur))
        self.lbl_now_playing.set_text(f"{track.title} — {track.artist} [{track.album}]")
        self.lbl_audio_badge.set_text(track.format_badge())

        self.audio_engine.play()
        self.btn_play_pause.set_label("||")
        return True

    def toggle_play_pause(self) -> None:
        if self.audio_engine.is_playing:
            self.audio_engine.pause()
            self.btn_play_pause.set_label("▶")
        elif self.audio_engine.is_paused:
            self.audio_engine.play()
            self.btn_play_pause.set_label("||")
        else:
            tracks = self.playlist_manager.get_tracks(self.playing_playlist_name)
            if tracks:
                target_idx = max(0, self.current_track_index)
                self.play_track_at_index(target_idx, playlist_name=self.playing_playlist_name)

    def stop_playback(self) -> None:
        self.audio_engine.stop()
        self.btn_play_pause.set_label("▶")
        self.seek_scale.set_value(0.0)
        self.lbl_elapsed.set_text("00:00")
        self.lyrics_view.set_active_time(0.0)

    def play_next(self) -> None:
        tracks = self.playlist_manager.get_tracks(self.playing_playlist_name)
        if not tracks:
            return

        # If repeat single track is enabled, replay current track
        if self.play_mode == 2:
            self.play_track_at_index(self.current_track_index, playlist_name=self.playing_playlist_name)
            return

        attempts = 0
        total_tracks = len(tracks)

        while attempts < total_tracks:
            if self.shuffle_mode and total_tracks > 1:
                next_idx = random.choice([i for i in range(total_tracks) if i != self.current_track_index])
            else:
                next_idx = self.current_track_index + 1
                if next_idx >= total_tracks:
                    if self.play_mode == 1:
                        next_idx = 0
                    else:
                        self.stop_playback()
                        return

            if self.play_track_at_index(next_idx, playlist_name=self.playing_playlist_name):
                return
            else:
                self.current_track_index = next_idx
                attempts += 1

        self.stop_playback()

    def play_previous(self) -> None:
        tracks = self.playlist_manager.get_tracks(self.playing_playlist_name)
        if not tracks:
            return

        # Requirement: If track has played for more than 5.0 seconds, restart it from 0.0
        if self.audio_engine.get_position() > 5.0:
            self.audio_engine.seek(0.0)
            self.seek_scale.set_value(0.0)
            self.lbl_elapsed.set_text("00:00")
            self.lyrics_view.set_active_time(0.0)
        else:
            prev_idx = self.current_track_index - 1
            if prev_idx < 0:
                prev_idx = len(tracks) - 1
            self.play_track_at_index(prev_idx, playlist_name=self.playing_playlist_name)

    def _on_audio_eos(self) -> None:
        if self.play_mode == 2:
            self.audio_engine.seek(0.0)
            self.audio_engine.play()
        else:
            self.play_next()

    def _on_clock_tick(self) -> bool:
        if self.audio_engine.is_playing and not self.is_seeking:
            pos = self.audio_engine.get_position()
            self.seek_scale.set_value(pos)
            self.lbl_elapsed.set_text(format_seconds(pos))
            self.lyrics_view.set_active_time(pos)
        return True

    def _on_seek_pressed(self, scale, event) -> bool:
        self.is_seeking = True
        return False

    def _on_seek_released(self, scale, event) -> bool:
        target_sec = self.seek_scale.get_value()
        self.audio_engine.seek(target_sec)
        self.lyrics_view.set_active_time(target_sec)
        self.is_seeking = False
        return False

    def _on_lyric_line_clicked(self, time_sec: float) -> None:
        self.audio_engine.seek(time_sec)
        self.seek_scale.set_value(time_sec)
        self.lbl_elapsed.set_text(format_seconds(time_sec))
        self.lyrics_view.set_active_time(time_sec)

    def _on_volume_changed(self, scale: Gtk.Scale) -> None:
        val = scale.get_value()
        self.audio_engine.set_volume(val)

    def _on_toggle_shuffle(self, btn: Gtk.Button) -> None:
        self.shuffle_mode = not self.shuffle_mode
        self._update_shuffle_ui()

    def _on_cycle_play_mode(self, btn: Gtk.Button) -> None:
        # cycle: 1 (LOOP ALL) -> 2 (REPEAT 1) -> 0 (OFF) -> 1 (LOOP ALL)
        self.play_mode = (self.play_mode % 3) + 1
        if self.play_mode > 2:
            self.play_mode = 0
        self._update_play_mode_ui()

    def _update_play_mode_ui(self) -> None:
        if not hasattr(self, "img_play_mode"):
            return
        ctx = self.btn_play_mode.get_style_context()
        if self.play_mode == 0:  # OFF
            self.img_play_mode.set_from_pixbuf(get_icon_pixbuf("repeat_off", 18))
            self.btn_play_mode.set_tooltip_text("Repeat: Off")
            ctx.remove_class("icon-btn-active")
        elif self.play_mode == 1:  # LOOP ALL
            self.img_play_mode.set_from_pixbuf(get_icon_pixbuf("repeat_all", 18))
            self.btn_play_mode.set_tooltip_text("Repeat: All (Loop Playlist)")
            ctx.add_class("icon-btn-active")
        elif self.play_mode == 2:  # REPEAT ONE
            self.img_play_mode.set_from_pixbuf(get_icon_pixbuf("repeat_one", 18))
            self.btn_play_mode.set_tooltip_text("Repeat: One (Current Track)")
            ctx.add_class("icon-btn-active")

    def _update_shuffle_ui(self) -> None:
        if not hasattr(self, "img_shuffle"):
            return
        ctx = self.btn_shuffle.get_style_context()
        if self.shuffle_mode:
            self.img_shuffle.set_from_pixbuf(get_icon_pixbuf("shuffle_on", 18))
            self.btn_shuffle.set_tooltip_text("Shuffle: On")
            ctx.add_class("icon-btn-active")
        else:
            self.img_shuffle.set_from_pixbuf(get_icon_pixbuf("shuffle_off", 18))
            self.btn_shuffle.set_tooltip_text("Shuffle: Off")
            ctx.remove_class("icon-btn-active")

    @property
    def btn_loop_all(self) -> Gtk.Button:
        return self.btn_play_mode

    @property
    def loop_all_enabled(self) -> bool:
        return self.play_mode == 1

    @loop_all_enabled.setter
    def loop_all_enabled(self, val: bool) -> None:
        if val:
            self.play_mode = 1
        elif self.play_mode == 1:
            self.play_mode = 0
        self._update_play_mode_ui()

    @property
    def repeat_one_enabled(self) -> bool:
        return self.play_mode == 2

    @repeat_one_enabled.setter
    def repeat_one_enabled(self, val: bool) -> None:
        if val:
            self.play_mode = 2
        elif self.play_mode == 2:
            self.play_mode = 0
        self._update_play_mode_ui()

    def _on_tracks_reordered(self, new_tracks: List[TrackInfo]) -> None:
        active_pl = self.playlist_manager.get_active_playlist_name()
        old_tracks = self.playlist_manager.get_tracks(active_pl)
        if self.playing_playlist_name == active_pl and 0 <= self.current_track_index < len(old_tracks):
            playing_track = old_tracks[self.current_track_index]
            self.current_track_index = next(
                (idx for idx, t in enumerate(new_tracks) if t is playing_track),
                self.current_track_index
            )
        self.playlist_manager.playlists[active_pl] = list(new_tracks)
        self.playlist_manager.save()

    def _on_track_reordered(self, new_order: List[int]) -> None:
        active_pl = self.playlist_manager.get_active_playlist_name()
        old_tracks = self.playlist_manager.get_tracks(active_pl)
        if not old_tracks:
            return
        valid_indices = [i for i in new_order if 0 <= i < len(old_tracks)]
        if len(valid_indices) == len(old_tracks):
            new_tracks = [old_tracks[i] for i in valid_indices]
            self._on_tracks_reordered(new_tracks)

    def _on_window_key_press(self, widget, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_space:
            self.toggle_play_pause()
            return True
        elif event.keyval == Gdk.KEY_Left:
            new_pos = max(0.0, self.audio_engine.get_position() - 5.0)
            self.audio_engine.seek(new_pos)
            self.seek_scale.set_value(new_pos)
            self.lbl_elapsed.set_text(format_seconds(new_pos))
            self.lyrics_view.set_active_time(new_pos)
            return True
        elif event.keyval == Gdk.KEY_Right:
            new_pos = self.audio_engine.get_position() + 5.0
            self.audio_engine.seek(new_pos)
            self.seek_scale.set_value(new_pos)
            self.lbl_elapsed.set_text(format_seconds(new_pos))
            self.lyrics_view.set_active_time(new_pos)
            return True
        elif event.keyval == Gdk.KEY_Up:
            self.vol_scale.set_value(min(1.0, self.vol_scale.get_value() + 0.05))
            return True
        elif event.keyval == Gdk.KEY_Down:
            self.vol_scale.set_value(max(0.0, self.vol_scale.get_value() - 0.05))
            return True
        return False

    def _on_window_destroy(self, widget) -> None:
        self.audio_engine.release_device()
        self.playlist_manager.save()
