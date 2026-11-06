from typing import List, Callable, Optional
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Pango
from monoflac.core.lyrics_parser import LyricLine, find_active_lyric_index

class LyricsView(Gtk.ScrolledWindow):
    """
    Displays time-synced lyrics with instant line highlighting and click-to-seek support.
    """
    def __init__(self, on_line_clicked: Optional[Callable[[float], None]] = None):
        super().__init__()
        self.on_line_clicked = on_line_clicked
        self.lines: List[LyricLine] = []
        self.active_index: int = -1
        self._row_labels: List[Gtk.Label] = []

        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_overlay_scrolling(False)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_box.get_style_context().add_class("lyrics-box")
        self.list_box.connect("row-activated", self._on_row_activated)

        self.add(self.list_box)
        self._show_empty_message("No lyrics loaded")

    def _show_empty_message(self, message: str) -> None:
        for child in self.list_box.get_children():
            self.list_box.remove(child)
        self._row_labels.clear()

        row = Gtk.ListBoxRow()
        label = Gtk.Label(label=message)
        label.get_style_context().add_class("dim-label")
        label.set_xalign(0.5)
        label.set_yalign(0.5)
        label.set_margin_top(40)
        label.set_margin_bottom(40)
        row.add(label)
        self.list_box.add(row)
        self.list_box.show_all()

    def set_lyrics(self, lines: List[LyricLine]) -> None:
        self.lines = lines
        self.active_index = -1
        self._row_labels.clear()

        for child in self.list_box.get_children():
            self.list_box.remove(child)

        if not self.lines:
            self._show_empty_message("No synced lyrics available (.lrc)")
            return

        for idx, item in enumerate(self.lines):
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=item.text if item.text else "—")
            label.set_xalign(0.0)
            label.set_yalign(0.5)
            label.set_line_wrap(True)
            label.get_style_context().add_class("lyric-line-inactive")

            row.add(label)
            self._row_labels.append(label)
            self.list_box.add(row)

        self.list_box.show_all()

    def set_active_time(self, time_sec: float) -> None:
        if not self.lines:
            return

        new_index = find_active_lyric_index(self.lines, time_sec)
        if new_index == self.active_index:
            return

        # Demote previously active row
        if 0 <= self.active_index < len(self._row_labels):
            old_label = self._row_labels[self.active_index]
            old_label.get_style_context().remove_class("lyric-line-active")
            old_label.get_style_context().add_class("lyric-line-inactive")
            old_text = self.lines[self.active_index].text or "—"
            old_label.set_text(old_text)

        self.active_index = new_index

        # Promote newly active row
        if 0 <= new_index < len(self._row_labels):
            active_label = self._row_labels[new_index]
            active_label.get_style_context().remove_class("lyric-line-inactive")
            active_label.get_style_context().add_class("lyric-line-active")
            active_text = f"▶  {self.lines[new_index].text or '—'}"
            active_label.set_text(active_text)

            # Auto-scroll to center the active row
            rows = self.list_box.get_children()
            if 0 <= new_index < len(rows):
                target_row = rows[new_index]
                adj = self.get_vadjustment()
                if adj is not None:
                    alloc = target_row.get_allocation()
                    target_y = alloc.y - (adj.get_page_size() / 2) + (alloc.height / 2)
                    adj.set_value(max(0.0, min(target_y, adj.get_upper() - adj.get_page_size())))

    def _on_row_activated(self, box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        rows = self.list_box.get_children()
        try:
            idx = rows.index(row)
            if 0 <= idx < len(self.lines) and self.on_line_clicked:
                self.on_line_clicked(self.lines[idx].time_sec)
        except ValueError:
            pass
