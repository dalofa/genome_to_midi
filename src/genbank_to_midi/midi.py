"""MIDI rendering for bass and gene melody tracks."""

from __future__ import annotations

from pathlib import Path
import logging
from typing import Iterable, Mapping

from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from .mapping import (
    STANDARD_STOP_CODONS,
    codon_notes,
    codons,
    move_to_scale,
    nucleotide_pitch,
    scale_pitch_classes,
)
from .parser import SelectedFeature

logger = logging.getLogger(__name__)


def _add_note(track: MidiTrack, pitch: int, duration: int, velocity: int, channel: int) -> None:
    track.append(Message("note_on", note=pitch, velocity=velocity, time=0, channel=channel))
    track.append(Message("note_off", note=pitch, velocity=0, time=duration, channel=channel))


def _add_chord(track: MidiTrack, notes: tuple[int, ...], duration: int, velocity: int, channel: int) -> None:
    for note in notes:
        track.append(Message("note_on", note=note, velocity=velocity, time=0, channel=channel))
    track.append(Message("note_off", note=notes[0], velocity=0, time=duration, channel=channel))
    for note in notes[1:]:
        track.append(Message("note_off", note=note, velocity=0, time=0, channel=channel))


def _add_header(track: MidiTrack, name: str, tempo: int) -> None:
    track.append(MetaMessage("track_name", name=name, time=0))
    track.append(MetaMessage("set_tempo", tempo=tempo, time=0))
    track.append(MetaMessage("time_signature", numerator=4, denominator=4, time=0))


def _add_scheduled_events(
    track: MidiTrack,
    events: list[tuple[int, int, str, int]],
    channel: int,
    velocity: int,
) -> None:
    previous_time = 0
    for event_time, _, event_type, pitch in sorted(events, key=lambda event: event[:2]):
        track.append(
            Message(
                event_type,
                note=pitch,
                velocity=velocity if event_type == "note_on" else 0,
                time=event_time - previous_time,
                channel=channel,
            )
        )
        previous_time = event_time


def render_midi(
    records: Iterable,
    features: Iterable[SelectedFeature],
    output_path: Path,
    *,
    tempo: int = 100,
    ticks_per_beat: int = 480,
    bass_duration: int = 120,
    codon_duration: int = 480,
    bass_root: int = 36,
    melody_root: int = 60,
    velocity: int = 80,
    bass_program: int = 38,
    melody_program: int = 80,
    melody_mode: str = "notes",
    scale: str | None = None,
    amino_acid_mapping: bool = False,
    nucleotide_notes: Mapping[str, int] | None = None,
    arpeggiate: bool = False,
    melody_octaves: int | None = None,
) -> tuple[int, int]:
    """Write a Type 1 MIDI file and return bass and melody note counts."""
    logger.info("Starting MIDI rendering: %s (melody mode: %s)", output_path, melody_mode)
    if melody_octaves is not None and melody_octaves <= 0:
        raise ValueError("melody_octaves must be positive")
    if arpeggiate and codon_duration < 3:
        raise ValueError("codon_duration must be at least 3 when arpeggiate is enabled")
    records = list(records)
    features = list(features)
    allowed_pitch_classes = scale_pitch_classes(scale) if scale is not None else None
    midi = MidiFile(type=1, ticks_per_beat=ticks_per_beat)
    bass_track = MidiTrack()
    melody_track = MidiTrack()
    midi.tracks.extend((bass_track, melody_track))
    microseconds = bpm2tempo(tempo)
    _add_header(bass_track, "Bass - nucleotide sequence", microseconds)
    _add_header(melody_track, "Genes - codon melody", microseconds)
    bass_track.append(Message("program_change", program=bass_program, channel=0, time=0))
    melody_track.append(Message("program_change", program=melody_program, channel=1, time=0))

    record_offsets: dict[str, int] = {}
    sequence_offset = 0
    for record in records:
        record_offsets.setdefault(str(getattr(record, "id", "")), sequence_offset)
        sequence_offset += len(str(record.seq))

    bass_count = 0
    for record in records:
        for base in str(record.seq).upper():
            pitch = nucleotide_pitch(base, bass_root, nucleotide_notes)
            if allowed_pitch_classes is not None:
                pitch = move_to_scale(pitch, allowed_pitch_classes)
            _add_note(bass_track, pitch, bass_duration, velocity, 0)
            bass_count += 1
    logger.info("Generated bass track with %d note(s)", bass_count)

    melody_count = 0
    melody_events: list[tuple[int, int, str, int]] = []
    for feature in features:
        record_offset = record_offsets.get(feature.record_id, 0)
        for codon_index, codon in enumerate(codons(feature.sequence)):
            notes: tuple[int, ...]
            if amino_acid_mapping and codon.upper() in STANDARD_STOP_CODONS:
                notes = ()
            else:
                notes = codon_notes(
                    codon,
                    melody_root,
                    melody_mode,
                    amino_acid_mapping,
                    melody_octaves,
                )
            if allowed_pitch_classes is not None:
                notes = tuple(move_to_scale(note, allowed_pitch_classes) for note in notes)
            if not notes:
                continue
            if feature.strand == -1:
                codon_start = feature.end - (codon_index + 1) * 3
            else:
                codon_start = feature.start + codon_index * 3
            start_time = (record_offset + codon_start) * bass_duration
            end_time = start_time + 3 * bass_duration
            if arpeggiate and melody_mode == "chords":
                tone_duration, remainder = divmod(codon_duration, len(notes))
                note_time = start_time
                for note_index, note in enumerate(notes):
                    duration = tone_duration + (remainder if note_index == len(notes) - 1 else 0)
                    melody_events.append((note_time, 1, "note_on", note))
                    melody_events.append((note_time + duration, 0, "note_off", note))
                    note_time += duration
            else:
                for note in notes:
                    melody_events.append((start_time, 1, "note_on", note))
                    melody_events.append((end_time, 0, "note_off", note))
            melody_count += len(notes)
    _add_scheduled_events(melody_track, melody_events, 1, velocity)
    logger.info("Generated melody track with %d note(s)", melody_count)

    bass_track.append(MetaMessage("end_of_track", time=0))
    melody_track.append(MetaMessage("end_of_track", time=0))
    midi.save(output_path)
    logger.info("Saved MIDI file: %s", output_path)
    return bass_count, melody_count
