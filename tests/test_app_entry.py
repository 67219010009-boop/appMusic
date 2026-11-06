import unittest
import os

class TestAppEntry(unittest.TestCase):
    def test_desktop_file_exists(self):
        self.assertTrue(os.path.exists("monoflac.desktop"))
        with open("monoflac.desktop", "r") as f:
            content = f.read()
            self.assertIn("Name=MonoFLAC", content)
            self.assertIn("Exec=monoflac", content)

    def test_launcher_binary_exists_and_executable(self):
        self.assertTrue(os.path.exists("bin/monoflac"))
        self.assertTrue(os.access("bin/monoflac", os.X_OK))

    def test_build_script_exists_and_executable(self):
        self.assertTrue(os.path.exists("build_appimage.sh"))
        self.assertTrue(os.access("build_appimage.sh", os.X_OK))

if __name__ == "__main__":
    unittest.main()
