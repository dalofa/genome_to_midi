"""Render MIDI note events as a time-by-pitch image."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import random
import re
import xml.etree.ElementTree as ElementTree

from mido import MidiFile
from PIL import Image, ImageDraw


RGBColor = tuple[int, int, int]
_HEX_COLOR = re.compile(r"#?([0-9a-fA-F]{6})$")


@dataclass(frozen=True)
class MidiNote:
    """A note span in absolute MIDI ticks."""

    pitch: int
    start: int
    end: int
    track: int
    channel: int
    velocity: int


def parse_palette(path: Path) -> tuple[RGBColor, ...]:
    """Read one six-digit hex color per line from a palette file."""
    colors: list[RGBColor] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError(f"Could not read palette file {path}: {error}") from error

    for line_number, line in enumerate(lines, start=1):
        value = line.strip()
        if not value or value.startswith(";") or value.startswith("//"):
            continue
        match = _HEX_COLOR.fullmatch(value)
        if match is None:
            raise ValueError(f"Invalid palette color on line {line_number}: {value!r}")
        hex_value = match.group(1)
        red = int(hex_value[0:2], 16)
        green = int(hex_value[2:4], 16)
        blue = int(hex_value[4:6], 16)
        colors.append((red, green, blue))

    if not colors:
        raise ValueError("Palette file must contain at least one hex color")
    return tuple(colors)


def read_midi_notes(path: Path) -> tuple[list[MidiNote], int]:
    """Read note spans and total duration from a MIDI file."""
    try:
        midi = MidiFile(path)
    except (OSError, ValueError) as error:
        raise ValueError(f"Could not read MIDI file {path}: {error}") from error

    notes: list[MidiNote] = []
    total_ticks = 0
    for track_index, track in enumerate(midi.tracks):
        absolute_time = 0
        active: dict[tuple[int, int], list[tuple[int, int]]] = {}
        for message in track:
            absolute_time += message.time
            total_ticks = max(total_ticks, absolute_time)
            if message.type not in {"note_on", "note_off"}:
                continue
            channel = message.channel
            key = (channel, message.note)
            if message.type == "note_on" and message.velocity > 0:
                active.setdefault(key, []).append((absolute_time, message.velocity))
                continue
            pending = active.get(key)
            if not pending:
                continue
            start_time, velocity = pending.pop()
            notes.append(
                MidiNote(
                    pitch=message.note,
                    start=start_time,
                    end=max(start_time + 1, absolute_time),
                    track=track_index,
                    channel=channel,
                    velocity=velocity,
                )
            )
            if not pending:
                del active[key]

        for (channel, pitch), pending in active.items():
            for start_time, velocity in pending:
                notes.append(
                    MidiNote(
                        pitch=pitch,
                        start=start_time,
                        end=max(start_time + 1, absolute_time),
                        track=track_index,
                        channel=channel,
                        velocity=velocity,
                    )
                )

    return notes, total_ticks


def _pitch_bounds(pitch: int, height: int) -> tuple[int, int]:
    top = height - math.ceil((pitch + 1) * height / 128)
    bottom = height - math.ceil(pitch * height / 128) - 1
    return max(0, top), min(height - 1, max(top, bottom))


def _note_rectangles(
    notes: list[MidiNote],
    total_ticks: int,
    palette: tuple[RGBColor, ...],
    *,
    width: int,
    height: int,
    randomness: float,
    seed: int | None,
) -> list[tuple[int, int, int, int, RGBColor]]:
    duration = max(1, total_ticks)
    generator = random.Random(seed)
    position_jitter = round(randomness * min(12, max(width, height) * 0.01))
    color_jitter = round(randomness * max(1, len(palette) * 0.25))
    rectangles = []
    for note in notes:
        start_x = min(width - 1, note.start * width // duration)
        end_x = min(width - 1, max(start_x, (note.end * width - 1) // duration))
        top_y, bottom_y = _pitch_bounds(note.pitch, height)
        if position_jitter:
            start_x += generator.randint(-position_jitter, position_jitter)
            end_x += generator.randint(-position_jitter, position_jitter)
            start_x = max(0, min(width - 1, start_x))
            end_x = max(start_x, min(width - 1, end_x))
        pitch_index = note.pitch * len(palette) // 128
        channel_offset = (note.track * 16 + note.channel) % len(palette)
        palette_index = (pitch_index + channel_offset) % len(palette)
        if color_jitter:
            palette_index = (palette_index + generator.randint(-color_jitter, color_jitter)) % len(palette)
        rectangles.append((start_x, top_y, end_x, bottom_y, palette[palette_index]))
    return rectangles


def _output_format(output_path: Path, requested: str | None) -> str:
    selected = requested or output_path.suffix.lower().lstrip(".") or "png"
    if selected not in {"png", "svg"}:
        raise ValueError("Output format must be png or svg")
    return selected


def render_visualization(
    notes: list[MidiNote],
    total_ticks: int,
    palette: tuple[RGBColor, ...],
    output_path: Path,
    *,
    width: int = 1024,
    height: int = 1024,
    randomness: float = 0.0,
    seed: int | None = None,
    output_format: str | None = None,
) -> None:
    """Render MIDI notes into a PNG or SVG with time on x and pitch on y."""
    if width <= 0 or height <= 0:
        raise ValueError("Image width and height must be positive")
    if not palette:
        raise ValueError("Palette must contain at least one color")
    if not 0 <= randomness <= 1:
        raise ValueError("Randomness must be between 0 and 1")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rectangles = _note_rectangles(
        notes,
        total_ticks,
        palette,
        width=width,
        height=height,
        randomness=randomness,
        seed=seed,
    )
    if _output_format(output_path, output_format) == "svg":
        root = ElementTree.Element(
            "svg",
            {
                "xmlns": "http://www.w3.org/2000/svg",
                "width": str(width),
                "height": str(height),
                "viewBox": f"0 0 {width} {height}",
            },
        )
        ElementTree.SubElement(root, "rect", {"width": str(width), "height": str(height), "fill": "#000000"})
        for start_x, top_y, end_x, bottom_y, color in rectangles:
            ElementTree.SubElement(
                root,
                "rect",
                {
                    "x": str(start_x),
                    "y": str(top_y),
                    "width": str(end_x - start_x + 1),
                    "height": str(bottom_y - top_y + 1),
                    "fill": "#%02X%02X%02X" % color,
                },
            )
        ElementTree.ElementTree(root).write(output_path, encoding="utf-8", xml_declaration=True)
        return

    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    for start_x, top_y, end_x, bottom_y, color in rectangles:
        draw.rectangle((start_x, top_y, end_x, bottom_y), fill=color)
    image.save(output_path, format="PNG")


def render_midi_visualization(
    midi_path: Path,
    palette_path: Path,
    output_path: Path,
    *,
    width: int = 1024,
    height: int = 1024,
    randomness: float = 0.0,
    seed: int | None = None,
    output_format: str | None = None,
) -> None:
    """Load a MIDI and palette file and write a PNG or SVG visualization."""
    notes, total_ticks = read_midi_notes(midi_path)
    palette = parse_palette(palette_path)
    render_visualization(
        notes,
        total_ticks,
        palette,
        output_path,
        width=width,
        height=height,
        randomness=randomness,
        seed=seed,
        output_format=output_format,
    )