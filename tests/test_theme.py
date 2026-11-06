import unittest
from monoflac.ui.theme import get_css_content, apply_monochrome_theme

class TestTheme(unittest.TestCase):
    def test_theme_css_contains_monochrome_colors(self):
        css = get_css_content()
        self.assertIn("#000000", css)
        self.assertIn("#ffffff", css)
        self.assertIn("transition-duration: 0s", css)

    def test_apply_theme_function_callable(self):
        try:
            apply_monochrome_theme()
        except Exception as e:
            self.fail(f"apply_monochrome_theme raised an exception: {e}")

if __name__ == "__main__":
    unittest.main()
