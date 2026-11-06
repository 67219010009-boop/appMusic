import unittest
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from monoflac.core.lyrics_parser import LyricLine
from monoflac.core.playlist_manager import TrackInfo
from monoflac.ui.lyrics_view import LyricsView
from monoflac.ui.playlist_view import PlaylistView

class TestWidgets(unittest.TestCase):
    def test_lyrics_view_set_and_sync(self):
        clicked_times = []
        view = LyricsView(on_line_clicked=lambda t: clicked_times.append(t))
        
        lines = [LyricLine(10.0, "Line 1"), LyricLine(20.0, "Line 2")]
        view.set_lyrics(lines)
        self.assertEqual(len(view.lines), 2)

        view.set_active_time(5.0)
        self.assertEqual(view.active_index, -1)

        view.set_active_time(12.0)
        self.assertEqual(view.active_index, 0)

        view.set_active_time(25.0)
        self.assertEqual(view.active_index, 1)

    def test_playlist_view_tracks_and_selection(self):
        activated = []
        view = PlaylistView(
            on_track_activated=lambda idx: activated.append(idx),
            on_files_dropped=lambda paths: None,
            on_remove_track=lambda idx: None
        )
        tracks = [
            TrackInfo("/tmp/1.flac", "Song 1", "Artist 1", "Album", 180.0, 96000, 24, 2, file_size=40000000, bitrate=1777000),
            TrackInfo("/tmp/2.flac", "Song 2", "Artist 2", "Album", 200.0, 44100, 16, 2, file_size=20000000, bitrate=800000)
        ]
        view.set_tracks(tracks)
        self.assertEqual(len(view.list_store), 2)
        # Verify columns exist: #, Title, Artist, Time, Bitrate, Size, Quality
        self.assertEqual(view.list_store[0][4], "1777 kbps")
        self.assertEqual(view.list_store[0][5], "38.1 MB")
        view.set_active_track_index(1)
        self.assertEqual(view.get_selected_track_index(), 1)

    def test_playlist_view_drag_reorder_and_move_track(self):
        reordered_events = []
        view = PlaylistView(
            on_track_activated=lambda idx: None,
            on_files_dropped=lambda paths: None,
            on_remove_track=lambda idx: None,
            on_tracks_reordered=lambda trks: reordered_events.append(trks)
        )
        tracks = [
            TrackInfo("/tmp/1.flac", "Song 1", "Artist 1", "Album", 100.0),
            TrackInfo("/tmp/2.flac", "Song 2", "Artist 2", "Album", 200.0),
            TrackInfo("/tmp/3.flac", "Song 3", "Artist 3", "Album", 300.0)
        ]
        view.set_tracks(tracks)
        self.assertTrue(view.tree_view.get_reorderable())

        # Move track 0 to position 2
        success = view.move_track(0, 2)
        self.assertTrue(success)
        self.assertEqual(len(reordered_events), 1)
        self.assertEqual(reordered_events[0][0].title, "Song 2")
        self.assertEqual(reordered_events[0][1].title, "Song 3")
        self.assertEqual(reordered_events[0][2].title, "Song 1")

        # Check numbering column (#) in ListStore updated properly
        self.assertEqual(view.list_store[0][0], "01")
        self.assertEqual(view.list_store[1][0], "02")
        self.assertEqual(view.list_store[2][0], "03")

    def test_drag_data_received_internal_row_does_not_abort_context(self):
        from unittest.mock import MagicMock
        view = PlaylistView()
        context = MagicMock()
        data = MagicMock()
        data.get_target().name.return_value = "GTK_TREE_MODEL_ROW"

        # Calling _on_drag_data_received with GTK_TREE_MODEL_ROW should NOT call context.finish()
        view._on_drag_data_received(view.tree_view, context, 0, 0, data, 0, 1000)
        context.finish.assert_not_called()

if __name__ == "__main__":
    unittest.main()
