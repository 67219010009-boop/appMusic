import os
from typing import Optional
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

def get_css_path() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, "theme.css")

def get_css_content() -> str:
    path = get_css_path()
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def apply_monochrome_theme(custom_css: Optional[str] = None) -> None:
    """
    Loads and attaches the high-contrast monochrome stylesheet to the default Gdk screen.
    """
    css_data = custom_css if custom_css is not None else get_css_content()
    if not css_data:
        return

    provider = Gtk.CssProvider()
    provider.load_from_data(css_data.encode("utf-8"))

    screen = Gdk.Screen.get_default()
    if screen is not None:
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
