import unittest
import tempfile
import os
from unittest.mock import patch, MagicMock
from monoflac.core.playlist_manager import (
    PlaylistManager,
    TrackInfo,
    parse_uri_list,
    extract_track_info,
    format_file_size,
    format_bitrate,
)

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
        self.manager.set_active_playlist("Hi-Res Favorites")
        self.assertEqual(self.manager.get_active_playlist_name(), "Hi-Res Favorites")

    def test_parse_drag_drop_uris(self):
        uri_data = "file:///home/user/Music/Song%20One.flac\r\nfile:///home/user/Music/Song%20Two.flac\r\n#comment\r\n"
        paths = parse_uri_list(uri_data)
        self.assertEqual(paths, ["/home/user/Music/Song One.flac", "/home/user/Music/Song Two.flac"])

    def test_missing_file_handling(self):
        info = extract_track_info("/non/existent/audio.flac")
        self.assertEqual(info.title, "audio.flac")
        self.assertEqual(info.duration, 0.0)
        self.assertEqual(info.sample_rate, 0)
        self.assertEqual(info.bit_depth, 0)
        self.assertEqual(info.file_size, 0)
        self.assertEqual(info.bitrate, 0)

    def test_format_size_and_bitrate_helpers(self):
        self.assertEqual(format_file_size(86420000), "82.4 MB")
        self.assertEqual(format_file_size(0), "—")
        self.assertEqual(format_bitrate(2840000), "2840 kbps")
        self.assertEqual(format_bitrate(0), "—")

    def test_flac_metadata_extraction(self):
        dummy_flac = os.path.join(self.temp_dir.name, "hires_track.flac")
        content = b"fLaCdummy" * 10000
        with open(dummy_flac, "wb") as f:
            f.write(content)

        mock_flac = MagicMock()
        mock_flac.info.length = 245.5
        mock_flac.info.sample_rate = 96000
        mock_flac.info.bits_per_sample = 24
        mock_flac.info.channels = 2
        mock_flac.info.bitrate = 2854000
        mock_flac.get.side_effect = lambda k: {
            "title": ["Masterpiece"],
            "artist": ["Audiophile Artist"],
            "album": ["Hi-Res Sessions"]
        }.get(k)
        mock_flac.__getitem__.side_effect = lambda k: {
            "title": ["Masterpiece"],
            "artist": ["Audiophile Artist"],
            "album": ["Hi-Res Sessions"]
        }[k]

        with patch("mutagen.flac.FLAC", return_value=mock_flac):
            info = extract_track_info(dummy_flac)
            self.assertEqual(info.title, "Masterpiece")
            self.assertEqual(info.artist, "Audiophile Artist")
            self.assertEqual(info.sample_rate, 96000)
            self.assertEqual(info.bit_depth, 24)
            self.assertEqual(info.file_size, len(content))
            self.assertEqual(info.bitrate, 2854000)
            self.assertTrue(info.is_hi_res)
            self.assertIn("[HI-RES]", info.format_badge())
            self.assertIn("24-bit / 96.0 kHz", info.format_badge())
            self.assertIn("2854 kbps", info.format_badge())
            self.assertIn("MB", info.format_badge())

    def test_save_and_load_persistence(self):
        self.manager.create_playlist("Jazz")
        self.manager.set_active_playlist("Jazz")
        dummy_track = TrackInfo(
            path="/tmp/test.flac",
            title="Take Five",
            artist="Dave Brubeck",
            album="Time Out",
            duration=324.0,
            sample_rate=96000,
            bit_depth=24,
            channels=2,
            file_size=52428800,
            bitrate=1294000
        )
        self.manager.add_track_to_playlist("Jazz", dummy_track)
        self.manager.save()

        manager2 = PlaylistManager(config_path=self.config_path)
        self.assertIn("Jazz", manager2.get_playlist_names())
        self.assertEqual(manager2.get_active_playlist_name(), "Jazz")
        tracks = manager2.get_tracks("Jazz")
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].title, "Take Five")
        self.assertEqual(tracks[0].sample_rate, 96000)
        self.assertEqual(tracks[0].bit_depth, 24)
        self.assertEqual(tracks[0].file_size, 52428800)
        self.assertEqual(tracks[0].bitrate, 1294000)

    def test_remove_track_and_delete_playlist(self):
        self.manager.create_playlist("To Delete")
        dummy = TrackInfo("/tmp/1.flac", "Track 1", "Artist", "Album", 100.0, 44100, 16, 2)
        self.manager.add_track_to_playlist("To Delete", dummy)
        self.assertEqual(len(self.manager.get_tracks("To Delete")), 1)
        self.manager.remove_track("To Delete", 0)
        self.assertEqual(len(self.manager.get_tracks("To Delete")), 0)
        self.manager.remove_playlist("To Delete")
        self.assertNotIn("To Delete", self.manager.get_playlist_names())

    def test_move_track_in_playlist(self):
        self.manager.create_playlist("Queue")
        t1 = TrackInfo("/tmp/1.flac", "Track 1", "Artist", "Album", 100.0)
        t2 = TrackInfo("/tmp/2.flac", "Track 2", "Artist", "Album", 200.0)
        t3 = TrackInfo("/tmp/3.flac", "Track 3", "Artist", "Album", 300.0)
        self.manager.playlists["Queue"] = [t1, t2, t3]

        # Move track 0 to position 2: [t2, t3, t1]
        success = self.manager.move_track("Queue", 0, 2)
        self.assertTrue(success)
        tracks = self.manager.get_tracks("Queue")
        self.assertEqual(tracks[0].title, "Track 2")
        self.assertEqual(tracks[1].title, "Track 3")
        self.assertEqual(tracks[2].title, "Track 1")

        # Move track 2 back to position 0: [t1, t2, t3]
        success2 = self.manager.move_track("Queue", 2, 0)
        self.assertTrue(success2)
        tracks2 = self.manager.get_tracks("Queue")
        self.assertEqual(tracks2[0].title, "Track 1")
        self.assertEqual(tracks2[1].title, "Track 2")
        self.assertEqual(tracks2[2].title, "Track 3")

        # Out of bounds moves should return False
        self.assertFalse(self.manager.move_track("Queue", -1, 1))
        self.assertFalse(self.manager.move_track("Queue", 0, 99))
        self.assertFalse(self.manager.move_track("Nonexistent", 0, 1))

if __name__ == "__main__":
    unittest.main()
