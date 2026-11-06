import unittest
import tempfile
import os
from monoflac.core.lyrics_parser import LyricLine, parse_lrc, find_active_lyric_index, load_lyrics_for_file

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

    def test_load_lyrics_from_disk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "song.flac")
            lrc_path = os.path.join(tmpdir, "song.lrc")
            with open(audio_path, "wb") as f:
                f.write(b"dummy")
            with open(lrc_path, "w", encoding="utf-8") as f:
                f.write("[00:01.00]First line\n[00:03.50]Second line\n")
            lines = load_lyrics_for_file(audio_path)
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0].text, "First line")

    def test_parse_lrc_long_minutes(self):
        lrc = "[105:20.50]Symphony Movement 3"
        lines = parse_lrc(lrc)
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines[0].time_sec, 105 * 60 + 20.5)
        self.assertEqual(lines[0].text, "Symphony Movement 3")

    def test_parse_enhanced_lrc_karaoke_tags(self):
        lrc = (
            "[00:47.841]<00:47.841>\n"
            "[00:54.041]v1:<00:54.041>突<00:54.318><00:54.495>風一吹<00:55.068><00:55.10>き<00:55.399><00:55.399>、<00:55.502><00:55.502>晴れ <00:55.857>\n"
            "[00:55.864]v1:<00:55.864>私は道の<00:56.629><00:56.629>上<00:57.366>\n"
            "[00:57.902]v1:<00:57.902>とう<00:58.174><00:58.423>とう<00:58.639><00:58.639>と<00:58.739><00:58.779>闊<00:58.907><00:58.907>歩 <00:59.291>\n"
        )
        lines = parse_lrc(lrc)
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0].text, "突風一吹き、晴れ")
        self.assertEqual(lines[1].text, "私は道の上")
        self.assertEqual(lines[2].text, "とうとうと闊歩")

if __name__ == "__main__":
    unittest.main()
