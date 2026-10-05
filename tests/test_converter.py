from pathlib import Path

from mido import MidiFile
import pytest

from genbank_to_midi.cli import main
from genbank_to_midi.mapping import (
    codon_notes,
    codons,
    codon_index,
    codon_pitch,
    nucleotide_pitch,
    parse_midi_pitch,
    parse_nucleotide_notes,
    scale_pitch_classes,
)
from genbank_to_midi.midi import render_midi
from genbank_to_midi.parser import SelectedFeature, parse_genbank

GENBANK = """LOCUS       TEST                     18 bp    DNA     linear   01-JAN-2000
DEFINITION  Test record.
ACCESSION   TEST0001
VERSION     TEST0001.1
KEYWORDS    .
SOURCE      synthetic construct
  ORGANISM  synthetic construct
            other;
FEATURES             Location/Qualifiers
     CDS             1..9
                     /locus_tag="cds1"
     gene            1..9
                     /gene="overlap_gene"
     gene            complement(10..18)
                     /gene="reverse_gene"
ORIGIN
        1 atgcgttacatgcaatgg
//
"""


def write_genbank(path: Path) -> None:
    path.write_text(GENBANK, encoding="utf-8")


def test_parser_prefers_cds_and_extracts_reverse_gene(tmp_path: Path) -> None:
    source = tmp_path / "test.gb"
    write_genbank(source)

    records, features = parse_genbank([source])

    assert len(records) == 1
    assert [(feature.kind, feature.feature_id) for feature in features] == [
        ("CDS", "cds1"),
        ("gene", "reverse_gene"),
    ]
    assert features[0].sequence == "ATGCGTTAC"
    assert features[1].strand == -1
    assert features[1].sequence == "CCATTGCAT"


def test_mappings_are_deterministic_and_bounded() -> None:
    assert nucleotide_pitch("a") == 36
    assert nucleotide_pitch("N") == 41
    assert codon_index("AAA") == 0
    assert codons("ATGCGTA") == ["ATG", "CGT"]
    assert codon_notes("ATG", mode="notes") == codon_notes("ATG", mode="notes")
    assert len(codon_notes("ATG", mode="chords")) == 3
    assert all(0 <= note <= 127 for note in codon_notes("TTT", root=72, mode="chords"))


def test_custom_nucleotide_notes_use_absolute_midi_pitches() -> None:
    notes = parse_nucleotide_notes("A=10,C=20,G=30,T=40")

    assert [nucleotide_pitch(base, note_mapping=notes) for base in "ACGT"] == [10, 20, 30, 40]


def test_midi_pitch_parser_supports_note_names_and_integers() -> None:
    assert parse_midi_pitch("A2") == 45
    assert parse_midi_pitch("C3") == 48
    assert parse_midi_pitch("F#4") == 66
    assert parse_midi_pitch("Bb2") == 46
    assert parse_midi_pitch("60") == 60
    assert parse_midi_pitch("C-1") == 0
    assert parse_midi_pitch("G9") == 127


def test_custom_nucleotide_notes_support_note_names() -> None:
    notes = parse_nucleotide_notes("A=A2,C=C3,G=G3,T=F#3")

    assert notes == {"A": 45, "C": 48, "G": 55, "T": 54}


def test_custom_nucleotide_notes_require_all_bases_and_valid_pitches() -> None:
    with pytest.raises(ValueError, match="must specify A, C, G, and T"):
        parse_nucleotide_notes("A=10,C=20,G=30")
    with pytest.raises(ValueError, match="between 0 and 127"):
        parse_nucleotide_notes("A=10,C=20,G=30,T=128")
    with pytest.raises(ValueError, match="Invalid MIDI note"):
        parse_nucleotide_notes("A=H2,C=C3,G=G3,T=T3")


def test_amino_acid_mapping_groups_synonymous_codons_and_skips_stops() -> None:
    assert codon_notes("GAA", amino_acid_mapping=True) == codon_notes("GAG", amino_acid_mapping=True)
    assert codon_notes("GAA", amino_acid_mapping=True) != codon_notes("GAT", amino_acid_mapping=True)
    assert codon_notes("TAA", amino_acid_mapping=True) == ()


def test_amino_acid_mapping_groups_chord_tones() -> None:
    assert codon_notes("GAA", mode="chords", amino_acid_mapping=True) == codon_notes(
        "GAG", mode="chords", amino_acid_mapping=True
    )


def test_melody_octaves_wrap_codon_mapping_within_requested_span() -> None:
    one_octave_notes = [
        codon_pitch(codon, melody_octaves=1)
        for codon in ("AAA", "AAC", "AAG", "AAT", "ACT")
    ]

    assert one_octave_notes == [60, 62, 64, 65, 60]
    assert all(60 <= note < 72 for note in one_octave_notes)


