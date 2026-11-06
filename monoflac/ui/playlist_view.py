import os
from typing import List, Callable, Optional
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Pango
from monoflac.core.playlist_manager import (
    TrackInfo,
    parse_uri_list,
    format_file_size,
    format_bitrate,
)

def format_seconds(seconds: float) -> str:
    total_sec = int(round(seconds))
    mins = total_sec // 60
    secs = total_sec % 60
    return f"{mins:02d}:{secs:02d}"

class PlaylistView(Gtk.Box):
    """
    Displays the current playlist in a crisp TreeView and supports Drag-and-Drop
    reordering of queue as well as external drops from Linux file managers.
    Includes dedicated columns for Duration, Bitrate (kbps), File Size (MB), and Format.
    """
    def __init__(
        self,
        on_track_activated: Optional[Callable[[int], None]] = None,
        on_files_dropped: Optional[Callable[[List[str]], None]] = None,
        on_remove_track: Optional[Callable[[int], None]] = None,
        on_tracks_reordered: Optional[Callable[[List[TrackInfo]], None]] = None,
        on_track_reordered: Optional[Callable[[List[int]], None]] = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.on_track_activated = on_track_activated
        self.on_files_dropped = on_files_dropped
        self.on_remove_track = on_remove_track
        self.on_tracks_reordered = on_tracks_reordered or (
            (lambda trks: on_track_reordered([i for i in range(len(trks))])) if on_track_reordered else None
        )
        self.on_track_reordered = on_track_reordered
        self.tracks: List[TrackInfo] = []
        self._is_updating: bool = False

        # Store: 0: num, 1: title, 2: artist, 3: duration, 4: bitrate, 5: size, 6: format, 7: index
        self.list_store = Gtk.ListStore(str, str, str, str, str, str, str, int)

        self.tree_view = Gtk.TreeView(model=self.list_store)
        self.tree_view.set_headers_visible(True)
        self.tree_view.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
        self.tree_view.connect("row-activated", self._on_row_activated)
        self.tree_view.connect("key-press-event", self._on_key_press)

        self._build_columns()
        self._setup_drag_and_drop()

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_overlay_scrolling(False)
        scrolled.add(self.tree_view)

        self.pack_start(scrolled, True, True, 0)

    def _build_columns(self) -> None:
        columns_def = [
            ("#", 0, 40, False),
            ("Title", 1, 180, True),
            ("Artist", 2, 130, False),
            ("Time", 3, 60, False),
            ("Bitrate", 4, 90, False),
            ("Size", 5, 80, False),
            ("Format / Quality", 6, 200, True),
        ]

        for title, col_idx, min_width, can_expand in columns_def:
            renderer = Gtk.CellRendererText()
            renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
            if col_idx in (0, 3, 4, 5, 6):
                renderer.set_property("family", "monospace")
                renderer.set_property("foreground", "#888888")
            else:
                renderer.set_property("foreground", "#ffffff")

            column = Gtk.TreeViewColumn(title, renderer, text=col_idx)
            column.set_min_width(min_width)
            column.set_resizable(True)
            if can_expand:
                column.set_expand(True)
            self.tree_view.append_column(column)

    def _setup_drag_and_drop(self) -> None:
        # Enable native internal row drag reordering
        self.tree_view.set_reorderable(True)
        # Enable external files drag-and-drop
        self.tree_view.drag_dest_add_uri_targets()
        self.tree_view.connect("drag-data-received", self._on_drag_data_received)
        self.list_store.connect("row-deleted", self._on_row_deleted)

    def _on_row_deleted(self, model, path) -> None:
        if self._is_updating or len(self.list_store) == 0:
            return

        # Re-sync track order from model
        new_tracks = []
        for i in range(len(self.list_store)):
            it = self.list_store.get_iter(Gtk.TreePath.new_from_indices([i]))
            orig_idx = self.list_store.get_value(it, 7)
            if 0 <= orig_idx < len(self.tracks):
                new_tracks.append(self.tracks[orig_idx])

        if len(new_tracks) == len(self.tracks):
            self.tracks = new_tracks
            for i in range(len(self.list_store)):
                it = self.list_store.get_iter(Gtk.TreePath.new_from_indices([i]))
                self.list_store.set_value(it, 0, f"{i + 1:02d}")
                self.list_store.set_value(it, 7, i)

            if self.on_tracks_reordered:
                self.on_tracks_reordered(self.tracks)
            elif self.on_track_reordered:
                self.on_track_reordered([i for i in range(len(self.tracks))])

    def _on_drag_data_received(
        self, widget, context, x, y, data, info, time
    ) -> None:
        target_name = data.get_target().name()
        # If this is internal row DnD, do NOT call context.finish() - let GTK handle row movement
        if target_name not in ("text/uri-list", "STRING", "UTF8_STRING", "text/plain"):
            return

        raw_text = data.get_text()
        if not raw_text and data.get_data():
            try:
                raw_text = data.get_data().decode("utf-8")
            except Exception:
                pass

        if raw_text and ("file://" in raw_text or "\n" in raw_text or os.path.sep in raw_text):
            paths = parse_uri_list(raw_text)
            if paths and self.on_files_dropped:
                self.on_files_dropped(paths)
                context.finish(True, False, time)
                return

        context.finish(False, False, time)

    def move_track(self, src_index: int, dest_index: int) -> bool:
        """Programmatically move a track from src_index to dest_index and update view."""
        if not (0 <= src_index < len(self.tracks)):
            return False
        if not (0 <= dest_index < len(self.tracks)):
            return False
        if src_index == dest_index:
            return True

        track = self.tracks.pop(src_index)
        self.tracks.insert(dest_index, track)

        self.set_tracks(self.tracks)

        if self.on_tracks_reordered:
            self.on_tracks_reordered(self.tracks)
        elif self.on_track_reordered:
            self.on_track_reordered([i for i in range(len(self.tracks))])

        return True

    def _on_row_activated(self, tree: Gtk.TreeView, path: Gtk.TreePath, column: Gtk.TreeViewColumn) -> None:
        model_iter = self.list_store.get_iter(path)
        if model_iter:
            track_idx = self.list_store.get_value(model_iter, 7)
            if self.on_track_activated:
                self.on_track_activated(track_idx)

    def _on_key_press(self, widget, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Delete:
            selected_idx = self.get_selected_track_index()
            if selected_idx is not None and self.on_remove_track:
                self.on_remove_track(selected_idx)
                return True
        return False

    def set_tracks(self, tracks: List[TrackInfo]) -> None:
        self._is_updating = True
        try:
            self.tracks = list(tracks)
            self.list_store.clear()
            for idx, t in enumerate(tracks):
                dur_str = format_seconds(t.duration)
                badge_str = t.format_badge()
                bitrate_str = format_bitrate(t.bitrate)
                size_str = format_file_size(t.file_size)
                self.list_store.append([
                    f"{idx + 1:02d}",
                    t.title,
                    t.artist,
                    dur_str,
                    bitrate_str,
                    size_str,
                    badge_str,
                    idx
                ])
        finally:
            self._is_updating = False

    def set_active_track_index(self, index: int) -> None:
        if 0 <= index < len(self.list_store):
            path = Gtk.TreePath.new_from_indices([index])
            self.tree_view.get_selection().select_path(path)
            self.tree_view.scroll_to_cell(path, None, True, 0.5, 0.0)

    def get_selected_track_index(self) -> Optional[int]:
        model, model_iter = self.tree_view.get_selection().get_selected()
        if model_iter:
            return model.get_value(model_iter, 7)
        return None
