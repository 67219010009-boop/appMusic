import os
import re
from typing import Optional, Callable, Dict, Any, List
import gi

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Initialize GStreamer once
if not Gst.is_initialized():
    Gst.init(None)

def get_available_audio_devices() -> List[Dict[str, Any]]:
    """
    Discovers available playback audio hardware cards, USB DACs, and system outputs.
    Scans /proc/asound/cards and /proc/asound/pcm directly.
    """
    devices: List[Dict[str, Any]] = [
        {
            "device": "default",
            "name": "System Default (Auto / PipeWire / Pulse)",
            "is_dac": False,
            "type": "default"
        }
    ]

    card_names: Dict[int, str] = {}
    if os.path.exists("/proc/asound/cards"):
        try:
            with open("/proc/asound/cards", "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = re.match(r'\s*(\d+)\s+\[([^\]]+)\]:\s+(.*)', line)
                    if m:
                        card_num = int(m.group(1))
                        desc = m.group(3).strip()
                        card_names[card_num] = desc
        except Exception:
            pass

    hardware_found = False
    dac_found = False
    if os.path.exists("/proc/asound/pcm"):
        try:
            with open("/proc/asound/pcm", "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if "playback" in line:
                        parts = line.split(":")
                        if len(parts) >= 2:
                            card_dev = parts[0].strip()
                            dev_name = parts[1].strip()
                            cd = card_dev.split("-")
                            if len(cd) == 2:
                                try:
                                    c_num = int(cd[0])
                                    d_num = int(cd[1])
                                    card_desc = card_names.get(c_num, f"Card {c_num}")
                                    is_dac = any(k in card_desc.lower() or k in dev_name.lower() for k in [
                                        "dac", "usb-audio", "usb audio", "hifi", "dragonfly", "topping", "fiio", "schiit", "ifi", "chord"
                                    ])
                                    if is_dac:
                                        dac_found = True
                                        prefix = "[DAC]"
                                    else:
                                        prefix = "[ALSA]"
                                    devices.append({
                                        "device": f"hw:{c_num},{d_num}",
                                        "name": f"{prefix} {dev_name} ({card_desc})",
                                        "is_dac": is_dac,
                                        "type": "alsa"
                                    })
                                    hardware_found = True
                                except ValueError:
                                    pass
        except Exception:
            pass

    if not dac_found:
        devices.append({
            "device": "none",
            "name": "DAC: ไม่มี (ไม่พบ DAC ภายนอก)",
            "is_dac": False,
            "type": "none"
        })

    return devices

class AudioEngine:
    """
    High-Resolution Lossless Audio Engine built on GStreamer.
    Includes an explicit software volume attenuation element to guarantee volume scaling
    across all ALSA hardware DACs without relying on hardware mixer support.
    """

    def __init__(self, output_mode: str = "auto", alsa_device: str = "default"):
        self.output_mode = output_mode
        self.alsa_device = alsa_device
        self._current_file: Optional[str] = None
        self._on_eos_callback: Optional[Callable[[], None]] = None
        self._on_state_change_callback: Optional[Callable[[str], None]] = None
        self._is_playing: bool = False
        self._is_paused: bool = False
        self._volume: float = 1.0

        self._volume_element: Optional[Gst.Element] = None
        self._pipeline: Optional[Gst.Element] = None
        self._create_pipeline()

    def _create_sink_bin(self) -> Gst.Element:
        """
        Creates an audio sink bin containing:
        audioconvert ! volume name=audio_volume ! raw_sink
        This guarantees volume control works even with direct ALSA DAC hardware.
        """
        bin_elem = Gst.Bin.new("audio_sink_bin")

        conv = Gst.ElementFactory.make("audioconvert", "sink_conv")
        vol = Gst.ElementFactory.make("volume", "audio_volume")
        self._volume_element = vol
        if vol:
            vol.set_property("volume", self._volume)

        # Create the hardware or system sink
        if self.output_mode == "alsa":
            raw_sink = Gst.ElementFactory.make("alsasink", "raw_audio_sink")
            if raw_sink is not None:
                if self.alsa_device:
                    raw_sink.set_property("device", self.alsa_device)
                if hasattr(raw_sink.props, "slave_method"):
                    raw_sink.set_property("slave-method", 2)  # GST_AUDIO_BASE_SINK_SLAVE_NONE
        else:
            raw_sink = Gst.ElementFactory.make("autoaudiosink", "raw_audio_sink")

        if raw_sink is None:
            raw_sink = Gst.ElementFactory.make("fakesink", "raw_audio_sink")

        bin_elem.add(conv)
        bin_elem.add(vol)
        bin_elem.add(raw_sink)

        conv.link(vol)
        vol.link(raw_sink)

        # Expose ghost sink pad
        pad = conv.get_static_pad("sink")
        ghost_pad = Gst.GhostPad.new("sink", pad)
        bin_elem.add_pad(ghost_pad)

        return bin_elem

    def _create_pipeline(self) -> None:
        if self._pipeline is not None:
            self._pipeline.set_state(Gst.State.NULL)
            self._pipeline = None

        self._pipeline = Gst.ElementFactory.make("playbin", "monoflac_playbin")
        if self._pipeline is None:
            raise RuntimeError("Failed to create GStreamer playbin element")

        GST_PLAY_FLAG_AUDIO = 0x02
        self._pipeline.set_property("flags", GST_PLAY_FLAG_AUDIO)

        audio_sink_bin = self._create_sink_bin()
        self._pipeline.set_property("audio-sink", audio_sink_bin)
        self._pipeline.set_property("volume", self._volume)

        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", self._on_bus_eos)
        bus.connect("message::error", self._on_bus_error)
        bus.connect("message::state-changed", self._on_bus_state_changed)

    def _on_bus_eos(self, bus, msg) -> None:
        self._is_playing = False
        self._is_paused = False
        if self._on_eos_callback:
            self._on_eos_callback()

    def _on_bus_error(self, bus, msg) -> None:
        err, debug = msg.parse_error()
        self.stop()
        if self.output_mode == "alsa":
            self.set_output_mode("auto")

    def _on_bus_state_changed(self, bus, msg) -> None:
        if msg.src == self._pipeline:
            old_state, new_state, pending = msg.parse_state_changed()
            state_str = new_state.value_nick
            if new_state == Gst.State.PLAYING:
                self._is_playing = True
                self._is_paused = False
            elif new_state == Gst.State.PAUSED:
                self._is_playing = False
                self._is_paused = True
            elif new_state == Gst.State.NULL or new_state == Gst.State.READY:
                self._is_playing = False
                self._is_paused = False

            if self._on_state_change_callback:
                self._on_state_change_callback(state_str)

    def set_output_mode(self, mode: str, device: str = "default") -> None:
        current_pos = self.get_position()
        was_playing = self.is_playing
        self.output_mode = mode
        self.alsa_device = device

        if self._pipeline:
            self._create_pipeline()
            if self._current_file:
                self.load(self._current_file)
                if current_pos > 0:
                    self.seek(current_pos)
                if was_playing:
                    self.play()

    def load(self, file_path: str) -> bool:
        if not os.path.isfile(file_path):
            return False

        self.stop()
        self._current_file = file_path
        abs_path = os.path.abspath(file_path)
        uri = Gst.filename_to_uri(abs_path)
        self._pipeline.set_property("uri", uri)
        self._pipeline.set_state(Gst.State.PAUSED)
        return True

    def play(self) -> None:
        if self._pipeline:
            self._pipeline.set_state(Gst.State.PLAYING)
            self._is_playing = True
            self._is_paused = False

    def pause(self) -> None:
        if self._pipeline:
            self._pipeline.set_state(Gst.State.PAUSED)
            self._is_playing = False
            self._is_paused = True

    def stop(self) -> None:
        if self._pipeline:
            self._pipeline.set_state(Gst.State.READY)
            self._is_playing = False
            self._is_paused = False

    def release_device(self) -> None:
        if self._pipeline:
            self._pipeline.set_state(Gst.State.NULL)
            self._is_playing = False
            self._is_paused = False

    def seek(self, position_sec: float) -> bool:
        if not self._pipeline:
            return False
        pos_ns = int(max(0.0, position_sec) * Gst.SECOND)
        return self._pipeline.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            pos_ns
        )

    def get_position(self) -> float:
        if not self._pipeline:
            return 0.0
        success, pos_ns = self._pipeline.query_position(Gst.Format.TIME)
        if success and pos_ns >= 0:
            return pos_ns / Gst.SECOND
        return 0.0

    def get_duration(self) -> float:
        if not self._pipeline:
            return 0.0
        success, dur_ns = self._pipeline.query_duration(Gst.Format.TIME)
        if success and dur_ns >= 0:
            return dur_ns / Gst.SECOND
        return 0.0

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, float(volume)))
        if self._volume_element:
            self._volume_element.set_property("volume", self._volume)
        if self._pipeline:
            self._pipeline.set_property("volume", self._volume)

    def get_volume(self) -> float:
        return self._volume

    def get_audio_format(self) -> Dict[str, Any]:
        result = {"sample_rate": 0, "channels": 2, "bit_depth": 16}
        if not self._current_file:
            return result

        try:
            from mutagen.flac import FLAC
            audio = FLAC(self._current_file)
            if audio.info:
                result["sample_rate"] = int(audio.info.sample_rate)
                result["channels"] = int(audio.info.channels)
                result["bit_depth"] = int(audio.info.bits_per_sample)
        except Exception:
            pass
        return result

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def set_on_eos(self, callback: Callable[[], None]) -> None:
        self._on_eos_callback = callback

    def set_on_state_change(self, callback: Callable[[str], None]) -> None:
        self._on_state_change_callback = callback