def test_melody_octaves_apply_to_amino_acid_mapping() -> None:
    note = codon_pitch("GAA", amino_acid_mapping=True, melody_octaves=2)

    assert 60 <= note < 84
    assert codon_pitch("GAA", amino_acid_mapping=True, melody_octaves=1) == 65


def test_render_midi_uses_amino_acid_mapping_and_skips_stops(tmp_path: Path) -> None:
    output = tmp_path / "amino-acids.mid"
    records = [type("Record", (), {"id": "record", "seq": "AAAAAAAAA"})()]
    features = [SelectedFeature("record", "cds", "CDS", 0, 9, 1, "GAAGAGTAA")]

    _, melody_count = render_midi(records, features, output, amino_acid_mapping=True)

    melody_notes = [
        message.note
        for message in MidiFile(output).tracks[1]
        if message.type == "note_on" and message.velocity > 0
    ]
    assert melody_count == 2
    assert melody_notes[0] == melody_notes[1]


def test_scale_pitch_classes_supports_named_major_and_minor_scales() -> None:
    assert scale_pitch_classes("A-minor") == frozenset({0, 2, 4, 5, 7, 9, 11})
    assert scale_pitch_classes("c major") == frozenset({0, 2, 4, 5, 7, 9, 11})


def test_scale_pitch_classes_rejects_unknown_scales() -> None:
    try:
        scale_pitch_classes("H-minor")
    except ValueError as error:
        assert "Unknown scale" in str(error)
    else:
        raise AssertionError("Unknown scales should be rejected")


def test_render_midi_moves_notes_into_scale(tmp_path: Path) -> None:
    output = tmp_path / "scaled.mid"
    features = [SelectedFeature("test", "feature", "CDS", 0, 6, 1, "AAAACG")]

    bass_count, melody_count = render_midi([], features, output, scale="D-minor")

    melody_notes = [
        message.note
        for message in MidiFile(output).tracks[1]
        if message.type == "note_on" and message.velocity > 0
    ]
    assert (bass_count, melody_count) == (0, 2)
    assert melody_notes == [60, 70]


def test_render_midi_moves_bass_notes_into_scale(tmp_path: Path) -> None:
    output = tmp_path / "scaled-bass.mid"
    records = [type("Record", (), {"seq": "ACGT"})()]

    bass_count, melody_count = render_midi(records, [], output, scale="C-major")

    bass_notes = [
        message.note
        for message in MidiFile(output).tracks[0]
        if message.type == "note_on" and message.velocity > 0
    ]
    assert (bass_count, melody_count) == (4, 0)
    assert bass_notes == [36, 38, 43, 45]


def test_render_midi_uses_custom_nucleotide_notes(tmp_path: Path) -> None:
    output = tmp_path / "custom-bass.mid"
    records = [type("Record", (), {"seq": "ACGT"})()]

    render_midi(records, [], output, nucleotide_notes={"A": 10, "C": 20, "G": 30, "T": 40})

    bass_notes = [
        message.note
        for message in MidiFile(output).tracks[0]
        if message.type == "note_on" and message.velocity > 0
    ]
    assert bass_notes == [10, 20, 30, 40]


def test_render_midi_arpeggiates_chords_within_codon_duration(tmp_path: Path) -> None:
    output = tmp_path / "arpeggio.mid"
    records = [type("Record", (), {"id": "record", "seq": "AAA"})()]
    features = [SelectedFeature("record", "cds", "CDS", 0, 3, 1, "ACA")]

    render_midi(records, features, output, melody_mode="chords", arpeggiate=True, codon_duration=10)

    elapsed = 0
    note_on_times = []
    note_off_times = []
    for message in MidiFile(output).tracks[1]:
        elapsed += message.time
        if message.type == "note_on" and message.velocity > 0:
            note_on_times.append(elapsed)
        elif message.type == "note_off":
            note_off_times.append(elapsed)
    assert note_on_times == [0, 3, 6]
    assert note_off_times == [3, 6, 10]


def test_render_midi_starts_codon_at_first_base_and_spans_three_bases(tmp_path: Path) -> None:
    output = tmp_path / "aligned.mid"
    records = [type("Record", (), {"id": "record", "seq": "AAAAAA"})()]
    features = [SelectedFeature("record", "cds", "CDS", 0, 3, 1, "AGT")]

    render_midi(records, features, output, bass_duration=120, codon_duration=240)

    elapsed = 0
    note_on_times = []
    note_off_times = []
    for message in MidiFile(output).tracks[1]:
        elapsed += message.time
        if message.type == "note_on" and message.velocity > 0:
            note_on_times.append(elapsed)
        elif message.type == "note_off":
            note_off_times.append(elapsed)
    assert note_on_times == [0]
    assert note_off_times == [360]


