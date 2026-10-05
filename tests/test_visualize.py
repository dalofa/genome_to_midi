from pathlib import Path
import xml.etree.ElementTree as ElementTree

from mido import Message, MidiFile, MidiTrack
from PIL import Image
import pytest

from genbank_to_midi.visualize import MidiNote, parse_palette, read_midi_notes, render_visualization
from genbank_to_midi.visualize_cli import main


def write_midi(path: Path) -> None:
    midi = MidiFile(ticks_per_beat=480)
    first = MidiTrack()
    first.append(Message("note_on", note=60, velocity=90, channel=0, time=120))
    first.append(Message("note_off", note=60, velocity=0, channel=0, time=240))
    second = MidiTrack()
    second.append(Message("note_on", note=64, velocity=100, channel=1, time=0))
    second.append(Message("note_off", note=64, velocity=0, channel=1, time=480))
    midi.tracks.extend((first, second))
    midi.save(path)


def test_parse_palette_accepts_hex_colors_and_comments(tmp_path: Path) -> None:
    palette_file = tmp_path / "palette.txt"
    palette_file.write_text("#000000\n; comment\nFF0040\n// comment\n", encoding="utf-8")

    assert parse_palette(palette_file) == ((0, 0, 0), (255, 0, 64))


def test_parse_palette_rejects_invalid_colors(tmp_path: Path) -> None:
    palette_file = tmp_path / "palette.txt"
    palette_file.write_text("#12GG00\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        parse_palette(palette_file)


def test_read_midi_notes_uses_absolute_track_time(tmp_path: Path) -> None:
    midi_file = tmp_path / "input.mid"
    write_midi(midi_file)

    notes, total_ticks = read_midi_notes(midi_file)

    assert notes == [
        MidiNote(pitch=60, start=120, end=360, track=0, channel=0, velocity=90),
        MidiNote(pitch=64, start=0, end=480, track=1, channel=1, velocity=100),
    ]
    assert total_ticks == 480


def test_read_midi_notes_closes_notes_at_track_end(tmp_path: Path) -> None:
    midi_file = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    track.append(Message("note_on", note=60, velocity=90, time=0))
    track.append(Message("control_change", control=1, value=10, time=240))
    midi_file.tracks.append(track)
    path = tmp_path / "open-note.mid"
    midi_file.save(path)

    notes, total_ticks = read_midi_notes(path)

    assert notes[0].start == 0
    assert notes[0].end == 240
    assert total_ticks == 240


def test_render_visualization_maps_duration_pitch_and_channel(tmp_path: Path) -> None:
    output = tmp_path / "art" / "output.png"
    notes = [
        MidiNote(pitch=0, start=0, end=240, track=0, channel=0, velocity=80),
        MidiNote(pitch=127, start=240, end=480, track=0, channel=0, velocity=80),
    ]
    render_visualization(
        notes,
        480,
        ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)),
        output,
        width=100,
        height=128,
    )

    image = Image.open(output)
    assert image.size == (100, 128)
    assert image.getpixel((0, 127)) == (255, 0, 0)
    assert image.getpixel((49, 127)) == (255, 0, 0)
    assert image.getpixel((50, 0)) == (255, 255, 255)
    assert image.getpixel((99, 0)) == (255, 255, 255)


def test_render_visualization_randomness_is_repeatable_with_seed(tmp_path: Path) -> None:
    notes = [MidiNote(pitch=60, start=0, end=240, track=0, channel=0, velocity=80)]
    palette = ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255))
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    different = tmp_path / "different.png"

    render_visualization(notes, 240, palette, first, width=100, height=100, randomness=1, seed=7)
    render_visualization(notes, 240, palette, second, width=100, height=100, randomness=1, seed=7)
    render_visualization(notes, 240, palette, different, width=100, height=100, randomness=1, seed=8)

    assert Image.open(first).tobytes() == Image.open(second).tobytes()
    assert Image.open(first).tobytes() != Image.open(different).tobytes()


def test_render_visualization_writes_svg_with_note_rectangles(tmp_path: Path) -> None:
    output = tmp_path / "output.svg"
    notes = [MidiNote(pitch=60, start=0, end=240, track=0, channel=0, velocity=80)]

    render_visualization(notes, 240, ((255, 0, 64),), output, width=100, height=80)

    root = ElementTree.parse(output).getroot()
    rectangles = root.findall("{http://www.w3.org/2000/svg}rect")
    assert root.attrib["width"] == "100"
    assert root.attrib["height"] == "80"
    assert len(rectangles) == 2
    assert rectangles[1].attrib["fill"] == "#FF0040"


def test_visualization_cli_creates_png(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    midi_file = tmp_path / "input.mid"
    palette_file = tmp_path / "palette.txt"
    output = tmp_path / "output.png"
    write_midi(midi_file)
    palette_file.write_text("#000000\n#FF0040\n", encoding="utf-8")

    assert main(
        [str(midi_file), "--palette", str(palette_file), "--output", str(output), "--width", "80", "--height", "60"]
    ) == 0

    assert Image.open(output).size == (80, 60)
    assert "Wrote" in capsys.readouterr().out


def test_visualization_cli_creates_svg(tmp_path: Path) -> None:
    midi_file = tmp_path / "input.mid"
    palette_file = tmp_path / "palette.txt"
    output = tmp_path / "output.svg"
    write_midi(midi_file)
    palette_file.write_text("#000000\n#FF0040\n", encoding="utf-8")

    assert main(
        [
            str(midi_file),
            "--palette",
            str(palette_file),
            "--output",
            str(output),
            "--format",
            "svg",
            "--width",
            "80",
            "--height",
            "60",
        ]
    ) == 0

    assert ElementTree.parse(output).getroot().tag == "{http://www.w3.org/2000/svg}svg"


def test_visualization_cli_rejects_nonpositive_dimensions(tmp_path: Path) -> None:
    midi_file = tmp_path / "input.mid"
    palette_file = tmp_path / "palette.txt"
    write_midi(midi_file)
    palette_file.write_text("#000000\n", encoding="utf-8")

    with pytest.raises(SystemExit):
        main([str(midi_file), "--palette", str(palette_file), "--output", str(tmp_path / "out.png"), "--width", "0"])


def test_visualization_cli_rejects_invalid_randomness(tmp_path: Path) -> None:
    midi_file = tmp_path / "input.mid"
    palette_file = tmp_path / "palette.txt"
    write_midi(midi_file)
    palette_file.write_text("#000000\n", encoding="utf-8")

    with pytest.raises(SystemExit):
        main(
            [
                str(midi_file),
                "--palette",
                str(palette_file),
                "--output",
                str(tmp_path / "out.png"),
                "--randomness",
                "1.1",
            ]
        )