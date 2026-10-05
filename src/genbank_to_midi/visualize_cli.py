"""Command-line interface for rendering MIDI visualizations."""

from __future__ import annotations

import argparse
from pathlib import Path

from .visualize import render_midi_visualization


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render MIDI notes as a time-by-pitch PNG or SVG")
    parser.add_argument("input", type=Path, help="Input MIDI file")
    parser.add_argument("-p", "--palette", required=True, type=Path, help="Palette file with one hex color per line")
    parser.add_argument("-o", "--output", required=True, type=Path, help="Output PNG file")
    parser.add_argument("--width", type=int, default=1024, help="Output image width in pixels")
    parser.add_argument("--height", type=int, default=1024, help="Output image height in pixels")
    parser.add_argument("--format", choices=("png", "svg"), help="Output format; otherwise inferred from the output extension")
    parser.add_argument(
        "--randomness",
        type=float,
        default=0.0,
        help="Amount of bounded position and color variation, from 0 to 1",
    )
    parser.add_argument("--seed", type=int, help="Optional seed for repeatable randomness")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.width <= 0 or args.height <= 0:
        parser.error("width and height must be positive")
    if not 0 <= args.randomness <= 1:
        parser.error("randomness must be between 0 and 1")
    if not args.input.is_file():
        parser.error(f"Input MIDI file does not exist: {args.input}")
    if not args.palette.is_file():
        parser.error(f"Palette file does not exist: {args.palette}")
    try:
        render_midi_visualization(
            args.input,
            args.palette,
            args.output,
            width=args.width,
            height=args.height,
            output_format=args.format,
            randomness=args.randomness,
            seed=args.seed,
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())