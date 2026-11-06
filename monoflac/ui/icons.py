import gi
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf, Gio

# Strict Monochrome SVG Icons (matching audio player standards & user reference screenshots)
# Zero colored emojis, zero external assets, fast in-memory rendering.

SVG_REPEAT_OFF = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#555555" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg">
  <polyline points="17 1 21 5 17 9"></polyline>
  <path d="M3 11V9a4 4 0 0 1 4-4h14"></path>
  <polyline points="7 23 3 19 7 15"></polyline>
  <path d="M21 13v2a4 4 0 0 1-4 4H3"></path>
</svg>"""

SVG_REPEAT_ALL = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg">
  <polyline points="17 1 21 5 17 9"></polyline>
  <path d="M3 11V9a4 4 0 0 1 4-4h14"></path>
  <polyline points="7 23 3 19 7 15"></polyline>
  <path d="M21 13v2a4 4 0 0 1-4 4H3"></path>
</svg>"""

SVG_REPEAT_ONE = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <polyline points="17 1 21 5 17 9"></polyline>
    <path d="M3 11V9a4 4 0 0 1 4-4h14"></path>
    <polyline points="7 23 3 19 7 15"></polyline>
    <path d="M21 13v2a4 4 0 0 1-4 4H3"></path>
  </g>
  <text x="12" y="15" fill="#ffffff" font-family="sans-serif" font-weight="bold" font-size="9" text-anchor="middle">1</text>
</svg>"""

SVG_SHUFFLE_OFF = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#555555" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg">
  <polyline points="16 3 21 3 21 8"></polyline>
  <line x1="4" y1="20" x2="21" y2="3"></line>
  <polyline points="21 16 21 21 16 21"></polyline>
  <line x1="15" y1="15" x2="21" y2="21"></line>
  <line x1="4" y1="4" x2="9" y2="9"></line>
</svg>"""

SVG_SHUFFLE_ON = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg">
  <polyline points="16 3 21 3 21 8"></polyline>
  <line x1="4" y1="20" x2="21" y2="3"></line>
  <polyline points="21 16 21 21 16 21"></polyline>
  <line x1="15" y1="15" x2="21" y2="21"></line>
  <line x1="4" y1="4" x2="9" y2="9"></line>
</svg>"""

_CACHE = {}

def get_icon_pixbuf(name: str, size: int = 18) -> GdkPixbuf.Pixbuf:
    key = (name, size)
    if key in _CACHE:
        return _CACHE[key]

    svg_map = {
        "repeat_off": SVG_REPEAT_OFF,
        "repeat_all": SVG_REPEAT_ALL,
        "repeat_one": SVG_REPEAT_ONE,
        "shuffle_off": SVG_SHUFFLE_OFF,
        "shuffle_on": SVG_SHUFFLE_ON,
    }

    svg_text = svg_map.get(name, SVG_REPEAT_OFF)
    stream = Gio.MemoryInputStream.new_from_data(svg_text.encode("utf-8"), None)
    pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(stream, size, size, True, None)
    _CACHE[key] = pixbuf
    return pixbuf
