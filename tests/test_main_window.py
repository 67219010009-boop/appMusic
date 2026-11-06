import unittest
import tempfile
import os
import gi
from unittest.mock import MagicMock

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
from monoflac.ui.main_window import MainWindow
from monoflac.core.playlist_manager import TrackInfo
from monoflac.core.lyrics_parser import LyricLine

class TestMainWindow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.win = MainWindow()
        self.win.playlist_manager.config_path = os.path.join(self.temp_dir.name, "playlists.json")
        self.win.playlist_manager.playlists = {"Default": []}
        self.win.playlist_manager.set_active_playlist("Default")

    def tearDown(self):
        self.win.destroy()
        self.temp_dir.cleanup()

    def test_main_window_creation(self):
        self.assertIsNotNone(self.win)
        self.assertIn("MonoFLAC", self.win.get_title())
        self.assertIsNotNone(self.win.playlist_view)
        self.assertIsNotNone(self.win.lyrics_view)
        self.assertIsNotNone(self.win.audio_engine)
        self.assertIsNotNone(self.win.playlist_manager)

    def test_no_emojis_in_ui_labels(self):
        emojis = ["🔁", "🔀", "🔊", "🎵", "🎶"]
        for widget in [self.win.btn_play_mode, self.win.btn_shuffle, self.win.lbl_vol]:
            label = widget.get_label() if hasattr(widget, "get_label") else widget.get_text()
            tooltip = widget.get_tooltip_text()
            for emo in emojis:
                if label:
                    self.assertNotIn(emo, label)
                if tooltip:
                    self.assertNotIn(emo, tooltip)

    def test_previous_button_5_second_threshold(self):
        t1 = TrackInfo("/tmp/1.flac", "Track 1", "Artist", "Album", 200.0)
        t2 = TrackInfo("/tmp/2.flac", "Track 2", "Artist", "Album", 200.0)
        self.win.playlist_manager.playlists["Default"] = [t1, t2]
        self.win._load_active_playlist_tracks()
        self.win.current_track_index = 1
        self.win.playing_playlist_name = "Default"
        self.win.audio_engine.seek = MagicMock()

        # Case 1: Playback time is 6.5s (> 5.0 seconds) -> Should RESTART current track
        self.win.audio_engine.get_position = MagicMock(return_value=6.5)
        self.win.play_previous()
        self.win.audio_engine.seek.assert_called_with(0.0)
        self.assertEqual(self.win.current_track_index, 1) # Remained on track 1!

        # Case 2: Playback time is 3.0s (<= 5.0 seconds) -> Should go to previous track (track 0)
        self.win.audio_engine.get_position = MagicMock(return_value=3.0)
        self.win.audio_engine.load = MagicMock(return_value=True)
        self.win.audio_engine.play = MagicMock()
        self.win.play_previous()
        self.assertEqual(self.win.current_track_index, 0) # Switched to track 0!

    def test_dedicated_loop_and_repeat_buttons(self):
        # Initial: play_mode = 1 (LOOP ALL), shuffle is OFF
        self.assertIsNotNone(self.win.btn_play_mode)
        self.assertIsNotNone(self.win.btn_shuffle)
        self.assertEqual(self.win.play_mode, 1)
        self.assertFalse(self.win.shuffle_mode)

    def test_play_mode_cycle(self):
        # Initial: play_mode = 1 (LOOP ALL)
        self.assertEqual(self.win.play_mode, 1)
        self.win._on_cycle_play_mode(self.win.btn_play_mode)
        self.assertEqual(self.win.play_mode, 2)  # REPEAT 1
        self.win._on_cycle_play_mode(self.win.btn_play_mode)
        self.assertEqual(self.win.play_mode, 0)  # OFF
        self.win._on_cycle_play_mode(self.win.btn_play_mode)
        self.assertEqual(self.win.play_mode, 1)  # Back to LOOP ALL

    def test_keyboard_seek_updates_ui_immediately(self):
        self.win.seek_scale.set_range(0.0, 200.0)
        self.win.audio_engine.get_position = MagicMock(return_value=10.0)
        self.win.audio_engine.seek = MagicMock()
        self.win.lyrics_view.set_lyrics([LyricLine(10.0, "Line 1"), LyricLine(20.0, "Line 2")])

        event = Gdk.EventKey()
        event.keyval = Gdk.KEY_Right
        handled = self.win._on_window_key_press(self.win, event)
        self.assertTrue(handled)
        self.win.audio_engine.seek.assert_called_with(15.0)
        self.assertEqual(self.win.seek_scale.get_value(), 15.0)
        self.assertEqual(self.win.lbl_elapsed.get_text(), "00:15")
        self.assertEqual(self.win.lyrics_view.active_index, 0)

    def test_skip_missing_files_on_play_next(self):
        t1 = TrackInfo("/nonexistent/1.flac", "Track 1", "Artist", "Album", 100.0)
        t2 = TrackInfo("/nonexistent/2.flac", "Track 2", "Artist", "Album", 100.0)
        self.win.playlist_manager.playlists["Default"] = [t1, t2]
        self.win.playlist_manager.set_active_playlist("Default")
        self.win.playing_playlist_name = "Default"
        self.win._load_active_playlist_tracks()

        self.win.audio_engine.load = MagicMock(return_value=False)
        self.win.play_next()
        self.assertIn("Error loading", self.win.lbl_now_playing.get_text())

    def test_playlist_switch_does_not_override_playing_playlist(self):
        self.win.playlist_manager.create_playlist("Playlist A")
        self.win.playlist_manager.create_playlist("Playlist B")
        self.win.playlist_manager.playlists["Playlist A"] = [
            TrackInfo("/tmp/a1.flac", "A1", "Artist", "Album", 100.0),
            TrackInfo("/tmp/a2.flac", "A2", "Artist", "Album", 100.0),
        ]
        self.win.playlist_manager.playlists["Playlist B"] = [
            TrackInfo("/tmp/b1.flac", "B1", "Artist", "Album", 100.0),
        ]
        self.win.playlist_manager.set_active_playlist("Playlist A")
        self.win.audio_engine.load = MagicMock(return_value=True)
        self.win.audio_engine.play = MagicMock()
        self.win.play_track_at_index(1)
        self.assertEqual(self.win.playing_playlist_name, "Playlist A")
        self.assertEqual(self.win.current_track_index, 1)

        self.win.playlist_manager.set_active_playlist("Playlist B")
        self.win._load_active_playlist_tracks()

        self.win.play_next()
        self.assertEqual(self.win.playing_playlist_name, "Playlist A")

    def test_open_dac_menu_and_selection(self):
        # Verify opening the DAC dropdown menu populates correctly
        self.win._on_open_dac_menu(self.win.btn_audio_device)
        self.assertIsNotNone(self.win.btn_audio_device)

        # Test selecting a DAC or Auto device
        dev_auto = {"device": "default", "name": "System Default", "is_dac": False, "type": "default"}
        self.win._on_select_dac(None, dev_auto)
        self.assertEqual(self.win.audio_engine.output_mode, "auto")
        self.assertIn("Auto", self.win.btn_audio_device.get_label())

        dev_dac = {"device": "hw:2,0", "name": "[DAC] USB Audio", "is_dac": True, "type": "alsa"}
        self.win._on_select_dac(None, dev_dac)
        self.assertEqual(self.win.audio_engine.output_mode, "alsa")
        self.assertEqual(self.win.audio_engine.alsa_device, "hw:2,0")
        self.assertIn("DAC", self.win.btn_audio_device.get_label())

    def test_reordering_updates_playing_track_index(self):
        t1 = TrackInfo("/tmp/1.flac", "Track 1", "Artist", "Album", 100.0)
        t2 = TrackInfo("/tmp/2.flac", "Track 2", "Artist", "Album", 200.0)
        t3 = TrackInfo("/tmp/3.flac", "Track 3", "Artist", "Album", 300.0)
        self.win.playlist_manager.playlists["Default"] = [t1, t2, t3]
        self.win.playing_playlist_name = "Default"
        self.win.current_track_index = 0  # Currently playing Track 1

        # Reorder queue: move Track 1 from index 0 to index 2: [t2, t3, t1]
        new_order_tracks = [t2, t3, t1]
        self.win._on_tracks_reordered(new_order_tracks)

        # Track 1 is now at index 2, so current_track_index must update to 2
        self.assertEqual(self.win.current_track_index, 2)
        self.assertEqual(self.win.playlist_manager.get_tracks("Default")[2].title, "Track 1")

if __name__ == "__main__":
    unittest.main()
