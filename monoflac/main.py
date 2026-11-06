import sys
import os
import signal
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from monoflac.ui.main_window import MainWindow

def main():
    # Allow terminal Ctrl+C to terminate application gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    win = MainWindow()

    # If audio files or directories were passed via command line
    if len(sys.argv) > 1:
        args = sys.argv[1:]
        valid_paths = [os.path.abspath(p) for p in args if os.path.exists(p)]
        if valid_paths:
            active_pl = win.playlist_manager.get_active_playlist_name()
            win.playlist_manager.add_paths_to_playlist(active_pl, valid_paths)
            win._load_active_playlist_tracks()
            win.play_track_at_index(0)

    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
