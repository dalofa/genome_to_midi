"""Command-line interface for GenBank to MIDI conversion."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .mapping import parse_nucleotide_notes
from .midi import render_midi
from .parser import parse_genbank

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert GenBank sequences and genes into MIDI")
    parser.add_argument("inputs", nargs="+", type=Path, help="Input GenBank file(s)")
    parser.add_argument("-o", "--output", required=True, type=Path, help="Output MIDI file")
    parser.add_argument("--tempo", type=int, default=100, help="Tempo in beats per minute")
    parser.add_argument("--ticks-per-beat", type=int, default=480)
    parser.add_argument("--bass-duration", type=int, default=120, help="Bass note duration in ticks")
    parser.add_argument("--codon-duration", type=int, default=480, help="Melody note duration in ticks")
    parser.add_argument("--bass-root", type=int, default=36, help="MIDI pitch for the bass root")
    parser.add_argument("--melody-root", type=int, default=60, help="MIDI pitch for the melody root")
    parser.add_argument("--velocity", type=int, default=80)
    parser.add_argument("--bass-program", type=int, default=38, help="General MIDI bass program, 0-based")
    parser.add_argument("--melody-program", type=int, default=80, help="General MIDI lead program, 0-based")
    parser.add_argument("--melody-mode", choices=("notes", "chords"), default="notes")
    parser.add_argument("--scale", help="Optional named major or minor scale, such as A-minor")
    parser.add_argument(
        "--amino-acid-mapping",
        action="store_true",
        help="Map synonymous codons to the same melody note and skip stop codons",
    )
    parser.add_argument(
        "--nucleotide-notes",
        help="Absolute MIDI pitches, such as A=36,C=39,G=43,T=46",
    )
    parser.add_argument(
        "--arpeggiate",
        action="store_true",
        help="Play chord tones in ascending order within each codon duration",
    )
    parser.add_argument(
        "--melody-octaves",
        type=int,
        help="Limit melody roots to this many octaves above melody-root",
    )
    return parser


def _positive(value: int, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger.info("Validating %d input file(s)", len(args.inputs))
    try:
        for input_path in args.inputs:
            if not input_path.is_file():
                raise ValueError(f"Input file does not exist: {input_path}")
        for value, name in (
            (args.tempo, "tempo"),
            (args.ticks_per_beat, "ticks-per-beat"),
            (args.bass_duration, "bass-duration"),
            (args.codon_duration, "codon-duration"),
        ):
            _positive(value, name)
        if args.melody_octaves is not None:
            _positive(args.melody_octaves, "melody-octaves")
        if not 0 <= args.velocity <= 127:
            raise ValueError("velocity must be between 0 and 127")
        for value, name in ((args.bass_program, "bass-program"), (args.melody_program, "melody-program")):
            if not 0 <= value <= 127:
                raise ValueError(f"{name} must be between 0 and 127")
        logger.info("Validation complete")
        nucleotide_notes = parse_nucleotide_notes(args.nucleotide_notes) if args.nucleotide_notes else None
        if args.arpeggiate and args.codon_duration < 3:
            raise ValueError("codon-duration must be at least 3 when arpeggiate is enabled")
        records, features = parse_genbank(args.inputs)
        if not records:
            raise ValueError("No GenBank records were found")
        if not any(str(record.seq) for record in records):
            raise ValueError("GenBank records contain no sequence")
        logger.info("Rendering %d record(s) and %d melody feature(s)", len(records), len(features))
        bass_count, melody_count = render_midi(
            records,
            features,
            args.output,
            tempo=args.tempo,
            ticks_per_beat=args.ticks_per_beat,
            bass_duration=args.bass_duration,
            codon_duration=args.codon_duration,
            bass_root=args.bass_root,
            melody_root=args.melody_root,
            velocity=args.velocity,
            bass_program=args.bass_program,
            melody_program=args.melody_program,
            melody_mode=args.melody_mode,
            scale=args.scale,
            amino_acid_mapping=args.amino_acid_mapping,
            nucleotide_notes=nucleotide_notes,
            arpeggiate=args.arpeggiate,
            melody_octaves=args.melody_octaves,
        )
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(f"Wrote {args.output}: {len(records)} record(s), {len(features)} melody feature(s), {bass_count} bass notes, {melody_count} melody notes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