def test_render_midi_stacks_overlapping_feature_notes(tmp_path: Path) -> None:
    output = tmp_path / "overlapping.mid"
    records = [type("Record", (), {"id": "record", "seq": "AAA"})()]
    features = [
        SelectedFeature("record", "cds1", "CDS", 0, 3, 1, "AGT"),
        SelectedFeature("record", "cds2", "CDS", 0, 3, 1, "CCA"),
    ]

    render_midi(records, features, output, bass_duration=120)

    elapsed = 0
    note_on_times = []
    for message in MidiFile(output).tracks[1]:
        elapsed += message.time
        if message.type == "note_on" and message.velocity > 0:
            note_on_times.append(elapsed)
    assert note_on_times == [0, 0]


def test_render_midi_reverses_codon_timing_for_reverse_features(tmp_path: Path) -> None:
    output = tmp_path / "reverse-aligned.mid"
    records = [type("Record", (), {"id": "record", "seq": "AAAAAA"})()]
    features = [SelectedFeature("record", "reverse", "CDS", 0, 6, -1, "AGTCCC")]

    render_midi(records, features, output, bass_duration=120)

    elapsed = 0
    note_on_times = []
    for message in MidiFile(output).tracks[1]:
        elapsed += message.time
        if message.type == "note_on" and message.velocity > 0:
            note_on_times.append(elapsed)
    assert note_on_times == [0, 360]


def test_render_midi_moves_chord_tones_into_scale(tmp_path: Path) -> None:
    output = tmp_path / "scaled-chord.mid"
    features = [SelectedFeature("test", "feature", "CDS", 0, 3, 1, "ACA")]

    _, melody_count = render_midi([], features, output, melody_mode="chords", scale="D-minor")

    melody_notes = [
        message.note
        for message in MidiFile(output).tracks[1]
        if message.type == "note_on" and message.velocity > 0
    ]
    assert melody_count == 3
    assert melody_notes == [67, 70, 74]


def test_render_midi_has_two_tracks_and_distinct_channels(tmp_path: Path) -> None:
    source = tmp_path / "test.gb"
    output = tmp_path / "test.mid"
    write_genbank(source)
    records, features = parse_genbank([source])

    bass_count, melody_count = render_midi(records, features, output)
    midi = MidiFile(output)

    assert (bass_count, melody_count) == (18, 6)
    assert [track.name for track in midi.tracks] == [
        "Bass - nucleotide sequence",
        "Genes - codon melody",
    ]
    channels = {
        message.channel
        for track in midi.tracks
        for message in track
        if hasattr(message, "channel")
    }
    assert channels == {0, 1}
    programs = [
        message.program
        for track in midi.tracks
        for message in track
        if message.type == "program_change"
    ]
    assert programs == [38, 80]


def test_cli_creates_midi_and_reports_summary(tmp_path: Path, capsys) -> None:
    source = tmp_path / "test.gb"
    output = tmp_path / "cli.mid"
    write_genbank(source)

    assert main(
        [str(source), "--output", str(output), "--melody-mode", "chords", "--amino-acid-mapping"]
    ) == 0
    assert output.exists()
    output_text = capsys.readouterr().out
    assert "18 bass notes" in output_text
    assert "18 melody notes" in output_text


def test_cli_rejects_unknown_scale(tmp_path: Path, capsys) -> None:
    source = tmp_path / "test.gb"
    output = tmp_path / "invalid-scale.mid"
    write_genbank(source)

    with pytest.raises(SystemExit):
        main([str(source), "--output", str(output), "--scale", "H-minor"])

    assert "Unknown scale" in capsys.readouterr().err
    assert not output.exists()


def test_cli_rejects_nonpositive_melody_octaves(tmp_path: Path, capsys) -> None:
    source = tmp_path / "test.gb"
    output = tmp_path / "invalid-octaves.mid"
    write_genbank(source)

    with pytest.raises(SystemExit):
        main([str(source), "--output", str(output), "--melody-octaves", "0"])

    assert "melody-octaves must be positive" in capsys.readouterr().err
    assert not output.exists()


def test_chord_mode_starts_triad_together(tmp_path: Path) -> None:
    source = tmp_path / "test.gb"
    output = tmp_path / "chords.mid"
    write_genbank(source)
    records, features = parse_genbank([source])

    render_midi(records, features, output, melody_mode="chords")
    melody_notes = [
        message
        for message in MidiFile(output).tracks[1]
        if message.type == "note_on" and message.velocity > 0
    ]

    assert [message.time for message in melody_notes[:3]] == [0, 0, 0]
