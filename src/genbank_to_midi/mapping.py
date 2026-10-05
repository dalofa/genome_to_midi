"""Deterministic nucleotide and codon-to-pitch mappings."""

from __future__ import annotations

from itertools import product
import re
from typing import Mapping

from Bio.Data.CodonTable import unambiguous_dna_by_name

BASE_OFFSETS = {"A": 0, "C": 3, "G": 7, "T": 10}
SCALE_INTERVALS = (0, 2, 4, 5, 7, 9, 11, 12)
SCALE_PATTERNS = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
}
NOTE_PITCH_CLASSES = {
    "C": 0,
    "C#": 1,
    "DB": 1,
    "D": 2,
    "D#": 3,
    "EB": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "GB": 6,
    "G": 7,
    "G#": 8,
    "AB": 8,
    "A": 9,
    "A#": 10,
    "BB": 10,
    "B": 11,
}
BASES = "ACGT"
AMINO_ACIDS = tuple("ACDEFGHIKLMNPQRSTVWY")
AMINO_ACID_INDEX = {amino_acid: index for index, amino_acid in enumerate(AMINO_ACIDS)}

STANDARD_DNA_TABLE = unambiguous_dna_by_name["Standard"]
STANDARD_STOP_CODONS = frozenset(STANDARD_DNA_TABLE.stop_codons)
MIDI_NOTE_PATTERN = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")


def parse_midi_pitch(value: str) -> int:
    """Parse an integer MIDI pitch or a standard note name such as C4 or Bb2."""
    normalized = value.strip()
    try:
        pitch = int(normalized)
    except ValueError as error:
        match = MIDI_NOTE_PATTERN.fullmatch(normalized)
        if match is None:
            raise ValueError(f"Invalid MIDI note: {value!r}") from error
        letter, accidental, octave_text = match.groups()
        note_name = letter.upper() + ("B" if accidental == "b" else accidental)
        pitch_class = NOTE_PITCH_CLASSES.get(note_name)
        if pitch_class is None:
            raise ValueError(f"Invalid MIDI note: {value!r}") from error
        pitch = (int(octave_text) + 1) * 12 + pitch_class
    if not 0 <= pitch <= 127:
        raise ValueError(f"MIDI pitch must be between 0 and 127: {value!r}")
    return pitch


def parse_nucleotide_notes(value: str) -> dict[str, int]:
    """Parse an absolute MIDI pitch mapping for A, C, G, and T."""
    notes: dict[str, int] = {}
    for item in value.split(","):
        try:
            base, pitch_text = item.split("=", 1)
        except ValueError:
            raise ValueError(f"Invalid nucleotide mapping entry: {item!r}") from None
        base = base.strip().upper()
        if base not in BASES:
            raise ValueError(f"Unknown nucleotide in mapping: {base!r}")
        if base in notes:
            raise ValueError(f"Duplicate nucleotide in mapping: {base!r}")
        try:
            notes[base] = parse_midi_pitch(pitch_text)
        except ValueError as error:
            raise ValueError(f"Invalid MIDI pitch for {base}: {error}") from None
    if set(notes) != set(BASES):
        raise ValueError("Nucleotide mapping must specify A, C, G, and T")
    return notes


def nucleotide_pitch(
    base: str,
    root: int = 36,
    note_mapping: Mapping[str, int] | None = None,
) -> int:
    """Map a nucleotide to a bass pitch; ambiguous bases use a neutral fifth."""
    normalized = base.upper()
    if note_mapping is not None and normalized in note_mapping:
        return note_mapping[normalized]
    return root + BASE_OFFSETS.get(normalized, 5)


def move_to_scale(pitch: int, allowed_pitch_classes: frozenset[int]) -> int:
    """Move a MIDI pitch to the nearest note in the scale."""
    candidates = (
        note
        for note in range(max(0, pitch - 11), min(127, pitch + 11) + 1)
        if note % 12 in allowed_pitch_classes
    )
    return min(candidates, key=lambda note: (abs(note - pitch), note))


def codon_index(codon: str) -> int:
    """Return a stable index for a codon in the A/C/G/T lexicographic order."""
    normalized = codon.upper()
    if len(normalized) != 3 or any(base not in BASES for base in normalized):
        raise ValueError(f"Invalid codon: {codon!r}")
    index = 0
    for base in normalized:
        index = index * 4 + BASES.index(base)
    return index


def codon_amino_acid(codon: str) -> str | None:
    """Return the standard genetic-code amino acid for a canonical codon."""
    normalized = codon.upper()
    codon_index(normalized)
    return STANDARD_DNA_TABLE.forward_table.get(normalized)


def codon_pitch(
    codon: str,
    root: int = 60,
    amino_acid_mapping: bool = False,
    melody_octaves: int | None = None,
) -> int:
    """Map a codon to a deterministic diatonic melody pitch."""
    if melody_octaves is not None and melody_octaves <= 0:
        raise ValueError("melody_octaves must be positive")
    if amino_acid_mapping:
        amino_acid = codon_amino_acid(codon)
        if amino_acid is None:
            raise ValueError(f"Stop codon has no amino-acid pitch: {codon!r}")
        index = AMINO_ACID_INDEX[amino_acid]
        scale_intervals = SCALE_INTERVALS[:-1]
        if melody_octaves is not None:
            index %= melody_octaves * len(scale_intervals)
        return root + (index // len(scale_intervals)) * 12 + scale_intervals[index % len(scale_intervals)]
    index = codon_index(codon)
    if melody_octaves is not None:
        scale_intervals = SCALE_INTERVALS[:-1]
        index %= melody_octaves * len(scale_intervals)
        return root + (index // len(scale_intervals)) * 12 + scale_intervals[index % len(scale_intervals)]
    return root + (index // len(SCALE_INTERVALS)) % 2 * 12 + SCALE_INTERVALS[index % len(SCALE_INTERVALS)]


def codon_notes(
    codon: str,
    root: int = 60,
    mode: str = "notes",
    amino_acid_mapping: bool = False,
    melody_octaves: int | None = None,
) -> tuple[int, ...]:
    """Return one note or a major triad for a codon."""
    if amino_acid_mapping and codon_amino_acid(codon) is None:
        return ()
    pitch = codon_pitch(codon, root, amino_acid_mapping, melody_octaves)
    if mode == "notes":
        return (pitch,)
    if mode == "chords":
        return (pitch, pitch + 4, pitch + 7)
    raise ValueError(f"Unknown melody mode: {mode!r}")


def scale_pitch_classes(scale: str) -> frozenset[int]:
    """Return the MIDI pitch classes included in a named major or minor scale."""
    normalized = scale.strip().upper().replace(" ", "-")
    try:
        root, mode = normalized.rsplit("-", 1)
        root_pitch_class = NOTE_PITCH_CLASSES[root]
        intervals = SCALE_PATTERNS[mode.lower()]
    except (KeyError, ValueError):
        supported = ", ".join(f"<root>-{mode}" for mode in SCALE_PATTERNS)
        raise ValueError(f"Unknown scale {scale!r}; expected one of: {supported}") from None
    return frozenset((root_pitch_class + interval) % 12 for interval in intervals)


def codons(sequence: str) -> list[str]:
    """Split a sequence into complete codons and ignore a trailing partial codon."""
    normalized = sequence.upper()
    return [normalized[index : index + 3] for index in range(0, len(normalized) - 2, 3)]


def all_codons() -> tuple[str, ...]:
    """Return every canonical codon in the mapping order."""
    return tuple("".join(parts) for parts in product(BASES, repeat=3))
