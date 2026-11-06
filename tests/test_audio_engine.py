import unittest
from unittest.mock import patch, MagicMock
from monoflac.core.audio_engine import AudioEngine, get_available_audio_devices

class TestAudioEngine(unittest.TestCase):
    def test_engine_init(self):
        engine = AudioEngine(output_mode="auto")
        self.assertFalse(engine.is_playing)
        self.assertFalse(engine.is_paused)
        self.assertEqual(engine.get_position(), 0.0)
        self.assertEqual(engine.get_duration(), 0.0)

    def test_volume_control_attenuation(self):
        engine = AudioEngine(output_mode="auto")
        engine.set_volume(0.8)
        self.assertAlmostEqual(engine.get_volume(), 0.8, places=2)
        # Verify internal volume element was updated
        self.assertIsNotNone(engine._volume_element)
        self.assertAlmostEqual(engine._volume_element.get_property("volume"), 0.8, places=2)
        engine.set_volume(0.0)
        self.assertEqual(engine.get_volume(), 0.0)
        self.assertEqual(engine._volume_element.get_property("volume"), 0.0)

    def test_output_mode_switch(self):
        engine = AudioEngine(output_mode="auto")
        self.assertEqual(engine.output_mode, "auto")
        engine.set_output_mode("alsa", device="default")
        self.assertEqual(engine.output_mode, "alsa")
        self.assertEqual(engine.alsa_device, "default")

    def test_get_audio_format_interface(self):
        engine = AudioEngine(output_mode="auto")
        fmt = engine.get_audio_format()
        self.assertIsInstance(fmt, dict)
        self.assertIn("sample_rate", fmt)
        self.assertIn("channels", fmt)
        self.assertIn("bit_depth", fmt)

    def test_get_available_audio_devices(self):
        devices = get_available_audio_devices()
        self.assertIsInstance(devices, list)
        self.assertGreater(len(devices), 0)
        self.assertEqual(devices[0]["device"], "default")

    def test_no_dacs_found_fallback(self):
        with patch("os.path.exists", return_value=False):
            devices = get_available_audio_devices()
            # If no hardware files exist, default and a notice should be returned
            self.assertTrue(any("ไม่มี" in d["name"] for d in devices))

if __name__ == "__main__":
    unittest.main()
